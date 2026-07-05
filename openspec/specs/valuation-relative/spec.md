# valuation-relative Specification

## Purpose
TBD - created by archiving change add-valuation-methods-full. Update Purpose after archive.
## Requirements
### Requirement: MagicFormula Greenblatt 神奇公式
系统 SHALL 实现 `MagicFormula`，计算 Earnings Yield（EBIT/EV）与 ROC（EBIT/Invested Capital），
基于 `required_ey`（默认 10%）与 `benchmark_roc`（默认 25%）推导 implied fair value。

#### Scenario: 正常 Magic Formula 计算
- **WHEN** ebit > 0（或可从 revenue × operating_margin 推导）、EV > 0、invested_capital > 0
- **THEN** `fair_value > 0`，与 ref ±0.1%

#### Scenario: invested_capital ≤ 0 时使用 fallback
- **WHEN** net_fixed_assets + net_working_capital ≤ 0 但 equity+debt fallback > 0
- **THEN** 使用 fallback 计算，`warnings` 说明

### Requirement: PERelativeValuation 历史 PE 分位估值
系统 SHALL 实现 `PERelativeValuation`，基于 `StockData.historical_pe` 序列计算当前 PE 分位，
公允价 = EPS × 历史中位 PE（或分位对应 PE）。

#### Scenario: historical_pe 有值时正常计算
- **WHEN** `historical_pe = [18.5, 20.1, 15.3, 22.0, 16.8]`，eps、current_price 齐全
- **THEN** `fair_value > 0`，`applicability = "Applicable"`，与 ref ±0.1%

#### Scenario: historical_pe 为 None 时 Not Applicable
- **WHEN** `StockData.historical_pe = None`
- **THEN** `applicability = "Not Applicable"`，不抛异常

### Requirement: PBRelativeValuation 历史 PB 分位估值
系统 SHALL 实现 `PBRelativeValuation`，逻辑同 PE Relative，使用 `historical_pb` 与 bvps。**当 `historical_pb` 由 Tushare 5 年数据提供后，该方法 SHALL 从 Not Applicable 变为 Applicable，参与聚合中位计算。**

#### Scenario: historical_pb 有值时正常计算
- **WHEN** `historical_pb` 长度 ≥ 3，bvps、current_price 齐全
- **THEN** `fair_value > 0`，与 ref ±0.1%

#### Scenario: historical_pb 为空时 Not Applicable
- **WHEN** `StockData.historical_pb = None` 或 `[]`
- **THEN** `applicability = "Not Applicable"`

### Requirement: pe_relative 使用 TTM EPS（年化，非季报单季值）
`PERelativeValuation.calculate(stock)` 的公允价计算所用 `stock.eps` SHALL 为年化 TTM EPS（由 provider merge 层推导），而非 Tushare `fina_indicator` 中的当期单季 EPS。当 TTM EPS 推导正确后，pe_relative 的公允价 SHALL 与 `ttm_eps × avg_historical_pe` 一致。

#### Scenario: 使用 TTM EPS 计算 pe_relative 公允价
- **WHEN** stock.eps=65.86（TTM，推导自 net_income/shares），stock.historical_pe=[22.0, 20.0, 21.0, 19.0, 23.0]（avg≈21.0）
- **THEN** pe_relative 公允价 ≈ 65.86 × 21.0 = 1383.06，约为修复前（21.76×21.0=457）的 3 倍

#### Scenario: pe_relative 公允价落入 LLM 参考区间
- **WHEN** stock=茅台（code="600519"），TTM EPS 正确推导，historical_pe 为近 2 年历史均值
- **THEN** pe_relative 公允价 SHALL 落入 1200-1600 元区间（LLM 参考 1340-1474）

### Requirement: PERelativeValuation 数据窗口扩展至 5 年
`PERelativeValuation` 所使用的 `historical_pe` SHALL 来自 Tushare 5 年季末采样（约 20 点）；Baostock 2 年（约 8 点）作为 fallback。更长的窗口使均值更稳定，减少近期市场情绪偏差。

#### Scenario: 5 年 PE 均值比 2 年更稳定
- **WHEN** `historical_pe` 包含 ≥ 15 个点
- **THEN** pe_relative 公允价基于更长期均值，不受近 2 年极端行情影响

