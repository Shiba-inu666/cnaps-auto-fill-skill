# CNAPS Auto Fill Skill / 开户行行号自动填充 Skill

A bilingual Codex Skill for resolving Chinese bank opening-branch names to 12-digit CNAPS routing codes and filling payroll or payment workbooks.

用于把中国银行开户行名称解析为 12 位 CNAPS／人行支付系统行号，并自动填写工资表或付款模板的中英文 Codex Skill。

## Features / 功能

- Reuses a persistent, evidence-backed local CNAPS registry. / 复用带证据来源的持久化本地行号库。
- Searches missing codes with privacy-safe, multi-source verification. / 对缺失行号进行隐私安全的联网搜索和多来源核验。
- Falls back to the nearest verified parent or head office when no dedicated branch code is usable. / 没有可用支行号时，默认使用最近的已核验上级行或总行号兜底。
- Produces an audit trail and warns about fallbacks, old bank names, incomplete branch data, conflicts, and unresolved rows. / 生成审计记录，并提示兜底、旧称、支行信息不完整、冲突和未解析记录。
- Prevents account numbers, identity data, phone numbers, amounts, and other payment-row data from entering searches or the registry. / 禁止把账号、身份信息、手机号、金额及其他付款逐行数据发送到搜索服务或写入行号库。

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
使用 cnaps-auto-fill 帮我填写这份工资表的银行行号。
缺失支行号时自动搜索，必要时使用已核验的上级行或总行号兜底，并提示风险行。
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
