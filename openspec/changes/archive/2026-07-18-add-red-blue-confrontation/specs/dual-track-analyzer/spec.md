## ADDED Requirements

### Requirement: DualTrackAnalyzer 新增离线分析方法
`DualTrackAnalyzer` SHALL 新增 `analyze_offline(code: str) -> DualTrackReport`，内部调用 `ValueAnalyzer.analyze_offline()` 与 `TechAnalyzer.analyze(code, offline=True)`，不发起任何网络请求。既有 `analyze()`（联网版）行为 SHALL 保持不变。

#### Scenario: 离线双轨分析成功
- **WHEN** 本地已有 `600519` 的价值快照与 K 线缓存，调用 `analyze_offline("600519")`
- **THEN** SHALL 返回 `DualTrackReport`，且过程不触发任何网络请求

#### Scenario: 无本地缓存时降级
- **WHEN** 本地无 `600519` 的价值快照或 K 线缓存
- **THEN** 对应子结果（`value_result`/`tech_result`）SHALL 为 `None` 并记录 warning，`combined_signal` 按现有降级语义处理，不抛异常

#### Scenario: 既有联网 analyze() 行为不变
- **WHEN** 调用既有 `analyze("600519")`（联网版）
- **THEN** 行为与本 change 之前完全一致（回归测试覆盖）
