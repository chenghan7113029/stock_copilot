# value-analyzer Specification

## Purpose
TBD - created by archiving change add-value-analyzer-core. Update Purpose after archive.
## Requirements
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

#### Scenario: 正常分析（价值成长原型）
- **WHEN** code="600519"（茅台）且 StockData 包含足够的财务字段
- **THEN** 返回 `ValueAnalysisResult`，`prototype="value_growth"`，`fair_value_range` 非 None，`method_keys_used` 包含 "dcf"、"epv"、"owner_earnings" 等价值成长方法，`warnings` 列表不为 None

#### Scenario: 银行原型路由
- **WHEN** code="601398"（工行）且 StockDataProvider 返回高杠杆数据
- **THEN** `prototype="bank"`，`method_keys_used` 包含 "pb"、"residual_income"，不包含 "dcf"

#### Scenario: 非 A 股代码拒绝
- **WHEN** code="AAPL"
- **THEN** 抛出 `UnsupportedMarketError`，不返回结果

#### Scenario: 数据严重不足（unknown 原型）
- **WHEN** StockData 关键字段（total_assets、dividend_yield、growth_rate）全为 None
- **THEN** `prototype="unknown"`，`method_keys_used` 包含 "graham_number"、"altman_z"、"value_trap"，`warnings` 包含原型未识别说明

### Requirement: ValueAnalyzer 支持依赖注入构造
`ValueAnalyzer.__init__` SHALL 接受 `provider`、`engine`（可选）、`router`（可选）、`aggregator`（可选）参数；`from_config(config: dict) -> ValueAnalyzer` SHALL 从配置字典构造完整实例。

#### Scenario: 默认引擎使用 default_engine
- **WHEN** `engine=None` 时构造 ValueAnalyzer
- **THEN** 内部自动使用 `default_engine()`，包含 23 个注册方法

#### Scenario: 注入 mock provider 用于单测
- **WHEN** 在测试中注入返回固定 StockData 的 mock provider
- **THEN** `analyze()` 正常执行且不发起真实网络请求

### Requirement: ValueAnalysisResult 包含规定字段
`ValueAnalysisResult` SHALL 包含：`code`、`name`、`current_price`、`prototype`、`method_keys_used`、`fair_value_range`（ValuationRange 或 None）、`margin_of_safety`（float % 或 None）、`price_percentile`（0–100 或 None）、`assessment`（str）、`confidence`（"High"/"Medium"/"Low"）、`method_results`（dict）、`warnings`（list[str]）、`data_timestamp`、`fundamental_report_date`、`value_score`（预留，None）。

#### Scenario: 输出类型校验
- **WHEN** 分析任意 A 股代码成功返回
- **THEN** result 为 `ValueAnalysisResult` 实例，所有必填字段不缺失（`warnings` 至少为空列表，`method_results` 至少为空字典）

