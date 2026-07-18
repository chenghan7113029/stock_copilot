## ADDED Requirements

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

### Requirement: ConfrontationGenerator 生成 Level 1 互相反驳叙事
系统 SHALL 提供 `ConfrontationGenerator`，调用 `add-llm-narrative-core` 的 `narrate()`，输入为 `EvidenceBucketer` 的分桶结果，输出结构化 `{bull_report, bear_report, bull_rebuts_bear, bear_rebuts_bull, confidence}`。反驳内容 MUST 引用输入证据桶中的具体条目，MUST NOT 引入证据集合之外的新数字或新论点（由 `narrate()` 的 grounded 校验保证）。

#### Scenario: 正常生成双方报告与反驳
- **WHEN** `bull_evidence` 与 `bear_evidence` 均非空，`narrate()` 调用成功
- **THEN** `ConfrontationGenerator` SHALL 返回含 `bull_report`、`bear_report`、非空的 `bull_rebuts_bear`、`bear_rebuts_bull`

#### Scenario: narrate() 失败时降级
- **WHEN** `narrate()` 返回 `ok=False`（LLM 未配置、调用失败或 grounded 校验不过）
- **THEN** `ConfrontationGenerator` SHALL 返回降级结果，标注 `narrative_failed=True`，调用方 SHALL 展示 Level 0（纯证据列表）内容并附警告

### Requirement: ConfrontationRecord 持久化（预留用户声明字段）
系统 SHALL 提供 `ConfrontationRecord` DAO 模型与 Repo，持久化字段：`code`、`generated_at`、`bull_report`、`bear_report`、`rebuttals`（JSON）、`accepted_side`（nullable）、`reason_text`（nullable）。V1 SHALL 仅在生成 Level 1 报告后写入前 5 项，`accepted_side`/`reason_text` SHALL 保持 `NULL`，不要求任何调用方填写。

#### Scenario: Level 1 生成后落库
- **WHEN** `ConfrontationGenerator` 成功生成报告
- **THEN** SHALL 写入一条 `ConfrontationRecord`，`accepted_side` 与 `reason_text` 为 `NULL`

#### Scenario: 预留字段不阻塞写入
- **WHEN** 落库时未提供 `accepted_side`/`reason_text`
- **THEN** SHALL 正常写入成功，不因这两个字段缺失而报错
