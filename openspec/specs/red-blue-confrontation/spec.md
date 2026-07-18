# red-blue-confrontation Specification

## Purpose
红蓝对抗 Level 0：从 DualTrackReport 确定性分桶多空证据，并在证据不足时追加方法论假设脆弱性兜底。

## Requirements

### Requirement: EvidenceBucketer 从 DualTrackReport 分桶多空证据
系统 SHALL 提供 `EvidenceBucketer`，输入 `DualTrackReport`，输出 `{bull_evidence: list[str], bear_evidence: list[str]}`。分类规则 SHALL 优先使用已有结构化字段（`value_trap.overall_risk`、`ValueRating` 枚举等），缺乏结构化字段时才 fallback 到 assessment/warnings 文本关键词匹配。分桶过程 MUST NOT 调用 LLM。

#### Scenario: 低估 + 技术面多头信号归入 bull
- **WHEN** `value_result` 的 `ValueRating = UNDERVALUED`，`tech_result.signal_reasons = ["MA5 上穿 MA20"]`
- **THEN** `bull_evidence` SHALL 包含低估相关条目与技术面信号原因

#### Scenario: value_trap 高风险归入 bear
- **WHEN** `value_result.method_results["value_trap"].details["overall_risk"] = "High"`
- **THEN** `bear_evidence` SHALL 包含该 value_trap 高风险条目

#### Scenario: risk_factors 归入 bear
- **WHEN** `tech_result.risk_factors = ["RSI 超买"]`
- **THEN** `bear_evidence` SHALL 包含该风险提示

### Requirement: 证据不足时的兜底假设脆弱性规则
当 `bull_evidence` 或 `bear_evidence` 任一方条数少于 2 时，`EvidenceBucketer` SHALL 追加对方的「核心假设脆弱性」条目（基于 `prototype` 的方法论已知局限，如 growth_rate 假设依赖、原型方法排除项），且追加内容 MUST 为方法论层面的通用陈述，MUST NOT 编造针对该股票的具体数值断言。

#### Scenario: 强多头个股的 bear_evidence 触发兜底
- **WHEN** `bear_evidence` 分桶结果为空（技术面纯多头、价值面无 value_trap 风险）
- **THEN** SHALL 追加该原型对应估值方法的假设局限性条目到 `bear_evidence`，使其非空

#### Scenario: 兜底内容不含具体数值断言
- **WHEN** 兜底规则被触发
- **THEN** 追加的条目 SHALL 仅描述方法论/假设的通用局限，不得包含针对该股票的具体数字（如"预测未来 3 年增长 20%"这类断言）
