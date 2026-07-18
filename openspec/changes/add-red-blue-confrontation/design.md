## Context

`DualTrackAnalyzer.analyze()` 已产出 `DualTrackReport`，内含丰富的、天然带立场的确定性证据（详见 proposal）。`add-llm-narrative-core`（本 change 的前置依赖）提供了通用的 `narrate()` 叙事生成能力。本 change 是两者的结合，落地 `product-overview.md` §6 的红蓝军对抗机制（Level 1：规则证据分桶 + LLM 互相反驳叙事）。

现有 CLI 设计原则（`add-cli-core` D-1）：「report 永不联网，要新数据必须先 sync」。红蓝对抗的叙事化环节需要联网调用 LLM，与该原则存在张力，本 design 需明确解决（见决策 3）。

另发现一个既有缺口：`DualTrackAnalyzer.analyze()` 内部调用的是联网版 `ValueAnalyzer.analyze()`，不是 `analyze_offline()`。若 `report dual` 要严格离线，必须先补齐 `DualTrackAnalyzer.analyze_offline()`。

## Goals / Non-Goals

**Goals:**
- 从 `DualTrackReport` 确定性地（零 LLM）分桶出多空证据
- 某一方证据不足时有兜底规则（列出对方假设脆弱性），保证对抗内容不空
- 基于 `narrate()` 生成 Level 1 互相反驳叙事，反驳内容锚定已有证据
- 新增 `report dual` CLI 入口，默认离线（Level 0），`--narrate` 显式联网增强（Level 1）
- 为未来 Web 层的"用户声明拒绝哪方及理由"预留持久化字段（不实现交互本身）

**Non-Goals:**
- 不实现真正多轮对话式攻防（Level 2）
- 不实现用户声明/复盘归因的交互界面（依赖未来 Web 层，`add-red-blue-confrontation` 仅建表留空）
- 不修改 `SignalFusion` 或 `combined_signal` 的既有融合逻辑
- 不改变 `DualTrackAnalyzer.analyze()`（联网版）的既有行为，只新增 `analyze_offline()`

## Decisions

### 决策 1：证据分桶规则——直接复用既有确定性字段，不新增判断逻辑

**选择**：`EvidenceBucketer` 按以下规则分类，均为读取已有字段，不重新计算：

| 证据来源 | 分桶规则 |
|---|---|
| `value_result.method_results[k].assessment` 含"低估"/正向关键词 | → bull |
| `value_result.method_results[k].assessment` 含"高估"/负向关键词，或 `value_trap` overall_risk ∈ {Medium, High} | → bear |
| `value_result.warnings` | 含"风险"/"不可信"/"Limited" → bear；其余不采信（避免噪音） |
| `tech_result.signal_reasons` | → bull（该字段本身就是"支持买入"的理由） |
| `tech_result.risk_factors` | → bear（该字段本身就是"风险提示"） |

**理由**：`agent-engineering-quality.md` 强调"能用代码做的不要给 LLM"；这些字段的正负极性在产出时已经确定（如 `risk_factors` 命名本身就是负面），用规则分类零幻觉风险、可单测。

**备选方案**：让 LLM 直接读原始 `DualTrackReport` 自行判断哪些是利好哪些是利空 —— 拒绝，这是让 LLM 做"代码能做的事"（分类打标签），且判断本身会影响后续叙事的事实基础，一旦分类错误整个对抗内容的立场都会错，风险不可控。

### 决策 2：兜底规则的触发阈值与内容来源

**选择**：任一方证据数 `< 2` 时，触发兜底，追加以下内容（仍是规则生成，零 LLM）：
- 价值面：读取 `prototype` 对应方法论的已知局限（如 `value_growth` 原型的 DCF 依赖 growth_rate 假设、bank 原型排除 DCF 的原因）
- 技术面：若 `trend_status` 单边强势，追加"该状态可能钝化/趋势反转历史概率"的通用提示（非个股数据，是方法论层面的通用免责提示）

**理由**：保证对抗双方"有话可说"而不是留空，同时不编造具体数值（兜底内容是方法论局限性的通用陈述，不是对该股票的具体断言）。

**备选方案**：证据不足时不生成对抗内容，直接提示"证据不足无法对抗" —— 拒绝，这会导致强多头/强空头个股永远拿不到红蓝对抗报告，产品价值打折；兜底方案更符合"对抗确认偏差"的初衷（即使技术面很强，仍提醒方法论局限）。

### 决策 3：offline/online 边界——Level 0 默认离线，Level 1 显式联网

