## Context

`src/service/value/valuation/value_trap.py` 的 `ValueTrapDetector` 已实现五维度价值陷阱检测（财务健康、业务恶化、护城河侵蚀、AI/技术脆弱性占位、股息可持续性），通过 `_overall_risk()` 加权多数决输出 `overall_risk ∈ {Low, Medium, High, Limited}`（`High` 判定规则：≥2 维度为 High，或 1 维度 High + ≥2 维度 Medium 时归为 Medium——详见现有 `_overall_risk()` 实现，本 change 不改动该判定逻辑本身）。

`src/service/value/aggregator.py` 的 `ValuationAggregator` 当前把 `value_trap` 归入 `SCORE_METHOD_KEYS`（评分类，不参与区间聚合），通过 `_score_summary()` 生成一行摘要（如 `"Value Trap Detector: risk=High, High Value Trap Risk"`），`append` 进 `warnings` 列表。`warnings` 列表里还混杂 IQR 异常值说明、核心方法全 N/A 的「不可信」警告等，视觉权重相同。

`src/service/value/analyzer.py` 的 `ValueAnalyzer._analyze_stock()` 把 `agg.warnings` 原样追加到 `ValueAnalysisResult.warnings`，再由 `src/apps/formatters.py` 的 `format_value_report()` 在报告末尾统一渲染 `--- 警告 ---` 区块。

下游消费方核查（决定本 change 的安全边界）：
- `src/service/dual_track/signal_fusion.py::derive_value_rating(mos, config)` 仅读取 `margin_of_safety` 浮点数计算 `ValueRating`，**不读取** `ValueAnalysisResult.assessment` 文本或 `confidence` 字段。
- `src/service/dual_track/evidence_bucketer.py::_bucket_method()` 对 `value_trap` 已经优先读取结构化字段 `result.details["overall_risk"]`（`High`/`Medium` → bear，`Low` → bull），**不使用**关键词匹配 `ValueAnalysisResult.assessment` 顶层文本；`_bucket_value()` 对 `value_result.warnings` 的处理是关键词匹配（`_WARNING_BEAR_KEYWORDS`），但只做「归入 bear」的判断，不解析具体结构。

结论：`assessment` 顶层字段与 `warnings` 列表的现有消费方均不依赖具体文案的稳定格式（`assessment` 完全不被读取；`warnings` 只做关键词存在性判断），只要新增内容不违反这两条隐含契约，改动风险可控。

## Goals / Non-Goals

**Goals:**
- High 风险时提供独立于 `warnings` 列表的醒目提示（`value_trap_alert` 字段），CLI 报告头部强制渲染
- High 风险时对 `confidence` 做确定性降级，避免"数值区间显示低估 + confidence=High"这种误导性组合
- 保持改动范围局限在 Aggregator/Analyzer/Formatter 三层，不改动 `ValueTrapDetector` 本身的五维度判定算法
- 不引入对下游（红蓝对抗证据分桶）的破坏性影响，并在设计中给出核查结论（见 Context）

**Non-Goals:**
- 不重新设计 `overall_risk` 的加权多数决算法（`_overall_risk()`）
- 不引入"价值陷阱警示"复合 `assessment` 状态（如 `"低估（价值陷阱警示）"`），不改变 `ValueRating`/`assessment` 既有取值集合的语义边界
- 不对 Medium/Low 风险做专项提示（本 change 聚焦 High，Medium/Low 沿用现有 `_score_summary()` warnings 摘要）
- 不重新设计整个 `ValuationAggregator` 的 warnings/confidence 体系（T-1 原型差异化 MOS 阈值等留给其他 change）
- 不修改 `EvidenceBucketer` 代码（核查确认无需联动，见 Context 与决策 1）

## Decisions

### 决策 1：不修改 `assessment` 语义，新增独立 `value_trap_alert` 字段（拒绝复合状态方案）

**选择**：`value_trap` High 时，`ValueAnalysisResult.assessment` 继续保持纯 MOS 驱动的既有取值（低估/合理偏低/合理/合理偏高/高估），不叠加"价值陷阱"信息；新增正交字段 `value_trap_alert: str | None`，只在 High 时非空，供报告层单独渲染醒目区块。

**理由**：
1. 保持 `assessment` 单一语义（"当前价相对估值区间的位置"），避免一个字段承载两种不同维度的判断（估值定位 vs 风险等级），减少未来维护复杂度。
2. Context 核查确认 `assessment` 无任何下游代码消费方依赖具体文案，改字段值本身不是技术障碍——但**语义清晰度**才是拒绝复合状态的核心理由：即使技术上安全，"低估（价值陷阱警示）"这种字符串拼接会让后续任何新增消费方（如未来的 Web 前端、LLM ContextPack）都需要额外解析逗号/括号里的次要信息，而结构化的独立字段不需要解析。
3 `VA-OUT` 系列需求（MRD §6.2）明确"安全边际阈值可按原型差异化"，隐含 `assessment` 应保持单一、可预测的分类函数（`_assessment_from_mos()`），不应因风险维度的检测结果而改变分类边界。

**备选方案（拒绝）**：
- **方案 B：`assessment` 引入复合状态**（如 High 风险时强制输出"价值陷阱警示"而非"低估"，或在文本后缀"⚠"）—— 拒绝。理由：(1) 会立即造成 `assessment` 取值集合从 5 个固定值扩展为组合状态，任何未来直接判等 `assessment == "低估"` 的代码都会静默失效（当前无此类消费方，但无法保证未来没有）；(2) 属于"膨胀成重新设计整个 aggregator"的范围蔓延，用户明确要求本 change 保持小而聚焦。
- **方案 C：High 时直接阻断/清空 `fair_value_range`**（不返回估值区间，只返回警示）—— 拒绝。理由：五维度风险检测与估值区间计算是两个独立维度（一只股票可以估值便宜但同时有财务健康风险），阻断区间会丢失有效信息，且与 MRD §6.1 "所有数值来自确定性计算，不得阻断"的精神冲突；风险提示应该是"叠加"而不是"替代"估值结论。

