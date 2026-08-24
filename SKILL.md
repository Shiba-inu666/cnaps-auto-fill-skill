---
name: cnaps-auto-fill
description: Codex 专用的中国银行开户行行号补全与核对技能。用于在 Excel、CSV 或 TSV 中依据“开户行”填写空白行号，并自动核对已有行号是否正确；定位列后只读取开户行和行号两列，不访问其他业务数据。
---

# 开户行行号自动填充（Codex 专用）

## 数据访问边界

- 使用 Codex 的 `spreadsheets:Spreadsheets` 技能处理工作簿。
- 每张表只扫描表头来定位“开户行”和“行号”两列。定位成功后，只读取这两列的数据单元格；不得读取、解析、导出或缓存其他列。
- 不从姓名、账号、证件号、手机号、金额、省市等其他列补充上下文，也不得把它们用于联网查询。
- 只修改行号列。保留其他单元格、公式、格式、筛选、隐藏状态和工作表结构。

处理表格前阅读 [references/workbook-workflow.md](references/workbook-workflow.md)。

## 快速流程

1. 在各工作表的表头中识别两列。识别完成后立即停止访问其他列。
2. 读取行号列及对应的开户行名称：空白行号进入补全流程，已有行号进入核对流程。
3. 对需要补全或核对的开户行名称去重，批量查询本地注册库：

   ```bash
   python3 scripts/cnaps_registry.py lookup --name '开户行一' --name '开户行二'
   ```

4. 仅当结果为 `auto_fill_ready` 且 `autofill_code` 是 12 位数字时处理：空白单元格直接填写；已有行号与核验值一致则记为正确，不一致则记为错误但不自动覆盖。
5. 对未命中的不同开户行名称各检索一次。按 [references/source-policy.md](references/source-policy.md) 核验后写入注册库并重新查询。联网搜索词只能包含开户行名称和“联行号／人行行号”等关键词。
6. 没有专属支行号时，只有银行身份及上下级关系能从开户行名称或公开来源唯一确定，且上级行本身为 `auto_fill_ready`，才可使用最近上级行或总行号，并标记 `parent_fallback`；否则留空。
7. 已有值不是 12 位纯数字时标记为格式错误。证据不足时标记为无法确认，不猜测对错。
8. 行号按文本写入。除非用户明确要求自动更正，否则已有值即使错误也不覆盖。默认另存新文件；完成后只复查开户行和行号两列，不渲染或检查整张表。

## 本地注册库

默认数据库为 `~/.codex/state/cnaps-auto-fill/registry.sqlite3`，空库会自动导入 `assets/seed-registry.jsonl`。用户可用 `CNAPS_REGISTRY_PATH` 或 `--db` 指定其他位置。

```bash
python3 scripts/cnaps_registry.py init
python3 scripts/cnaps_registry.py stats
python3 scripts/cnaps_registry.py verify \
  --name '完整规范开户行名称' --code 123456789012 \
  --source 'official=https://官方来源.example/record' \
  --source 'directory=https://独立来源.example/record'
```

注册库只保存开户行名称、行号、别名、来源和核验日期，不保存工作簿其他数据。

## 填写规则

- 行号必须是 12 位纯数字。
- 已有行号必须自动核对格式，并在取得已核验映射后核对是否与开户行匹配。
- 自动填写仅限规范名称精确匹配或明确允许自动填写的安全别名。
- 新映射需要两个相互独立且实际打开的来源；来源冲突时不填。
- 不根据账号、卡 BIN 或相似名称推测行号，不跨银行兜底。
- 不把下级网点永久登记为上级行的安全别名，除非官方明确说明共用行号。

## 交付

回复保持简短：提供输出文件，以及补全、核对正确、格式错误、不一致、无法确认和留空的数量。问题项只列工作表、行号、开户行、现有值、核验值及原因；除非用户要求，不新增完整审计表。