**选择**：
- `report dual <code>`（不加 flag）：内部仅调用 `DualTrackAnalyzer.analyze_offline()` + `EvidenceBucketer` + 兜底规则，全程不触网，输出证据分桶列表
- `report dual <code> --narrate`：额外调用 `ConfrontationGenerator`（内部用 `narrate()`），此步骤联网；CLI 帮助文本与运行时输出 SHALL 明确提示"此步骤将联网调用 LLM"
- `--narrate` 调用失败（LLM 未配置/调用失败/grounded 校验不过）时，SHALL 降级为 Level 0 输出并打印 warning，不中断整个命令

**理由**：维持现有"report 默认离线"的心智模型不被悄悄打破；"联网"作为显式、可选、可降级的增强步骤，用户始终可以拿到确定性的 Level 0 结果作为兜底。

**备选方案**：
- 方案 A（红蓝对抗单独成一类命令）——拒绝，会让 CLI 命令集变得碎片化，且 Level 0/Level 1 共享同一套证据分桶逻辑，拆两个命令会有代码重复
- 方案 C（缓存尽量维持 offline 语义）——已通过 `add-llm-narrative-core` 的幂等缓存部分实现（重复调用不重复联网），但首次调用仍需联网，因此 `--narrate` 的"显式"语义依然保留

### 决策 4：Level 1 互相反驳的 Prompt/Schema 设计

**选择**：单次 `narrate()` 调用，`evidence` 同时包含 `bull_evidence[]` 和 `bear_evidence[]`（含兜底内容），`schema` 要求输出：

```json
{
  "bull_report": "string，看多方基于 bull_evidence 的论述",
  "bear_report": "string，看空方基于 bear_evidence 的论述",
  "bull_rebuts_bear": ["string，看多方针对 bear_evidence 中某条的反驳"],
  "bear_rebuts_bull": ["string，看空方针对 bull_evidence 中某条的反驳"],
  "confidence": 0.0
}
```

Prompt instruction 明确要求：反驳内容必须引用对方证据列表中的具体条目（可要求输出时带 evidence 索引，便于人工核对来源），不得引入证据集合之外的新论点或新数字。

**理由**：单次调用输出双方内容，既能体现"互相攻击"的产品效果，又避免了多轮对话/多次 API 调用的成本与状态管理复杂度（对齐用户确认的"Level 1：单次调用同时生成双方并互相引用反驳"）。

## Risks / Trade-offs

- **[风险] 证据分桶的关键词匹配（"低估"/"高估"等）脆弱，未来估值方法输出文案变化会导致分类失效** → **缓解**：优先用已有结构化字段（如 `value_trap.overall_risk` 枚举值、`ValueRating` 枚举）而非自由文本关键词匹配；仅在缺乏结构化字段时才 fallback 到关键词匹配，且单测覆盖具体文案。
- **[风险] `DualTrackAnalyzer.analyze_offline()` 是新增方法，需要与联网版保持字段行为一致** → **缓解**：复用 `ValueAnalyzer.analyze_offline()` 与 `TechAnalyzer.analyze(offline=True)` 已验证的既有离线路径，`DualTrackAnalyzer` 层只做编排，不重新实现离线逻辑。
- **[风险] Level 1 反驳内容即使锚定证据，仍可能因为"选择性引用"造成误导性叙事**（如只反驳对方最弱的一条） → **缓解**：V1 接受此局限并在报告末尾固定输出免责声明"叙事由 AI 生成，仅供参考，请对照下方原始证据列表核实"；不做更复杂的"反驳质量"校验（避免过度工程化）。
- **[风险] `ConfrontationRecord` 表的 `accepted_side`/`reason_text` 长期留空，若后续 Web 层设计变化，字段可能需要调整** → **缓解**：V1 明确这两个字段是"预留"，不做迁移保证；后续 change 如需调整可直接 ALTER，不视为破坏性变更（无消费方依赖这两个字段的当前 schema）。

## Migration Plan

- 新增 `ConfrontationRecord` 表，走现有 `ensure_sqlite_schema()` 补丁模式（同 `prior_*`/`industry` 字段的接入方式）
- `DualTrackAnalyzer.analyze_offline()` 为新增方法，不影响现有 `analyze()` 调用方（`analyze()` 本身零改动）
- 回滚：删除新增文件 + `ConfrontationRecord` 表即可，不影响双轨分析、CLI 现有命令

## Open Questions

- 兜底规则的"方法论局限性通用提示"文案库，V1 先硬编码在 `EvidenceBucketer` 内（按 prototype 分支），未来若需要更细粒度（如按具体估值方法）可再拆分，本 change 不预先设计扩展点。
