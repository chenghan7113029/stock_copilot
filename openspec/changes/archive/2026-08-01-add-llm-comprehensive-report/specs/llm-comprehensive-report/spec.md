## ADDED Requirements

### Requirement: DualTrackReport 确定性证据打包
系统 SHALL 提供 `build_dual_track_evidence(report: DualTrackReport) -> dict`，仅打包价值面（`fair_value_range`/`margin_of_safety`/`price_percentile`/`assessment`/`confidence`/`prototype`）与技术面（`trend_status`/`signal_score`/`buy_signal`/`signal_reasons`/`risk_factors`）及融合结果（`combined_signal`/`value_rating`）字段，SHALL NOT 包含 `warnings` 自由文本字段，SHALL NOT 对数值做任何再加工/再计算。

#### Scenario: 价值面与技术面均存在
- **WHEN** 传入的 `DualTrackReport` 含非空 `value_result` 与 `tech_result`
- **THEN** 返回 dict SHALL 同时包含价值面与技术面对应分区字段

#### Scenario: 某一分析结果为 None
- **WHEN** `DualTrackReport.value_result` 为 `None`（如本地无快照）
- **THEN** 返回 dict SHALL NOT 包含价值面分区字段，SHALL NOT 抛异常

### Requirement: 综合报告叙事生成
系统 SHALL 提供 `narrate_comprehensive_report(report: DualTrackReport, config=None) -> NarrateResult`，内部调用 `common.llm.narrate(evidence, schema, instruction)`，schema SHALL 要求 `summary`（string）、`key_points`（array of string）、`risks`（array of string）、`confidence`（0-1 float）字段；instruction SHALL 显式声明「不得引入 evidence 之外的新数字/新结论」。

#### Scenario: 正常生成
- **WHEN** evidence 非空且 LLM 配置齐全，`narrate()` 返回 `ok=True`
- **THEN** `narrate_comprehensive_report()` SHALL 返回含 `summary`/`key_points`/`risks` 的 `NarrateResult`

#### Scenario: LLM 未配置
- **WHEN** 未配置 `llm:` 段且无 `LLM_API_KEY` 环境变量
- **THEN** SHALL 返回 `ok=False`，`error` 含「LLM 未配置」，SHALL NOT 抛未捕获异常

#### Scenario: grounded 校验失败
- **WHEN** LLM 输出含 evidence 之外的数值，重试耗尽仍失败
- **THEN** SHALL 返回 `ok=False`，`grounded=False`，调用方 SHALL 能据此降级为确定性摘要展示
