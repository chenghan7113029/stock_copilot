## Context

- Level 0 已交付：`EvidenceBucketer`、`report dual`、`analyze_offline()`（`add-red-blue-confrontation`）
- LLM 管道已交付：`narrate()`、`check_grounded()`、`LLMNarrateCache`（`add-llm-narrative-core` / PO-02）
- 产品方向变更：主路径 **CLI + API**；Skill 降为 fallback
- 约束：`report` 命令 Level 0 **严格离线**；`--narrate` **仅调用 LLM**，不触发 sync / 新行情拉取

## Goals / Non-Goals

**Goals:**
- 稳定 1-based evidence 序号，bull/bear 分列表独立编号
- `report confront --narrate` 产出 grounded 互驳 JSON 并持久化 `ConfrontationRecord`
- narrate 失败时保留 Level 0 输出 + 明确降级文案
- 与 `add-confrontation-declaration` 共享 `confrontation_id`

**Non-Goals:**
- 用户 declare、persona、Checklist 关联（后续 change）
- 修改证据分桶规则（除非为序号化必须）

## Decisions

### D1：Evidence 序号规则

**选择**：JSON 输出形态：

```json
{
  "bull_evidence": [{"index": 1, "text": "..."}, ...],
  "bear_evidence": [{"index": 1, "text": "..."}, ...]
}
```

bull/bear **各自**从 1 编号；declare 引用写 `bull:[1,2]` / `bear:[3]` 或分字段（declaration change 定稿）。

**理由**：避免合并列表后序号漂移；与 Skill 版 `[n]` 人类可读格式兼容（formatter 文本模式可渲染为 `1. ...`）。

### D2：`report confront` vs 扩展 `report dual`

**选择**：新增 `report confront` 子命令；`report dual` 仅同步 JSON 序号契约，**不**默认 narrate。

**理由**：保持 `dual` 纯离线语义（D-1）；narrate 是显式 opt-in。

### D3：Narrate Schema（Level 1）

**选择**：`narrate()` 输出 JSON：

- `bull_thesis` / `bear_thesis`（字符串，须 grounded）
- `bull_rebuttals[]` / `bear_rebuttals[]`：`{target_side, target_index, text}`
- `disclaimer`（固定文案）

**理由**：可机器校验 rebuttal 是否指向合法 index；便于 declare 阶段要求用户回应具体条目。

### D4：Grounded 策略

**选择**：复用 `check_grounded(evidence, narrative_text)`；失败则 schema 重试（与 PO-02 相同 `_SCHEMA_RETRIES`），仍失败则 **不写入 narrative**，`ConfrontationRecord.narrate_status=failed`。

### D5：持久化

**选择**：新增 `confrontation_records` 表，字段（V1 最小集）：

| 字段 | 说明 |
|------|------|
| id | PK |
| code | 股票 |
| evidence_json | numbered buckets + dual summary |
| narrative_json | narrate 结果，可 null |
| narrate_status | ok / skipped / failed |
| created_at | |

declare / persona 字段由 sibling changes 扩展或关联表追加。

## Risks / Trade-offs

- **LLM 成本**：每次 confront narrate 多轮 token → 缓存键含 evidence hash + model id
- **Grounded 误杀**：过严导致频繁 failed → 日志记录 + 用户可见「请仅使用 Level 0」
- **与 Skill 双轨**：文档明确 API 为产品路径，Skill 不保证 schema 一致

## Open Questions

- 是否在 `report confront --narrate` 成功后将 markdown 写入 `reports/<code>_confrontation.md`（默认 yes，与 Skill 路径对齐）
