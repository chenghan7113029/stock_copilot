## ADDED Requirements

### Requirement: 从历史价格与 epsTTM 计算 historical_pe 序列
`BaostockFetcher.fetch_fundamentals` SHALL 在同一 Baostock session 内，查询过去 2 年（8 个季末）的收盘价与 `epsTTM`，计算 PE 快照列表，写入 `StockData.historical_pe`。

#### Scenario: 取到足够历史数据
- **WHEN** 过去 8 个季末中至少 3 个能同时获取到收盘价和 epsTTM
- **THEN** `historical_pe` = 各季末 `close / epsTTM` 的有效值列表（已剔除负值和 PE > 200 的极值），且列表长度 ≥ 3

#### Scenario: 数据不足（< 3 个有效季末）
- **WHEN** 可计算的有效 PE 快照数量 < 3
- **THEN** `historical_pe` 不写入，加入 `missing_fields["historical_pe"]`

#### Scenario: epsTTM 为负（亏损期）
- **WHEN** 某季末 `epsTTM ≤ 0`
- **THEN** 该季末的 PE 快照 SHALL 被跳过，不计入 `historical_pe` 列表

#### Scenario: PE 极值过滤
- **WHEN** 某季末计算得 PE > 200 或 PE ≤ 0
- **THEN** 该值 SHALL 被过滤，写入 debug 日志
