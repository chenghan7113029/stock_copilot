## ADDED Requirements

### Requirement: get_kline 支持显式 as_of 观察日
`KlineProvider.get_kline` SHALL 接受可选参数 `as_of`（`None` | `date` | `YYYY-MM-DD` 字符串）。当 `as_of` 为 `None` 时，行为 MUST 与现网一致：观察日 = `date.today()`。当提供 `as_of` 时，查询窗口 MUST 为 `[as_of - days, as_of]`（日期字符串闭区间语义与现实现一致），offline 与 online 路径均适用；`offline=True` 时仍 MUST NOT 发起外部 API。

#### Scenario: 默认等价今天
- **WHEN** 调用 `get_kline("600519", days=90)` 且不传 `as_of`
- **THEN** 窗口 end 等于调用当日的日历日（与变更前语义一致）

#### Scenario: 显式 as_of 切窗口
- **WHEN** 调用 `get_kline("600519", days=90, offline=True, as_of="2026-08-10")` 且缓存含该窗口数据
- **THEN** 返回的 DataFrame 日期均落在 `2026-05-12`～`2026-08-10` 的查询语义内（具体 start 由 days 推算），且不联网

#### Scenario: TechAnalyzer 传递 as_of
- **WHEN** `TechAnalyzer.analyze(code, offline=True, as_of=...)` 被调用
- **THEN** SHALL 将同一 `as_of` 传入 `get_kline`，使离线技术面结果不依赖墙钟
