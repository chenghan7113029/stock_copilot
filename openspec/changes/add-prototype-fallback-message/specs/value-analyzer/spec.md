## MODIFIED Requirements

### Requirement: ValueAnalyzer 提供单一分析入口

`ValueAnalyzer.analyze(code: str) -> ValueAnalysisResult` SHALL 内部编排：
1. 调用 `StockDataProvider.get_stock_data(code)` 获取 `StockData`
2. 调用 `PrototypeRouter.route(stock)` 获取 prototype 和 method_keys 列表
3. 调用 `ValuationEngine.run_selected(method_keys, stock)` 运行方法
4. 调用 `ValuationAggregator.aggregate(results, current_price)` 聚合
5. 返回 `ValueAnalysisResult`（包含所有字段）

异常处理：
- 非 A 股代码 → 透传 `UnsupportedMarketError`
- 数据获取失败（provider 内部异常）→ 透传，不吞掉
- 单个估值方法失败 → 已由 engine 内部捕获，不影响整体

`prototype == "unknown"` 时的 warning 生成规则：SHALL 先调用 `describe_unimplemented_industry(stock.industry)`；命中（返回非 `None` 的 `(标签, 缺口说明)`）时，追加精确文案 `f"检测到{标签}行业，{缺口说明}，当前使用通用方法，结果参考性有限"`；未命中（行业信息缺失，或行业不在已识别 V2 清单中）时，追加现有通用文案"原型未识别，使用通用方法集，置信度低"。

#### Scenario: 正常分析（价值成长原型）

- **WHEN** code="600519"（茅台）且 StockData 包含足够的财务字段
- **THEN** 返回 `ValueAnalysisResult`，`prototype="value_growth"`，`fair_value_range` 非 None，`method_keys_used` 包含 "dcf"、"epv"、"owner_earnings" 等价值成长方法，`warnings` 列表不为 None

#### Scenario: 银行原型路由

- **WHEN** code="601398"（工行）且 StockDataProvider 返回高杠杆数据
- **THEN** `prototype="bank"`，`method_keys_used` 包含 "pb"、"residual_income"，不包含 "dcf"

#### Scenario: 非 A 股代码拒绝

- **WHEN** code="AAPL"
- **THEN** 抛出 `UnsupportedMarketError`，不返回结果

#### Scenario: 数据严重不足且行业信息缺失（unknown 原型，通用文案）

- **WHEN** StockData 关键字段（total_assets、dividend_yield、growth_rate）全为 None，且 `industry` 为空
- **THEN** `prototype="unknown"`，`method_keys_used` 包含 "graham_number"、"altman_z"、"value_trap"，`warnings` 包含"原型未识别，使用通用方法集，置信度低"

#### Scenario: 已识别 V2 行业但方法论暂缺（unknown 原型，精确文案）

- **WHEN** `StockData(code="601318", industry="保险", ...)`，路由结果 `prototype="unknown"`
- **THEN** `warnings` 包含同时提及"保险"与"EV/NBV"的精确文案，**不包含**笼统的"原型未识别"措辞