### 决策 2：confidence 一级降级，而非固定覆盖为某个值

**选择**：在现有 `confidence` 计算完成后（`_confidence(filtered)` + 核心方法全 N/A 检测），若 `value_trap` High，再执行一次降级：`High→Medium`、`Medium→Low`、`Low` 与 `不可信` 保持不变（已经是最低/特殊状态，无法进一步降级）。

**理由**：一级降级是相对操作，不覆盖既有的"有效方法数 + 离散度"评估结果，两套逻辑正交叠加，实现简单（一个映射表 + 一次条件判断），且符合"专项提示增强，不重新设计"的范围要求。

**备选方案（拒绝）**：
- 固定覆盖为 `"Low"`——拒绝，会掩盖"3 个方法一致性很高但公司有价值陷阱风险"与"数据严重不足"这两种本质不同的低置信度来源，降低诊断价值。

### 决策 3：`value_trap_alert` 文案内容与生成位置

**选择**：在 `ValuationAggregator.aggregate()` 内部，High 判定后生成结构化文案，格式：

```text
🚨 疑似价值陷阱（High Risk）：{列出 overall_risk 贡献的 High 维度中文名, 逗号分隔}。
估值区间/安全边际仅反映价格与账面/现金流的相对关系，不代表基本面已改善，决策前建议核对上述维度的最新变化。
```

维度中文名从 `value_trap` 结果的 `details` 字段（`financial_health`/`business_deterioration`/`moat_erosion`/`ai_vulnerability`/`dividend_sustainability`，逐一判断是否为 `"High"`）拼接，不重新计算，直接读取 `ValueTrapDetector` 已产出的结构化 `details`。

**理由**：生成逻辑放在 Aggregator（而不是 Analyzer 或 Formatter）是因为 Aggregator 已经是"消费 `method_results` 并产出 `AggregateResult`"的既有职责边界，`value_trap` 结果本身也在 `aggregate()` 的入参 `results` 中，无需额外传参；Formatter 只负责渲染，不做业务判断，符合三层分工。

**备选方案（拒绝）**：
- 在 Formatter 层判断 High 并生成文案——拒绝，Formatter 当前是纯展示层（`src/apps/formatters.py` 头部注释职责即为"格式化"），把风险判断逻辑放进展示层会导致未来 API/Web 层需要重复实现同样的判断，违反"确定性计算在 service 层"的分层约定（`docs/dev/engineering-conventions.md` §4.2）。

## Risks / Trade-offs

- **[风险] `value_trap_alert` 文案格式变化可能影响未来新增的消费方**（如未来 LLM ContextPack 若直接拼接该字符串）→ **缓解**：本 change 的文案生成逻辑集中在 Aggregator 一处（`_value_trap_alert_message()` 私有方法），未来若需要结构化（如拆分为 `{level, dimensions: list[str], message: str}`）可在不破坏现有字符串字段的前提下新增字段，不必立即过度设计。
- **[风险] confidence 一级降级可能与未来 T-1（安全边际阈值原型差异化）的置信度调整逻辑产生叠加顺序歧义** → **缓解**：本 change 将降级步骤放在现有 confidence 计算的**最后一步**（在"核心方法全 N/A → 不可信"判断之后），未来 T-1 若引入新的置信度调整，应遵循"先原有规则，后专项调整，按变更引入顺序叠加"的约定，在对应 change 的 design.md 中说明叠加顺序。
- **[风险] `Limited` 维度过多时 `overall_risk` 本身可能被判定为 `"Limited"` 而非 High/Medium/Low，本 change 的专项提示不会触发** → **接受**：这是 `ValueTrapDetector` 既有行为（`_overall_risk()` 中 `counted` 为空时返回 `"Limited"`），`Limited` 场景下警示的价值本来就低（数据不足以判断风险），维持现状，超出本 change 范围。

## Migration Plan

- 无数据库变更（`value_trap_alert` 是 dataclass 新字段，不落库；`AggregateResult`/`ValueAnalysisResult` 均为运行时 dataclass，非持久化模型）
- 新增字段均带默认值 `None`，现有构造 `ValueAnalysisResult(...)`（如测试 fixture）不传该字段时行为不变，向后兼容
- CLI `--json` 输出新增一个字段（`value_trap_alert`），JSON 消费方（当前仅红蓝对抗 Skill 读取 `bull_evidence`/`bear_evidence`，不读取原始 `ValueAnalysisResult` JSON）不受影响
- 回滚：删除 `value_trap_alert` 相关代码即可，不影响其他字段与既有测试

## Open Questions

- Medium 风险是否也需要一个轻量提示（如不强制展示区块，但在 warnings 里加前缀标记）？本 change 判断范围应聚焦 High（roadmap T-2 原文只提到 High），Medium 维持现状；若未来需要，建议作为独立小 change 处理，不在本 change 内顺带实现。
- `value_trap_alert` 是否应该支持多语言/可配置文案模板？V1 硬编码中文文案（与 `_PROTOTYPE_VULNERABILITIES` 等既有硬编码字典风格一致），本 change 不预先设计模板引擎。
