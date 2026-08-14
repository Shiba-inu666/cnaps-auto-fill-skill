---
name: cnaps-auto-fill
description: Automatically resolve Chinese bank opening-branch names to 12-digit CNAPS/人行支付系统行号, fill Excel payroll or payment workbooks, reuse a persistent verified registry, automatically research missing codes with privacy-safe model-assisted web search and multi-source verification, and default to the nearest verified parent or verified head-office code when no dedicated branch code is usable. 自动解析中国银行开户行名称并填写12位CNAPS/人行支付系统行号，适用于工资表、付款模板、收款账号开户行、联行号、人行行号的填写、校验、核对、搜索和维护；缺失行号时自动进行隐私安全的联网检索与多来源核验，无可用支行号时默认使用最近的已核验上级行或总行号兜底。Always warn after output about fallback rows, old names, incomplete branch data, conflicts, or unresolved evidence；输出后必须提示兜底行、旧称、支行信息不完整、冲突或证据不足的行。
---

# CNAPS Auto Fill / 开户行行号自动填充

## Core Behavior / 核心行为

Use a persistent local registry for verified branch-name-to-CNAPS mappings. For every blank target cell, try an exact verified match, automatically research unresolved names, then fall back to the nearest uniquely established verified parent and finally the verified national head office.

使用持久化本地注册表保存已经核验的“开户行名称—CNAPS行号”映射。对于每个空白目标单元格，先尝试精确核验匹配，再自动搜索未解析名称；仍无可用支行号时，依次使用唯一且已核验的最近上级行、区域上级行和全国总行号兜底。

Treat the model only as a research orchestrator. Count opened source records—not model output or search snippets—as evidence. Never turn a cross-bank, fuzzy, ambiguous, or conflicting candidate into a payment instruction. Make every fallback visible in the audit and the post-output warning summary.

只把大模型作为检索与核验流程的协调者。只有实际打开的来源页面可以作为证据；模型输出和搜索摘要不能作为证据。不得把跨银行、模糊、歧义或冲突候选项写成付款指令。所有兜底结果都必须出现在审计记录和输出后的风险提示中。

## Workflow / 工作流程

1. Locate this skill directory and use `scripts/cnaps_registry.py`. Let the script create the default registry at `~/.codex/state/cnaps-auto-fill/registry.sqlite3` and import `assets/seed-registry.jsonl` automatically when the registry is empty. Respect `CNAPS_REGISTRY_PATH` or `--db` when the user supplies another location.

   定位本 Skill 目录并使用 `scripts/cnaps_registry.py`。默认注册表位于 `~/.codex/state/cnaps-auto-fill/registry.sqlite3`；注册表为空时，脚本自动导入 `assets/seed-registry.jsonl`。用户通过 `CNAPS_REGISTRY_PATH` 或 `--db` 指定其他位置时，使用用户指定的位置。

2. For Excel, CSV, or TSV files, use the `spreadsheets:Spreadsheets` skill to inspect and edit the workbook. Read [references/workbook-workflow.md](references/workbook-workflow.md) before changing it.

   处理 Excel、CSV 或 TSV 文件时，使用 `spreadsheets:Spreadsheets` Skill 检查和编辑工作簿。修改文件前完整阅读 [references/workbook-workflow.md](references/workbook-workflow.md)。

3. Extract every row with a blank target code, deduplicate opening-bank names with available province and city fields, and process all sheets. Never send or save personal names, account numbers, identity numbers, phone numbers, card numbers, amounts, or other row data in the registry or external searches. Use the default fallback scope `nearest_parent_then_head_office` unless the user explicitly disables or narrows fallback for the current task.

   提取所有目标行号为空的记录，结合可用的省市字段对开户行名称去重，并处理所有工作表。不得把姓名、账号、身份证号、手机号、卡号、金额或其他逐行数据发送到外部搜索，也不得写入注册表。除非用户对当前任务明确禁用或缩小兜底范围，否则默认使用 `nearest_parent_then_head_office`。

4. Query the registry for every distinct bank name. Repeat the same name only when location context differs:

   对每个不同的银行名称查询注册表。只有地区信息不同时，才重复查询同一名称：

   ```bash
   python3 scripts/cnaps_registry.py lookup --name '中国工商银行股份有限公司佛山三水新城支行' --province 广东省 --city 佛山市
   python3 scripts/cnaps_registry.py lookup --name '开户行一' --name '开户行二'
   ```

