## Why

`product-overview.md` §8.2 验收准则「关键决策（Checklist 填写、用户拒绝红蓝哪方）可持久化备查」仍未勾选。PO-03 V1（Skill）只交付叙事，**无用户立场落库**；PO-04 Checklist 与 PO-09 复盘之间缺少「当时如何解读多空证据」的结构化审计记录。

Explore 结论（Owner 确认）：主路径为 CLI + API；**不做编排命令**；用户 declare 须为 **结构化 JSON Schema**，且 **必须引用 evidence 序号**（与 `report dual` / `report confront` 的 1-based 索引对齐）。

## What Changes

- 扩展 `ConfrontationRecord`：增加 declare 字段（`stance`、`adopted_side`、`rejected_side`、`adopted_evidence_refs`、`rejected_evidence_refs`、`rejection_rationale`、`residual_uncertainty`、`confidence` 等）
- 新增 `ConfrontationDeclarationValidator`（纯规则，零 LLM）：校验 evidence ref 范围、非空 rationale 须含 `[n]` 引用、禁止交易指令枚举
- 新增 CLI `confront declare <confrontation_id>`：交互式或 `--json-file` 提交结构化声明；校验失败硬拒绝且不覆盖已有合规 declare
- **关联 ID（命令仍分散）**：
  - `checklist submit <code> --confrontation-id <id>`（可选软链）
  - `trade record ... --confrontation-id <id>`（可选软链）
- 新增 `confront show <code>`：列出 confrontation + declare 历史

**不包含：**
- LLM 生成 declare 内容（用户输入 + 确定性校验）
- 强制「必须先 confront 再 checklist」硬门控（仅 CLI 提示）
- Web UI

## Capabilities

### New Capabilities
- `confrontation-declaration`：declare Schema、确定性 ref 校验、`ConfrontationDeclarationValidator`
- `cli-confront-declare`：`confront declare` / `confront show` 子命令

### Modified Capabilities
- `cli-checklist-submit`：可选 `--confrontation-id`
- `trade-record`：可选 `--confrontation-id`；`TradeRecord` 外键字段
- `trade-review-attribution`：Badcase 报告可展示关联 declare 摘要（只读，不阻塞）

## Impact

- **修改**：`src/dao/models.py`（`ConfrontationRecord` declare 列或 JSON 列）、`checklist_repo` / `trade record` CLI
- **依赖**：`add-confrontation-narrate-api`（`confrontation_id` 与 evidence 快照来源）
- **文档**：勾选 product-overview §8.2 declare 项；更新 PO-03 / PO-09 说明
