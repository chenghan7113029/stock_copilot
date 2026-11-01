## ADDED Requirements

### Requirement: DualTrackReport 新增龙虎榜结果字段与编排
`DualTrackReport` SHALL 新增可选字段 `top_list_result: TopListResult | None`（默认 `None`）。`DualTrackAnalyzer.analyze()` SHALL 在既有价值/技术/情绪/资金面/事件面之后追加龙虎榜分析；`analyze_offline()` SHALL 调用 `TopListAnalyzer.analyze_offline()`，无缓存时置 `None` 并追加「龙虎榜无本地缓存，请先运行 sync」warning。龙虎榜分析异常 MUST NOT 中断整体双轨分析，MUST NOT 改变 `combined_signal`/`value_rating`。

#### Scenario: 联网分析填入字段
- **WHEN** 调用 `analyze("600519")` 且龙虎榜可获取
- **THEN** 返回报告的 `top_list_result` SHALL 非空

#### Scenario: 离线分析无缓存时降级
- **WHEN** 调用 `analyze_offline("600519")` 且无龙虎榜缓存
- **THEN** `top_list_result` SHALL 为 `None`，`warnings` SHALL 含「龙虎榜无本地缓存，请先运行 sync」，且 `combined_signal` 与不含龙虎榜时一致

#### Scenario: 龙虎榜分析抛错不影响双轨
- **WHEN** 龙虎榜分析内部抛出异常
- **THEN** `value_result`/`tech_result`/`combined_signal` SHALL 正常返回，`warnings` SHALL 记「龙虎榜分析失败: <原因>」
