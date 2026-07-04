## ADDED Requirements

### Requirement: Baostock 使用 TTM 净利润而非单季值
`BaostockFetcher.fetch_fundamentals` SHALL 通过 `epsTTM × shares_outstanding` 推导 TTM 净利润写入 `net_income`，不直接使用 `netProfit`（单季值）。

#### Scenario: 正常取到 epsTTM 和 shares
- **WHEN** `query_profit_data` 返回有效的 `epsTTM` 且 `shares_outstanding` 已知
- **THEN** `net_income = epsTTM × shares_outstanding`，单位为元，写入 `FetchResult.data["net_income"]`

#### Scenario: epsTTM 为 None
- **WHEN** `epsTTM` 字段为空字符串或无法解析
- **THEN** `net_income` 不写入 `data`，加入 `missing_fields`

#### Scenario: shares_outstanding 尚未获取
- **WHEN** `fetch_fundamentals` 调用时 `shares_outstanding` 不在当前 session 数据中
- **THEN** 退化：直接使用 `netProfit`（原单季值），写入警告日志
