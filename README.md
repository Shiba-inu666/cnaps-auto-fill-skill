# CNAPS Auto Fill Skill / 开户行行号自动填充 Skill

Codex-only Skill for resolving Chinese bank opening-branch names to 12-digit CNAPS routing codes and filling workbooks.

Codex 专用技能：依据开户行名称补全 12 位 CNAPS／人行支付系统行号。

## Features / 功能

- Reuses a persistent, evidence-backed local CNAPS registry. / 复用带证据来源的持久化本地行号库。
- After locating headers, reads only the opening-bank and CNAPS-code columns. / 定位表头后只读取开户行和行号两列。
- Searches missing codes with privacy-safe, multi-source verification. / 对缺失行号进行隐私安全的联网搜索和多来源核验。
- Falls back to the nearest verified parent or head office when no dedicated branch code is usable. / 没有可用支行号时，默认使用最近的已核验上级行或总行号兜底。
- Warns concisely about fallbacks, conflicts, and unresolved rows. / 简要提示兜底、冲突和未解析记录。
- Never reads other data columns after header detection. / 识别目标列后不再读取其他业务列。

## Install / 安装

Copy or clone this repository into the Codex skills directory:

将本仓库复制或克隆到 Codex Skills 目录：

```bash
git clone https://github.com/Shiba-inu666/cnaps-auto-fill-skill.git ~/.codex/skills/cnaps-auto-fill
```

Restart Codex or open a new task so the Skill can be discovered.

重启 Codex 或新建任务，使 Skill 被重新发现。

## Usage / 使用

Ask Codex naturally, for example:

直接用自然语言提出请求，例如：

```text
使用 cnaps-auto-fill，只读取开户行和行号两列，快速填写缺失行号。
```

Registry commands / 注册表命令：

```bash
python3 scripts/cnaps_registry.py init
python3 scripts/cnaps_registry.py lookup --name '中国工商银行总行'
python3 scripts/cnaps_registry.py stats
python3 scripts/cnaps_registry.py export --output cnaps-registry-export.csv
```

The default mutable registry is stored outside the repository at `~/.codex/state/cnaps-auto-fill/registry.sqlite3`.

默认的可变注册表保存在仓库之外：`~/.codex/state/cnaps-auto-fill/registry.sqlite3`。

## Safety Notice / 安全提示

CNAPS data can change after bank renames, mergers, relocations, or outlet closures. Always verify critical payment instructions with the receiving bank. Seed records are provided as a research aid with source URLs, not as a warranty of current correctness.

银行改名、合并、迁址或网点撤销后，CNAPS 行号可能发生变化。重要付款指令必须向收款银行再次确认。种子数据仅作为带来源链接的检索辅助，不保证始终正确或最新。

## Validation / 校验

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/cnaps_registry.py --db /tmp/cnaps-test.sqlite3 init
python3 scripts/cnaps_registry.py --db /tmp/cnaps-test.sqlite3 stats
```

## License / 许可证

MIT. See [LICENSE](LICENSE).
