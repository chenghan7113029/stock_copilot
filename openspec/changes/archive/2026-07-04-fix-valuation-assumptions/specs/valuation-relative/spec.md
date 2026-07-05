## ADDED Requirements

### Requirement: pe_relative 使用 TTM EPS（年化，非季报单季值）
`PERelativeValuation.calculate(stock)` 的公允价计算所用 `stock.eps` SHALL 为年化 TTM EPS（由 provider merge 层推导），而非 Tushare `fina_indicator` 中的当期单季 EPS。当 TTM EPS 推导正确后，pe_relative 的公允价 SHALL 与 `ttm_eps × avg_historical_pe` 一致。

#### Scenario: 使用 TTM EPS 计算 pe_relative 公允价
- **WHEN** stock.eps=65.86（TTM，推导自 net_income/shares），stock.historical_pe=[22.0, 20.0, 21.0, 19.0, 23.0]（avg≈21.0）
- **THEN** pe_relative 公允价 ≈ 65.86 × 21.0 = 1383.06，约为修复前（21.76×21.0=457）的 3 倍

#### Scenario: pe_relative 公允价落入 LLM 参考区间
- **WHEN** stock=茅台（code="600519"），TTM EPS 正确推导，historical_pe 为近 2 年历史均值
- **THEN** pe_relative 公允价 SHALL 落入 1200-1600 元区间（LLM 参考 1340-1474）
