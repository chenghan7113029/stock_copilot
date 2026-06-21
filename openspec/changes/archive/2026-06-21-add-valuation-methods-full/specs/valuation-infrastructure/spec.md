## MODIFIED Requirements

### Requirement: ValuationEngine 注册并批量运行方法
系统 SHALL 提供 `ValuationEngine`，支持按名称注册估值方法、单独运行（`run_single`）
或批量运行（`run_all`）。`run_all` SHALL 在单个方法抛出异常时不中断，
将异常包装为 `ValuationResult(error=str(exc))`。

`default_engine()` SHALL 预注册 Phase 0–7 全部 method_key：
graham_number、graham_formula、ncav、pb、residual_income、ddm、two_stage_ddm、epv、
owner_earnings、dcf、reverse_dcf、altman_z、piotroski_f、beneish_m、
peg、garp、rule_of_40、ev_ebitda、magic_formula、pe_relative、pb_relative。

评分类方法（altman_z、piotroski_f、beneish_m、rule_of_40）SHALL 在 `details` 中设置
`output_type = "score"`，供下游聚合层排除公允价输入。

#### Scenario: 注册并单独运行方法
- **WHEN** `engine.register("graham_number", GrahamNumber())` 后调用 `engine.run_single("graham_number", stock_data)`
- **THEN** 返回 `ValuationResult`，`method == "Graham Number"`

#### Scenario: 批量运行某方法内部抛异常不中断
- **WHEN** `run_all` 中某方法 `calculate()` 抛出 `RuntimeError`
- **THEN** 该方法对应结果的 `error` 非空，其余方法结果正常返回，整体 `run_all` 不抛出异常

#### Scenario: default_engine 包含 Phase 4-7 全部 method_key
- **WHEN** 调用 `default_engine()` 并检查注册表
- **THEN** 至少包含 owner_earnings、dcf、reverse_dcf、altman_z、peg、pe_relative 等 21 个 key

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
