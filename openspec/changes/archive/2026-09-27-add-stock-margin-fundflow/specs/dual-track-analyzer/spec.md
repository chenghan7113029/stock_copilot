## ADDED Requirements

### Requirement: DualTrackReport 新增资金面结果字段与编排
`DualTrackReport` SHALL 新增 `fund_flow_result: FundFlowResult | None` 字段（默认可为 `None`）。`DualTrackAnalyzer.analyze()` 与 `analyze_offline()` SHALL 追加调用 `FundFlowAnalyzer.analyze(code)` / `analyze_offline(code)` 并填充该字段；资金面数据缺失或计算失败时该字段 SHALL 为 `None` 并记录 warning。既有 `combined_signal`/`value_rating` 数值融合逻辑 SHALL NOT 改变，资金面仅通过独立字段与展示区块呈现。

#### Scenario: 离线分析填充资金面结果
- **WHEN** 本地已有该股价值快照、K 线缓存与资金面缓存，调用 `analyze_offline("600519")`
- **THEN** `DualTrackReport.fund_flow_result` 非空，过程不触发网络请求

#### Scenario: 资金面缺失时不阻断双轨
- **WHEN** 本地无资金面缓存，但价值面与技术面快照均存在
- **THEN** `fund_flow_result` SHALL 为 `None`，`warnings` 说明资金面缺失，`combined_signal`/`value_rating` 计算 SHALL 不受影响

#### Scenario: 融合逻辑不变（回归）
- **WHEN** 资金面为任意数值
- **THEN** `SignalFusion.fuse()` 计算的 `combined_signal`/`value_rating` SHALL 与本 change 之前完全一致，资金面不参与融合公式
