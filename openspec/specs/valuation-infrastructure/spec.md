# valuation-infrastructure Specification

## Purpose
TBD - created by archiving change add-valuation-methods-core. Update Purpose after archive.
## Requirements
### Requirement: BaseValuation 提供统一计算接口
系统 SHALL 提供 `BaseValuation` 抽象基类，所有估值方法继承该类并实现 `calculate(stock) -> ValuationResult`。
`ValuationResult` SHALL 包含：`method`（方法名）、`fair_value`（公允价）、`current_price`、
`premium_discount`（溢价/折价 %）、`assessment`（Undervalued/Fair/Overvalued）、
`missing_fields`（缺失字段列表）、`warnings`（警告列表）、`confidence`（High/Medium/Low）、
`fair_value_range`（ValuationRange: low/base/high）、`applicability`（Applicable/Limited/Not Applicable）、
`error`（错误信息，无误时为 None）。

#### Scenario: 正常计算返回结果
- **WHEN** 传入数据完整的 `StockData`（所有 critical 字段非 None 且满足 min_value 约束）
- **THEN** `calculate()` 返回 `ValuationResult`，`error=None`，`fair_value > 0`，`missing_fields=[]`

#### Scenario: 缺失 critical 字段返回错误结果
- **WHEN** `StockData` 中某 `is_critical=True` 的字段为 `None`
- **THEN** 返回 `ValuationResult`，`error` 非空，`fair_value=0`，`missing_fields` 包含该字段名，不抛出异常

#### Scenario: 0.0 不视为缺失
- **WHEN** `StockData` 中某字段值为 `0.0`（真实零值，如 `interest_expense=0.0`）
- **THEN** 该字段不出现在 `missing_fields`，值 `0.0` 被透传到计算逻辑

### Requirement: AssumptionProvider 集中管理假设参数
系统 SHALL 提供 `AssumptionProvider` 类，统一提供估值方法所需的宏观经济假设参数，
参数取值优先级：`StockData` 字段 > 方法实例 `__init__` 覆盖 > `config/app.yaml value_analysis:` > 硬编码默认值。

除现有参数外，SHALL 提供 DCF 专用默认值：
- `growth_rate_1_5 = 5.0`（%）
- `growth_rate_6_10 = 3.0`（%）
- `terminal_growth = 2.0`（%）
- `ev_ebitda_multiple = 12.0`（可配置行业基准）

#### Scenario: 使用 StockData 字段覆盖默认值
- **WHEN** `StockData.cost_of_capital = 8.5` 且未提供外部覆盖参数
- **THEN** `AssumptionProvider.get_discount_rate(stock_data)` 返回 `8.5`

#### Scenario: DCF 增长率使用 AssumptionProvider 默认
- **WHEN** `StockData.growth_rate = None` 且 config 无覆盖
- **THEN** `get_growth_rate_1_5(stock)` 返回 `5.0`

### Requirement: StockDataAdapter 将 StockData 转换为估值方法输入
系统 SHALL 提供 `StockDataAdapter`，将 `StockData` 对象转换为估值方法可直接读取的属性访问接口，
凡 `StockData.xxx = None` 的字段，通过 adapter 访问时 SHALL 返回 `None`（不返回 0）。

#### Scenario: None 字段通过 adapter 透传为 None
- **WHEN** `StockData.eps = None`
- **THEN** `adapter.eps` 返回 `None`，不返回 `0.0`

#### Scenario: 有值字段正常返回
- **WHEN** `StockData.bvps = 12.5`
- **THEN** `adapter.bvps` 返回 `12.5`

### Requirement: ValuationEngine 注册并批量运行方法
系统 SHALL 提供 `ValuationEngine`，支持按名称注册估值方法、单独运行（`run_single`）
或批量运行（`run_all`）。`run_all` SHALL 在单个方法抛出异常时不中断，
将异常包装为 `ValuationResult(error=str(exc))`。

`default_engine()` SHALL 预注册 Phase 0–8 全部 method_key（共 23 个）：
graham_number、graham_formula、ncav、pb、residual_income、ddm、two_stage_ddm、epv、
owner_earnings、dcf、reverse_dcf、altman_z、piotroski_f、beneish_m、
peg、garp、rule_of_40、ev_ebitda、magic_formula、pe_relative、pb_relative、
value_trap、sbc。

评分类方法（altman_z、piotroski_f、beneish_m、rule_of_40、value_trap、sbc）SHALL 在 `details` 中设置
`output_type = "score"`，供下游聚合层排除公允价输入。

#### Scenario: 注册并单独运行方法
- **WHEN** `engine.register("graham_number", GrahamNumber())` 后调用 `engine.run_single("graham_number", stock_data)`
- **THEN** 返回 `ValuationResult`，`method == "Graham Number"`

#### Scenario: 批量运行某方法内部抛异常不中断
- **WHEN** `run_all` 中某方法 `calculate()` 抛出 `RuntimeError`
- **THEN** 该方法对应结果的 `error` 非空，其余方法结果正常返回，整体 `run_all` 不抛出异常

#### Scenario: default_engine 包含 Phase 0-8 全部 method_key
- **WHEN** 调用 `default_engine()` 并检查注册表
- **THEN** 包含全部 23 个 key，含 value_trap 和 sbc

### Requirement: WACC 计算从 StockData 推导
系统 SHALL 提供 `calculate_wacc(stock_data, **overrides) -> WACCResult`，
公式：`WACC = (E/V) × Re + (D/V) × Rd × (1 - T)`，
其中 Re 在有 β 时用 CAPM，无 β 时用 `cost_of_capital`；
Rd 在有 `interest_expense` 时用实际利率，否则用 `aaa_corporate_yield`。

#### Scenario: 有完整数据时计算 WACC
- **WHEN** `StockData` 含 `market_cap`, `net_debt`, `interest_expense`, `short_term_debt`, `long_term_debt`, `tax_rate`
- **THEN** `WACCResult.wacc` 按公式正确计算，与 `ref/valueinvest.roic.wacc.calculate_wacc` 同输入偏差 ≤ ±0.1%

#### Scenario: 缺少负债数据时 equity_weight=1
- **WHEN** `StockData.market_cap > 0` 且 `net_debt = 0`（无负债）
- **THEN** `WACCResult.equity_weight = 1.0`，`debt_weight = 0.0`

