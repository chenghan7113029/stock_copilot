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

### Requirement: ValueAnalyzer 支持依赖注入构造

`ValueAnalyzer.__init__` SHALL 接受 `provider`、`engine`（可选）、`router`（可选）、`aggregator`（可选）、`override_repo`（可选，`PrototypeOverrideRepo | None`）参数；`from_config(config: dict, repo=None, override_repo=None) -> ValueAnalyzer` SHALL 从配置字典构造完整实例，`override_repo` 透传给构造函数。

分析流程中（`analyze()`/`analyze_offline()` 内部的 `_analyze_stock()`）：若 `override_repo` 非 `None`，SHALL 在调用 `router.route(stock)` 前先查询 `override_repo.get_by_code(stock.code)`；查询到记录时，SHALL 以 `router.route(stock, override=record.prototype)` 调用路由，并在返回的 `ValueAnalysisResult.warnings` 中追加一条包含 `record.prototype` 与 `record.reason` 的可追溯提示；未查询到记录，或 `override_repo` 为 `None`，SHALL 按 `router.route(stock)`（不传 override）的既有方式执行，行为与本 change 之前完全一致。

#### Scenario: 默认引擎使用 default_engine

- **WHEN** `engine=None` 时构造 ValueAnalyzer
- **THEN** 内部自动使用 `default_engine()`，包含 23 个注册方法

#### Scenario: 注入 mock provider 用于单测

- **WHEN** 在测试中注入返回固定 StockData 的 mock provider
- **THEN** `analyze()` 正常执行且不发起真实网络请求

#### Scenario: 存在人工覆盖记录时应用覆盖并追加可追溯提示

- **WHEN** `override_repo.get_by_code("600519")` 返回 `PrototypeOverrideRecord(prototype="high_dividend", reason="管理层变更")`
- **THEN** `ValueAnalysisResult.prototype == "high_dividend"`（而非硬编码表/启发式原本会判定的值）
- **THEN** `ValueAnalysisResult.warnings` 中包含一条同时提及 `"high_dividend"` 与 `"管理层变更"` 的提示文案

#### Scenario: 无覆盖记录或未注入 override_repo 时行为不变

- **WHEN** `override_repo=None`，或 `override_repo.get_by_code(code)` 返回 `None`
- **THEN** `router.route(stock)` 按原有方式调用（不传 `override`），`ValueAnalysisResult` 的 `prototype`/`warnings` 与本 change 之前完全一致

### Requirement: ValueAnalysisResult 包含规定字段

`ValueAnalysisResult` SHALL 包含：`code`、`name`、`current_price`、`prototype`、`method_keys_used`、`fair_value_range`（ValuationRange 或 None）、`margin_of_safety`（float % 或 None）、`price_percentile`（0–100 或 None）、`assessment`（str）、`confidence`（"High"/"Medium"/"Low"/"不可信"）、`method_results`（dict）、`warnings`（list[str]）、`data_timestamp`、`fundamental_report_date`、`value_score`（预留，None）、`value_trap_alert`（str 或 None，默认 None；`value_trap` 方法 `overall_risk == "High"` 时非空的醒目提示文案，语义与生成规则见 `value-aggregator` capability）。

#### Scenario: 输出类型校验

- **WHEN** 分析任意 A 股代码成功返回
- **THEN** result 为 `ValueAnalysisResult` 实例，所有必填字段不缺失（`warnings` 至少为空列表，`method_results` 至少为空字典，`value_trap_alert` 缺省为 `None`）

#### Scenario: value_trap High 时字段透传

- **WHEN** `ValuationAggregator.aggregate()` 返回的 `AggregateResult.value_trap_alert` 非空
- **THEN** `ValueAnalyzer._analyze_stock()` 构造的 `ValueAnalysisResult.value_trap_alert` 与其完全一致（透传，不做二次加工）

#### Scenario: 非 High 风险时字段为 None

- **WHEN** 分析结果中 `value_trap` 方法 `overall_risk` 不是 `"High"`（或该方法未运行）
- **THEN** `ValueAnalysisResult.value_trap_alert is None`

