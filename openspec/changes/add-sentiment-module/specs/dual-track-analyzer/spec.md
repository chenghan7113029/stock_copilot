## MODIFIED Requirements

### Requirement: DualTrackAnalyzer 新增离线分析方法
`DualTrackAnalyzer` SHALL 提供 `analyze_offline(code: str) -> DualTrackReport`，内部调用 `ValueAnalyzer.analyze_offline()`、`TechAnalyzer.analyze(code, offline=True)` 与 `SentimentAnalyzer.analyze_offline(code)`，不发起任何网络请求。`DualTrackReport` SHALL 新增 `sentiment_result: SentimentAnalysisResult | None` 字段。`analysis_summary` SHALL 总是包含情绪面段落：情绪面计算成功时输出三维联合解读文本（引用价值面评估、技术面趋势、情绪面等级），情绪面数据缺失时显式输出"情绪面数据缺失，本次报告仅基于价值+技术双维"，不得静默省略该段落。既有 `analyze()`（联网版）SHALL 同步新增 `sentiment_result` 计算，且不改变既有 `combined_signal`/`value_rating` 数值融合逻辑。

#### Scenario: 离线三维分析成功
- **WHEN** 本地已有 `600519` 的价值快照、K 线缓存与市场情绪快照，调用 `analyze_offline("600519")`
- **THEN** SHALL 返回 `DualTrackReport`，`sentiment_result` 非空，`analysis_summary` 包含情绪面联合解读段落，且过程不触发任何网络请求

#### Scenario: 情绪面数据缺失时的显式降级
- **WHEN** 本地无市场情绪快照，但价值面与技术面快照均存在
- **THEN** `sentiment_result` SHALL 为 `None`，`analysis_summary` SHALL 显式包含"情绪面数据缺失，本次报告仅基于价值+技术双维"文案，`combined_signal`/`value_rating` 计算 SHALL 不受影响

#### Scenario: 既有 combined_signal 数值融合逻辑不变
- **WHEN** 情绪面为极度贪婪或极度恐慌等任意等级
- **THEN** `SignalFusion.fuse()` 计算得出的 `combined_signal`/`value_rating` 数值 SHALL 与本 change 之前完全一致（回归测试覆盖），情绪面仅通过 `warnings`/`analysis_summary` 呈现，不参与数值融合公式
