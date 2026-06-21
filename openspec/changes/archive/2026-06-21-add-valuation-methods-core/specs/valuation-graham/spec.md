## ADDED Requirements

### Requirement: GrahamNumber 计算格雷厄姆数
系统 SHALL 实现 `GrahamNumber` 估值方法，公式：`√(22.5 × EPS × BVPS)`。
BVPS < 10.0 时 SHALL 返回 `applicability="Not Applicable"` 并说明原因（轻资产公司不适用）。
公允价区间 SHALL 为 `[√(20×EPS×BVPS), √(25×EPS×BVPS)]`。

#### Scenario: 正常计算
- **WHEN** `StockData.eps = 5.0`, `bvps = 30.0`, `current_price = 50.0`
- **THEN** `fair_value ≈ 58.09`（`√(22.5 × 5 × 30)`），与 `ref/valueinvest.GrahamNumber` 同输入偏差 ≤ ±0.1%

#### Scenario: BVPS 低于阈值时不适用
- **WHEN** `StockData.bvps = 2.0`（轻资产科技股）
- **THEN** 返回 `applicability="Not Applicable"`，`error` 含 "BVPS" 关键词，不输出 `fair_value`

#### Scenario: EPS 为 None 时返回 missing_fields
- **WHEN** `StockData.eps = None`
- **THEN** 返回 `missing_fields = ["eps"]`，`fair_value = 0`，`error` 非空

### Requirement: GrahamFormula 计算成长公式内在价值
系统 SHALL 实现 `GrahamFormula` 估值方法，公式：`V = (EPS × (8.5 + 2g) × 4.4) / Y`，
其中 g 为预期增长率（%，上限 20，下限 0），Y 为 AAA 级公司债收益率（%）。
g 为 None 时 SHALL 使用 0% 并在 `warnings` 中说明；g 超界时自动截断并警告。

#### Scenario: 正常计算（有增长率）
- **WHEN** `StockData.eps = 4.0`, `growth_rate = 10.0`, `aaa_corporate_yield = 5.3`, `current_price = 60.0`
- **THEN** `fair_value ≈ (4 × (8.5 + 20) × 4.4) / 5.3 ≈ 94.34`，与 ref/valueinvest 偏差 ≤ ±0.1%

#### Scenario: growth_rate 超 20% 截断
- **WHEN** `StockData.growth_rate = 25.0`
- **THEN** 计算使用 `g = 20.0`，`warnings` 含截断说明

#### Scenario: growth_rate 为 None 时默认 0%
- **WHEN** `StockData.growth_rate = None`
- **THEN** 使用 `g = 0.0`，`warnings` 含 "defaulting to 0%" 说明，`fair_value > 0`

### Requirement: NCAV 计算净流动资产价值
系统 SHALL 实现 `NCAV（Net-Net）` 估值方法，
公式：`NCAV = (current_assets - total_liabilities - preferred_stock) / shares_outstanding`。
买入目标 SHALL 为 `NCAV × 0.67`（可配置 `safety_margin`）。
NCAV < 0 时 SHALL 在 `analysis` 中标注偿债风险，不阻断计算（返回负的 fair_value）。

#### Scenario: 正常 Net-Net 机会
- **WHEN** `current_assets = 10e9`, `total_liabilities = 5e9`, `shares_outstanding = 1e9`, `current_price = 3.0`
- **THEN** `fair_value = 5.0`，`buy_target（2/3）= 3.33`，assessment = "Undervalued"

#### Scenario: NCAV 为负时的分析提示
- **WHEN** `current_assets = 3e9`, `total_liabilities = 8e9`
- **THEN** `fair_value < 0`，`analysis` 含 "solvency" 或 "negative" 相关描述，不抛异常

#### Scenario: shares_outstanding 为 None 时 missing_fields
- **WHEN** `StockData.shares_outstanding = None`
- **THEN** `missing_fields = ["shares_outstanding"]`，`error` 非空
