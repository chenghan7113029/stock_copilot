## Context

依赖 `add-confrontation-narrate-api` 产出的 `confrontation_id` 与 `evidence_json`。Checklist（PO-04）、TradeRecord（PO-09）已存在，缺 confrontation 关联与 declare 校验。

Owner 约束：**命令分散**；declare **结构化 + 必须引用 evidence 序号**；**不**自动替用户生成 declare。

## Goals / Non-Goals

**Goals:**
- JSON Schema + 确定性 validator
- `confront declare` CLI（交互 + `--json-file`）
- `--confrontation-id` 软链 checklist / trade record
- `confront show` 历史查询

**Non-Goals:**
- 编排式 audit 命令
- LLM 填写 declare
- 强制 confront 先于 checklist

## Decisions

### D1：Declare Schema（V1）

```json
{
  "stance": "adopt_bull | adopt_bear | partial | abstain",
  "adopted_side": "bull | bear | none",
  "rejected_side": "bull | bear | none",
  "adopted_evidence_refs": {"bull": [1], "bear": []},
  "rejected_evidence_refs": {"bull": [], "bear": [2, 3]},
  "rejection_rationale": "拒绝空方[2]：...；部分采纳多方[1]：...",
  "residual_uncertainty": "可选，自由文本",
  "confidence": 0.65
}
```

### D2：确定性校验规则

1. `confrontation_id` 存在且 `evidence_json` 可解析
2. 所有 ref 整数 ∈ `[1, len(side_evidence)]`
3. 若 `rejected_evidence_refs` 任一非空 → `rejection_rationale` 非空且匹配 `\[(?:bull|bear)?\[?\d+\]?|\d+\]` 或统一要求含 `[n]` 模式（实现时选用一种并单测）
4. `stance` 枚举外拒绝；禁止字段 `order`/`signal`/`action_buy`
5. `confidence` ∈ [0, 1]
6. 同一 `confrontation_id` 仅允许 **一条** `declare_status=ok`（后续 declare 覆盖需 `--force`，V1 可禁止覆盖）

### D3：关联 ID

- `ChecklistRecord.confrontation_id` nullable FK
- `TradeRecord.confrontation_id` nullable FK
- CLI 仅传参写入，**不** cascade 校验 confront 与 checklist 同 code（警告即可）

### D4：表结构扩展

在 `confrontation_records` 增加：

| 字段 | 说明 |
|------|------|
| declare_json | 用户声明 |
| declare_status | ok / invalid |
| declared_at | |

## Risks

- Rationale 引用 regex 过严/过松 → 单测覆盖边界
- 用户不跑 declare 仍可用 Checklist → 接受；复盘降级显式提示

## Open Questions

- `stance=partial` 是否要求 adopted 与 rejected 两侧 refs 均非空（建议 yes）
