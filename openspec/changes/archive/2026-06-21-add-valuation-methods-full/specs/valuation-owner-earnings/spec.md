## ADDED Requirements

### Requirement: OwnerEarnings 计算巴菲特所有者收益并估值
系统 SHALL 实现 `OwnerEarnings` 方法，公式：
`OE = 净利润 + 折旧 - 维护性资本支出 - 营运资本变化`。
维护性 capex 默认取总 capex 的 70%（可配置 `maintenance_capex_pct`）；
depreciation/capex 缺失时按营收百分比估算并在 `warnings` 说明。
公允价 = 零增长价值与 Gordon 增长价值（使用 `growth_rate`）的算术平均。

#### Scenario: 正常 Owner Earnings 估值
- **WHEN** `StockData` 含 net_income、depreciation、capex、shares_outstanding、current_price、cost_of_capital（经 adapter 提供）
- **THEN** `fair_value > 0`，与 `ref/valueinvest.OwnerEarnings` 同输入偏差 ≤ ±0.1%

#### Scenario: Owner Earnings 为负时返回错误
- **WHEN** 计算得 owner_earnings ≤ 0
- **THEN** 返回 `error` 非空，`fair_value=0`，不抛异常

#### Scenario: net_income 为 None 时 missing_fields
- **WHEN** `StockData.net_income = None`
- **THEN** `missing_fields` 含 `net_income`
