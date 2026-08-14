# 银行行号还在一个个查？现在可以一键补全

把工资表、付款表交给 Codex，说一句“帮我填写银行行号”，剩下的交给 `cnaps-auto-fill`。

过去处理银行行号，最费时间的往往不是填表，而是逐行搜索、复制、核对。遇到开户行只写“中国工商银行”、支行名称缺失、银行使用旧称，或者同事随手填了一个不完整名称，还得反复确认到底该用哪个 12 位行号。一张几十行的表，查起来琐碎，填错了又可能影响付款。

`cnaps-auto-fill` 把这套流程变成一次自动处理：读取表格、识别开户行、查询本地行号库、自动搜索缺失记录、进行多来源核验，再把结果写回原表。没有可用的支行行号时，它会按规则选择已核验的上级行或总行号兜底，同时列出需要人工留意的行。

> 从“一个个查、一个个复制”变成“上传表格，一键生成填写结果”。

## 能解决什么

- **开户行填写不规范**：识别常见简称、旧称和安全别名。
- **行号需要逐条查询**：先查本地注册表，缺失时自动联网检索。
- **结果不知道能不能用**：要求两个独立来源核验，保留来源和检查日期。
- **支行信息缺失**：找不到专属支行号时，按规则使用已核验的最近上级行或总行号兜底。
- **填完难以复核**：自动记录匹配方式，并提示兜底、旧称、地区缺失、来源冲突和未解析记录。
- **担心工资表泄露**：搜索时只使用银行名称和地区，不发送姓名、账号、卡号、身份证号、手机号、金额等付款数据。

## 一句话使用

把 `.xls`、`.xlsx`、`.csv` 或 `.tsv` 文件交给 Codex，然后说：

```text
使用 cnaps-auto-fill 帮我填写这份工资表的银行行号。
缺失行号自动搜索，没有专属支行号时使用已核验的上级行或总行号兜底，完成后提示可能有问题的行。
```

处理完成后会得到一份新文件，原文件默认不覆盖。对于可能影响付款准确性的记录，还会附上清晰的风险提示。

## 它是怎么工作的

```text
读取表格
  ↓
识别开户行与空白行号
  ↓
查询本地已核验注册表
  ↓
缺失记录自动搜索并交叉核验
  ↓
精确匹配 → 最近上级行 → 区域上级行 → 全国总行
  ↓
写回新表格并输出风险清单
```

所有兜底结果都会标记为 `parent_fallback`。模糊匹配、跨银行候选或来源冲突不会被强行写入付款表。

## 安装

克隆到 Codex Skills 目录：

```bash
git clone https://github.com/Shiba-inu666/cnaps-auto-fill-skill.git ~/.codex/skills/cnaps-auto-fill
```

重启 Codex 或新建任务，让 Skill 被重新发现。

## 本地行号库

Skill 自带一份带来源链接的种子注册表。运行后，可变数据会保存到仓库之外：

```text
~/.codex/state/cnaps-auto-fill/registry.sqlite3
```

常用命令：

```bash
python3 scripts/cnaps_registry.py init
python3 scripts/cnaps_registry.py lookup --name '中国工商银行总行'
python3 scripts/cnaps_registry.py stats
python3 scripts/cnaps_registry.py export --output cnaps-registry-export.csv
```

## 安全说明

银行改名、合并、迁址或网点撤销后，CNAPS 行号可能变化。种子记录用于提高检索效率，并保留了证据来源，但不能替代银行的最终确认。大额或关键付款前，仍应向收款银行核实开户行名称和行号。

## 校验

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/cnaps_registry.py --db /tmp/cnaps-test.sqlite3 init
python3 scripts/cnaps_registry.py --db /tmp/cnaps-test.sqlite3 stats
```

## 开源许可

本项目采用 [MIT License](LICENSE)。
