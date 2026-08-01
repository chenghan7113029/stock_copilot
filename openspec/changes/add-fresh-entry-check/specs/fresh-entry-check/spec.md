## ADDED Requirements

### Requirement: 隐藏成本价的框架提问呈现
系统 SHALL 提供 `FreshEntryCheck.build(code) -> FreshEntryView`，内部调用 `DualTrackAnalyzer.analyze_offline()` 获取确定性结果，呈现内容 SHALL 包含现价、价值面结论、技术面结论与框架提问文本（「若你今天没有该股票的仓位，以现价买入，你还会买吗？」），SHALL NOT 包含 `PositionRecord.cost_price` 或任何盈亏百分比字段。

#### Scenario: 已录入持仓
- **WHEN** 调用 `build(code)` 且该代码本地已有 `PositionRecord`
- **THEN** `FreshEntryView` SHALL 包含固定提醒文案（提示已隐藏成本价，需独立判断），SHALL NOT 包含 `cost_price` 或盈亏百分比数值

#### Scenario: 未录入持仓
- **WHEN** 调用 `build(code)` 且该代码本地无 `PositionRecord`
- **THEN** `FreshEntryView` SHALL 包含「未检测到本地持仓记录，以下为标准三维分析」提示，SHALL NOT 抛异常

### Requirement: CLI `entry-check` 命令
系统 SHALL 提供 `python -m apps.cli entry-check <code> [--json] [--output]`，严格离线，输出 `FreshEntryCheck.build(code)` 的结果。

#### Scenario: 正常输出
- **WHEN** 运行 `entry-check 600519`（本地已有价值快照与 K 线缓存）
- **THEN** SHALL 输出现价、三维分析摘要与框架提问，不发起任何网络请求，输出内容 SHALL NOT 含成本价/盈亏百分比

#### Scenario: 无本地数据时明确报错
- **WHEN** 运行 `entry-check <code>` 但本地无该代码的价值快照与 K 线缓存
- **THEN** SHALL 输出 `[error] 未找到 <code> 的本地数据，请先运行 sync`，退出码非 0
