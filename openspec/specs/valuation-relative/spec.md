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
系统 SHALL 实现 `PBRelativeValuation`，逻辑同 PE Relative，使用 `historical_pb` 与 bvps。

#### Scenario: historical_pb 有值时正常计算
- **WHEN** `historical_pb` 长度 ≥ 3，bvps、current_price 齐全
- **THEN** `fair_value > 0`，与 ref ±0.1%

#### Scenario: historical_pb 为空时 Not Applicable
- **WHEN** `StockData.historical_pb = None` 或 `[]`
- **THEN** `applicability = "Not Applicable"`

