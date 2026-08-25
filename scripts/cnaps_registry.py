#!/usr/bin/env python3
"""Persistent, auditable registry for Chinese CNAPS branch codes."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse


CODE_RE = re.compile(r"^\d{12}$")
MIN_EVIDENCE_ORIGINS = 1
DEFAULT_DB = Path.home() / ".codex" / "state" / "cnaps-auto-fill" / "registry.sqlite3"
DEFAULT_SEED = Path(__file__).resolve().parent.parent / "assets" / "seed-registry.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


def validate_code(code: str) -> str:
    code = str(code).strip()
    if not CODE_RE.fullmatch(code):
        raise ValueError(f"CNAPS code must contain exactly 12 digits: {code!r}")
    return code


def parse_source(value: str) -> tuple[str, str, str]:
    if "=" in value:
        source_type, locator = value.split("=", 1)
    else:
        locator = value
        source_type = "web" if value.startswith(("http://", "https://")) else "manual"
    source_type = source_type.strip() or "web"
    locator = locator.strip()
    if not locator:
        raise ValueError("Evidence source locator cannot be empty")
    parsed = urlparse(locator)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        origin = parsed.hostname.lower()
        if origin.startswith("www."):
            origin = origin[4:]
    elif parsed.scheme == "manual":
        authority = parsed.netloc or parsed.path.strip("/") or "confirmation"
        origin = f"manual:{authority.lower()}"
    else:
        raise ValueError(
            "Evidence must be an http(s) URL or a non-personal manual:// confirmation locator"
        )
    return source_type, locator, origin


def resolve_db(cli_value: str | None) -> Path:
    raw = cli_value or os.environ.get("CNAPS_REGISTRY_PATH")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_DB


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS banks (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            code TEXT NOT NULL CHECK(length(code) = 12),
            bank_level TEXT NOT NULL DEFAULT 'branch',
            province TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('verified','review','conflict','retired')),
            auto_fill INTEGER NOT NULL DEFAULT 1 CHECK(auto_fill IN (0,1)),
            first_verified_at TEXT,
            last_verified_at TEXT,
            notes TEXT NOT NULL DEFAULT '',
            UNIQUE(canonical_name, code)
        );
        CREATE INDEX IF NOT EXISTS idx_banks_normalized ON banks(normalized_name);

        CREATE TABLE IF NOT EXISTS aliases (
            id INTEGER PRIMARY KEY,
            bank_id INTEGER NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            auto_fill INTEGER NOT NULL DEFAULT 0 CHECK(auto_fill IN (0,1)),
            UNIQUE(bank_id, normalized_alias)
        );
        CREATE INDEX IF NOT EXISTS idx_aliases_normalized ON aliases(normalized_alias);

        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY,
            bank_id INTEGER NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
            source_type TEXT NOT NULL,
            locator TEXT NOT NULL,
            origin TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            supports INTEGER NOT NULL DEFAULT 1 CHECK(supports IN (0,1)),
            note TEXT NOT NULL DEFAULT '',
            UNIQUE(bank_id, locator)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    return conn


def log_event(conn: sqlite3.Connection, action: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO audit_log(action, payload_json, created_at) VALUES (?, ?, ?)",
        (action, json.dumps(payload, ensure_ascii=False, sort_keys=True), now_iso()),
    )


def evidence_origins(conn: sqlite3.Connection, bank_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT origin FROM evidence WHERE bank_id = ? AND supports = 1", (bank_id,)
    ).fetchall()
    return {row["origin"] for row in rows}


def _coerce_alias(item: object) -> tuple[str, bool]:
    if isinstance(item, str):
        return item, False
    if isinstance(item, dict) and item.get("name"):
        return str(item["name"]), bool(item.get("auto_fill", False))
    raise ValueError(f"Invalid alias entry: {item!r}")


def upsert_mapping(conn: sqlite3.Connection, record: dict, action: str) -> dict:
    name = str(record["canonical_name"]).strip()
    if not name:
        raise ValueError("canonical_name cannot be empty")
    code = validate_code(str(record["code"]))
    normalized = normalize_name(name)
    if not normalized:
        raise ValueError("canonical_name has no searchable characters")
    checked_at = str(record.get("checked_at") or date.today().isoformat())
    requested_status = str(record.get("status") or "verified")
    if requested_status not in {"verified", "review", "conflict", "retired"}:
        raise ValueError(f"Unsupported status: {requested_status}")

    row = conn.execute(
        "SELECT id, first_verified_at FROM banks WHERE canonical_name = ? AND code = ?",
        (name, code),
    ).fetchone()
    first_verified_at = row["first_verified_at"] if row else None
    if row:
        bank_id = row["id"]
        conn.execute(
            """
            UPDATE banks SET normalized_name=?, bank_level=?, province=?, city=?,
                auto_fill=?, last_verified_at=?, notes=? WHERE id=?
            """,
            (
                normalized,
                str(record.get("bank_level") or "branch"),
                str(record.get("province") or ""),
                str(record.get("city") or ""),
                int(bool(record.get("auto_fill", True))),
                checked_at,
                str(record.get("notes") or ""),
                bank_id,
            ),
        )
    else:
        cur = conn.execute(
            """
            INSERT INTO banks(
                canonical_name, normalized_name, code, bank_level, province, city,
                status, auto_fill, first_verified_at, last_verified_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, 'review', ?, NULL, ?, ?)
            """,
            (
                name,
                normalized,
                code,
                str(record.get("bank_level") or "branch"),
                str(record.get("province") or ""),
                str(record.get("city") or ""),
                int(bool(record.get("auto_fill", True))),
                checked_at,
                str(record.get("notes") or ""),
            ),
        )
        bank_id = int(cur.lastrowid)

    for source in record.get("sources", []):
        if isinstance(source, str):
            source_type, locator, origin = parse_source(source)
            note = ""
        else:
            raw = f"{source.get('source_type', 'web')}={source['url']}"
            source_type, locator, origin = parse_source(raw)
            note = str(source.get("note") or "")
        conn.execute(
            """
            INSERT INTO evidence(bank_id, source_type, locator, origin, checked_at, supports, note)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(bank_id, locator) DO UPDATE SET
                source_type=excluded.source_type, origin=excluded.origin,
                checked_at=excluded.checked_at, supports=1, note=excluded.note
            """,
            (bank_id, source_type, locator, origin, checked_at, note),
        )

    for alias_item in record.get("aliases", []):
        alias, alias_auto_fill = _coerce_alias(alias_item)
        norm_alias = normalize_name(alias)
        if not norm_alias:
            continue
        conn.execute(
            """
            INSERT INTO aliases(bank_id, alias, normalized_alias, auto_fill)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bank_id, normalized_alias) DO UPDATE SET
                alias=excluded.alias, auto_fill=excluded.auto_fill
            """,
            (bank_id, alias, norm_alias, int(alias_auto_fill)),
        )

    origins = evidence_origins(conn, bank_id)
    conflicting = conn.execute(
        """
        SELECT id, code FROM banks
        WHERE normalized_name = ? AND code <> ? AND status = 'verified'
        """,
        (normalized, code),
    ).fetchall()
    if conflicting:
        final_status = "conflict"
    elif requested_status == "retired":
        final_status = "retired"
    elif requested_status == "review":
        final_status = "review"
    elif len(origins) >= MIN_EVIDENCE_ORIGINS:
        final_status = "verified"
    else:
        final_status = "review"

    verified_at = (first_verified_at or checked_at) if final_status == "verified" else first_verified_at
    conn.execute(
        "UPDATE banks SET status=?, first_verified_at=?, last_verified_at=? WHERE id=?",
        (final_status, verified_at, checked_at, bank_id),
    )
    payload = {
        "bank_id": bank_id,
        "canonical_name": name,
        "code": code,
        "status": final_status,
        "origins": sorted(origins),
    }
    if conflicting:
        payload["conflicts_with"] = [dict(item) for item in conflicting]
    log_event(conn, action, payload)
    return payload


def import_seed(conn: sqlite3.Connection, seed_path: Path) -> dict:
    imported = 0
    errors: list[dict] = []
    if not seed_path.exists():
        return {"imported": 0, "errors": [], "seed": str(seed_path), "missing": True}
    with seed_path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
                upsert_mapping(conn, record, "seed_import")
                imported += 1
            except Exception as exc:  # report all bad seed rows together
                errors.append({"line": line_number, "error": str(exc)})
    conn.commit()
    return {"imported": imported, "errors": errors, "seed": str(seed_path)}


def initialize_if_empty(conn: sqlite3.Connection, seed_path: Path = DEFAULT_SEED) -> dict | None:
    count = conn.execute("SELECT COUNT(*) AS n FROM banks").fetchone()["n"]
    return import_seed(conn, seed_path) if count == 0 else None


def bank_payload(conn: sqlite3.Connection, row: sqlite3.Row, matched_by: str, alias_safe: bool) -> dict:
    sources = [
        dict(item)
        for item in conn.execute(
            """
            SELECT source_type, locator, origin, checked_at, note
            FROM evidence WHERE bank_id=? AND supports=1
            ORDER BY checked_at DESC, id
            """,
            (row["id"],),
        ).fetchall()
    ]
    return {
        "bank_id": row["id"],
        "canonical_name": row["canonical_name"],
        "code": row["code"],
        "bank_level": row["bank_level"],
        "province": row["province"],
        "city": row["city"],
        "record_status": row["status"],
        "record_auto_fill": bool(row["auto_fill"]),
        "matched_by": matched_by,
        "alias_auto_fill": alias_safe,
        "checked_at": row["last_verified_at"],
        "notes": row["notes"],
        "sources": sources,
    }


def location_score(row: sqlite3.Row, province: str, city: str) -> int:
    score = 0
    if province and normalize_name(row["province"]) == normalize_name(province):
        score += 1
    if city and normalize_name(row["city"]) == normalize_name(city):
        score += 2
    return score


def lookup_one(conn: sqlite3.Connection, name: str, province: str = "", city: str = "") -> dict:
    normalized = normalize_name(name)
    exact: dict[int, tuple[sqlite3.Row, str, bool]] = {}
    for row in conn.execute("SELECT * FROM banks WHERE normalized_name=?", (normalized,)).fetchall():
        exact[row["id"]] = (row, "canonical_exact", True)
    for row in conn.execute(
        """
        SELECT b.*, a.auto_fill AS alias_auto_fill
        FROM aliases a JOIN banks b ON b.id=a.bank_id
        WHERE a.normalized_alias=?
        """,
        (normalized,),
    ).fetchall():
        exact.setdefault(row["id"], (row, "approved_alias" if row["alias_auto_fill"] else "alias_review", bool(row["alias_auto_fill"])))

    candidates = list(exact.values())
    if province or city:
        positive = [item for item in candidates if location_score(item[0], province, city) > 0]
        if positive:
            best = max(location_score(item[0], province, city) for item in positive)
            candidates = [item for item in positive if location_score(item[0], province, city) == best]

    payloads = [bank_payload(conn, *item) for item in candidates]
    fillable = [
        item
        for item in payloads
        if item["record_status"] == "verified"
        and item["record_auto_fill"]
        and (item["matched_by"] == "canonical_exact" or item["alias_auto_fill"])
    ]
    if len(payloads) == 1 and len(fillable) == 1:
        status = "auto_fill_ready"
        autofill_code = fillable[0]["code"]
    elif payloads and all(item["record_status"] == "verified" for item in payloads):
        status = "verified_match"
        autofill_code = None
    elif payloads and any(item["record_status"] == "conflict" for item in payloads):
        status = "conflict"
        autofill_code = None
    elif payloads:
        status = "review"
        autofill_code = None
    else:
        fuzzy_rows = conn.execute(
            """
            SELECT b.*, b.canonical_name AS candidate_text
            FROM banks b WHERE b.status <> 'retired'
            UNION ALL
            SELECT b.*, a.alias AS candidate_text
            FROM aliases a JOIN banks b ON b.id=a.bank_id WHERE b.status <> 'retired'
            """
        ).fetchall()
        scored: dict[int, tuple[float, sqlite3.Row]] = {}
        for row in fuzzy_rows:
            ratio = SequenceMatcher(None, normalized, normalize_name(row["candidate_text"])).ratio()
            if ratio >= 0.72 and (row["id"] not in scored or ratio > scored[row["id"]][0]):
                scored[row["id"]] = (ratio, row)
        suggestions = [
            {
                "canonical_name": row["canonical_name"],
                "code": row["code"],
                "record_status": row["status"],
                "similarity": round(score, 3),
            }
            for score, row in sorted(scored.values(), key=lambda item: (-item[0], item[1]["canonical_name"]))[:5]
        ]
        return {
            "query": name,
            "province": province,
            "city": city,
            "status": "unknown",
            "autofill_code": None,
            "candidates": [],
            "suggestions": suggestions,
        }
    return {
        "query": name,
        "province": province,
        "city": city,
        "status": status,
        "autofill_code": autofill_code,
        "candidates": payloads,
        "suggestions": [],
    }


def cmd_init(args: argparse.Namespace) -> int:
    db_path = resolve_db(args.db)
    conn = connect(db_path)
    if args.no_seed:
        result = {"imported": 0, "errors": [], "seed": None}
    else:
        result = import_seed(conn, Path(args.seed).expanduser().resolve())
    result["database"] = str(db_path)
    result["records"] = conn.execute("SELECT COUNT(*) AS n FROM banks").fetchone()["n"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


def cmd_lookup(args: argparse.Namespace) -> int:
    db_path = resolve_db(args.db)
    conn = connect(db_path)
    initialize_if_empty(conn)
    results = [lookup_one(conn, name, args.province or "", args.city or "") for name in args.name]
    output: object = results[0] if len(results) == 1 else results
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    db_path = resolve_db(args.db)
    conn = connect(db_path)
    initialize_if_empty(conn)
    aliases = [{"name": value, "auto_fill": args.alias_auto_fill} for value in args.alias]
    record = {
        "canonical_name": args.name,
        "code": args.code,
        "bank_level": args.level,
        "province": args.province,
        "city": args.city,
        "status": "verified",
        "auto_fill": not args.no_auto_fill,
        "aliases": aliases,
        "sources": args.source,
        "checked_at": args.checked_at or date.today().isoformat(),
        "notes": args.notes,
    }
    result = upsert_mapping(conn, record, "manual_verify")
    conn.commit()
    result["database"] = str(db_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "verified" else 2


def cmd_stats(args: argparse.Namespace) -> int:
    db_path = resolve_db(args.db)
    conn = connect(db_path)
    initialize_if_empty(conn)
    status_counts = {
        row["status"]: row["n"]
        for row in conn.execute("SELECT status, COUNT(*) AS n FROM banks GROUP BY status")
    }
    result = {
        "database": str(db_path),
        "records": conn.execute("SELECT COUNT(*) AS n FROM banks").fetchone()["n"],
        "aliases": conn.execute("SELECT COUNT(*) AS n FROM aliases").fetchone()["n"],
        "evidence": conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"],
        "status": status_counts,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    db_path = resolve_db(args.db)
    conn = connect(db_path)
    initialize_if_empty(conn)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT b.*, GROUP_CONCAT(DISTINCT e.locator) AS sources
        FROM banks b LEFT JOIN evidence e ON e.bank_id=b.id AND e.supports=1
        GROUP BY b.id ORDER BY b.canonical_name, b.code
        """
    ).fetchall()
    fields = [
        "canonical_name", "code", "bank_level", "province", "city", "status",
        "auto_fill", "first_verified_at", "last_verified_at", "notes", "sources",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})
    print(json.dumps({"database": str(db_path), "output": str(output), "rows": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Registry path; defaults to CNAPS_REGISTRY_PATH or ~/.codex/state/cnaps-auto-fill/registry.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create the schema and import seed mappings")
    init.add_argument("--seed", default=str(DEFAULT_SEED))
    init.add_argument("--no-seed", action="store_true")
    init.set_defaults(func=cmd_init)

    lookup = sub.add_parser("lookup", help="Look up one or more bank names")
    lookup.add_argument("--name", action="append", required=True)
    lookup.add_argument("--province", default="")
    lookup.add_argument("--city", default="")
    lookup.set_defaults(func=cmd_lookup)

    verify = sub.add_parser("verify", help="Add or update a mapping with evidence")
    verify.add_argument("--name", required=True)
    verify.add_argument("--code", required=True)
    verify.add_argument("--level", default="branch", choices=["head-office", "clearing-centre", "branch", "sub-branch", "outlet"])
    verify.add_argument("--province", default="")
    verify.add_argument("--city", default="")
    verify.add_argument("--alias", action="append", default=[])
    verify.add_argument("--alias-auto-fill", action="store_true", help="Mark every supplied alias safe for automatic filling")
    verify.add_argument("--source", action="append", required=True, help="Repeat as source_type=URL; use manual=manual://bank-confirmation for a documented bank confirmation")
    verify.add_argument("--checked-at", default="")
    verify.add_argument("--notes", default="")
    verify.add_argument("--no-auto-fill", action="store_true")
    verify.set_defaults(func=cmd_verify)

    stats = sub.add_parser("stats", help="Show registry counts")
    stats.set_defaults(func=cmd_stats)

    export = sub.add_parser("export", help="Export mappings and source links to CSV")
    export.add_argument("--output", required=True)
    export.set_defaults(func=cmd_export)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, sqlite3.Error, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
