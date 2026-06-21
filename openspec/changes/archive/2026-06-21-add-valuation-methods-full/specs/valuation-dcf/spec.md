## ADDED Requirements

### Requirement: DCF 三阶段自由现金流折现
系统 SHALL 实现 `DCF` 方法，使用 WACC 折现三阶段 FCF：
- 第 1–5 年：增长率 `growth_rate_1_5`（默认 5%）
- 第 6–10 年：增长率 `growth_rate_6_10`（默认 3%）
- 终值：Gordon 增长 `terminal_growth`（默认 2%）
FCF 基数取自 `StockData.fcf`；缺失时尝试 `operating_cash_flow - abs(capex)` 推导。

#### Scenario: 正常 DCF 计算
- **WHEN** `StockData.fcf > 0`、shares_outstanding、current_price 齐全，WACC 可计算
- **THEN** `fair_value > 0`，与 `ref/valueinvest.DCF` 同输入偏差 ≤ ±0.1%

#### Scenario: fcf 为 None 且无法推导时 missing_fields
- **WHEN** `StockData.fcf = None` 且 operating_cash_flow/capex 均缺失
- **THEN** `missing_fields` 含 `fcf`，`error` 非空

### Requirement: ReverseDCF 反推市场隐含增长率
系统 SHALL 实现 `ReverseDCF`，从 `current_price` 反推使 DCF 公允价等于现价的隐含永续增长率（或等效参数），结果写入 `details.implied_growth_rate`。

#### Scenario: 正常反推隐含增长率
- **WHEN** 与 DCF 相同输入且 current_price 在 DCF 公允价附近
- **THEN** `details.implied_growth_rate` 为有限正数，与 ref ±0.1% 相对误差

#### Scenario: 无解时返回错误
- **WHEN** current_price 极端偏离导致二分法不收敛
- **THEN** `error` 非空，不抛异常