5. Fill an exact target only when the result has `status: "auto_fill_ready"` and a non-null `autofill_code`. Treat `verified_match` as a candidate rather than an exact fill. For every `verified_match`, `review`, or `unknown`, automatically run the research step and independently look up the nearest unique parent and national head office. Use a parent only when its result is `auto_fill_ready`, and record `parent_fallback` in the audit. Treat `conflict` and ambiguous or cross-bank candidates as non-fillable.

   只有查询结果为 `status: "auto_fill_ready"` 且 `autofill_code` 非空时，才可作为精确匹配写入。把 `verified_match` 视为候选项，而不是可直接精确填充的结果。对每个 `verified_match`、`review` 或 `unknown` 自动执行搜索核验，并独立查询最近的唯一上级行和全国总行。只有上级行结果为 `auto_fill_ready` 时才可兜底，并在审计中记录 `parent_fallback`。`conflict`、歧义候选或跨银行候选均不得填写。

6. For a new, stale, or unresolved branch, read [references/source-policy.md](references/source-policy.md). Use available web-search and browser tools to research the full branch name, region, rename history, and parent relationship. Compare at least two independent opened sources and prefer official records. Search only with the bank name and location context. Never expose payment data, count model output as evidence, or infer a branch code from an account-number prefix.

   遇到新增、过期或未解析的支行时，完整阅读 [references/source-policy.md](references/source-policy.md)。使用可用的网页搜索和浏览器工具检索完整支行名称、地区、改名历史及上下级关系。至少比较两个相互独立且已实际打开的来源，并优先采用官方记录。搜索词仅包含银行名称和地区信息。不得暴露付款数据，不得把模型输出视为证据，也不得根据账号前缀推断行号。

7. Write a mapping to the registry only after the sources satisfy the policy and agree on the same full canonical branch name and 12-digit code:

   只有来源满足证据政策，并且对同一完整规范开户行名称及12位行号得出一致结论后，才把映射写入注册表：

   ```bash
   python3 scripts/cnaps_registry.py verify \
     --name '完整规范开户行名称' \
     --code 123456789012 \
     --province 广东省 --city 佛山市 \
     --alias '可安全等价的名称' \
     --source 'official=https://官方来源.example/page' \
     --source 'directory=https://独立来源.example/record'
   ```

   Pass every source as `source_type=URL`. Record a documented bank confirmation as `manual=manual://bank-confirmation` without including an employee name or customer information. Let the script downgrade fewer than two independent origins to `review` and block conflicting codes.

   每个来源都使用 `source_type=URL` 格式传入。经过记录的银行确认可写为 `manual=manual://bank-confirmation`，但不得包含员工姓名或客户信息。独立来源少于两个时，让脚本自动降级为 `review`；来源行号冲突时必须阻止验证通过。

8. Re-run `lookup` after verification. Fill verified exact or safe-alias rows first, followed by eligible parent fallbacks. For a broad institution-only input without a branch or region, independently look up the unique verified national head office and use it as `parent_fallback` when no nearer parent can be established. Create an audit record containing input name, canonical name, code, status, match method, both source URLs, check date, fallback scope, risk flag, and notes. For every fallback, preserve the input name, put the actual parent in `canonical_bank_name`, and explain why no dedicated outlet code was used. Leave conflicts and unresolved rows blank unless the workbook explicitly requires a marker such as `待确认`.

   核验完成后重新运行 `lookup`。先填写已核验的精确匹配或安全别名，再填写符合条件的上级行兜底。对于只有银行机构名、没有支行或地区的输入，独立查询唯一且已核验的全国总行；无法确定更近的上级行时，将总行号作为 `parent_fallback`。审计记录至少包含：输入名称、规范名称、行号、状态、匹配方式、两个来源网址、核验日期、兜底层级、风险标记和备注。每个兜底记录都要保留原始输入名称，把实际使用的上级行写入 `canonical_bank_name`，并说明未使用专属网点行号的原因。冲突和未解析行保持空白，除非工作簿明确要求填写 `待确认` 等标记。

9. Save a new output workbook unless the user explicitly requests overwriting. Render or otherwise inspect every changed sheet before delivery.

   除非用户明确要求覆盖原文件，否则保存为新的输出工作簿。交付前渲染或以其他方式检查所有发生修改的工作表。

10. After successful output, always warn about possibly problematic rows. List the sheet, row, input bank name, written code or blank result, actual canonical or parent bank, and reason. Include every `parent_fallback`, `alias_review`, renamed bank, missing branch or region, stale source, conflict, and unresolved row even when a code was filled.

    成功输出后，必须提示所有可能有问题的行。逐项列出工作表、行号、原始开户行名称、已写入行号或空白结果、实际规范银行或上级行及原因。即使已成功填入行号，也要提示所有 `parent_fallback`、`alias_review`、银行改名、缺少支行或地区、来源过期、冲突和未解析记录。

## Registry Operations / 注册表操作

Initialize, inspect, or export the local registry:

初始化、检查或导出本地注册表：

```bash
python3 scripts/cnaps_registry.py init
python3 scripts/cnaps_registry.py stats
python3 scripts/cnaps_registry.py export --output cnaps-registry-export.csv
```

Use `--db /absolute/path/registry.sqlite3` before the subcommand for testing or a project-specific registry. Store only bank names, codes, aliases, evidence, dates, and audit events. Never add payment-account data.

测试或使用项目专属注册表时，在子命令前添加 `--db /absolute/path/registry.sqlite3`。注册表只保存银行名称、行号、别名、证据、日期和审计事件，禁止写入付款账号数据。

## Decision Rules / 决策规则

- Require a 12-digit CNAPS code. / 行号必须为12位CNAPS代码。
- Require an exact canonical-name match or an alias explicitly marked safe for auto-fill. / 必须是规范名称精确匹配，或明确标记为可安全自动填充的别名。
- Require two independent evidence origins for `verified` status, even when one source is official. / 即使其中一个来源是官方来源，`verified` 状态仍必须具备两个独立证据来源。
- Use the default hierarchy: exact verified outlet, nearest verified parent, verified regional parent, then verified national head office. Allow fallback only when the exact outlet has no usable dedicated code, bank identity and parent relationship are unique from the input or authoritative evidence, and the parent mapping is `auto_fill_ready`. Require province and city agreement for regional parents. Never cross banks. / 默认按“已核验精确网点—最近已核验上级行—已核验区域上级行—已核验全国总行”的顺序处理。只有精确网点没有可用专属行号、银行身份和上下级关系能由输入或权威证据唯一确定、且上级行映射为 `auto_fill_ready` 时才可兜底。区域上级行必须省市一致，绝不跨银行兜底。
- For an institution-only generic name such as `中国工商银行`, independently look up the unique verified head office, require `auto_fill_ready`, fill it as `parent_fallback`, and keep the broad input name out of the permanent auto-fill alias registry. / 对 `中国工商银行` 等只有机构名的宽泛输入，独立查询唯一且已核验的总行；结果必须为 `auto_fill_ready`，并以 `parent_fallback` 方式填写。不得把宽泛机构名永久注册为总行的自动填充别名。
- Never register a child outlet as an auto-fill alias of its fallback parent unless an official source or bank confirmation states that they share the code. Treat default fallback as a workbook decision, not a permanent mapping claim. / 除非官方来源或银行确认子网点与上级行共用同一行号，否则不得把子网点注册为兜底上级行的自动填充别名。默认兜底属于当前工作簿的处理决定，不代表永久映射关系。
- Prefer the nearest verified parent. Use a head-office code only when no nearer verified parent exists and the relationship is explicit. Record every fallback as `parent_fallback` in the workbook audit. / 优先使用最近的已核验上级行。只有不存在更近的已核验上级行且上下级关系明确时，才使用总行号。所有兜底都必须在工作簿审计中记录为 `parent_fallback`。
- If sources disagree, write no workbook value. Preserve all candidates in the audit and request manual confirmation. / 来源不一致时不得写入工作簿；在审计中保留全部候选项，并请求人工确认。
- Recheck mappings affected by bank mergers, renames, outlet closures, or sources older than the refresh window in the source policy. / 银行合并、改名、网点关闭，或证据来源超过刷新期限时，必须重新核验映射。
