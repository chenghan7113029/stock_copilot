## ADDED Requirements

### Requirement: 诚实降级时主评估与 methodology_applicable

当分析流程中 `describe_honesty_gap(stock.code, stock.industry)` 非空，且本次路由**未**因人工 override 落到已实现原型（`bank` / `high_dividend` / `value_growth`）时，`ValueAnalyzer` SHALL：

1. 将 `ValueAnalysisResult.methodology_applicable` 设为 `False`
2. 将 `assessment` 设为 `"方法暂不适用"`（覆盖聚合器基于 MOS 的低估/高估）
3. 将 `confidence` 降为不高于 `"Low"`（若已为 `"不可信"` 则保持 `"不可信"`）
4. **保留** `fair_value_range` 与 `margin_of_safety`（若聚合器已算出）供对照
5. 在 `warnings` **靠前**插入诚实缺口文案（含不能作为买卖依据的语义）

未命中诚实缺口时，`methodology_applicable` SHALL 默认为 `True`，assessment/confidence 行为与本 change 之前一致。

#### Scenario: 比亚迪诚实降级

- **WHEN** 分析 `002594` 且无人工覆盖为已实现原型
- **THEN** `methodology_applicable is False`，`assessment == "方法暂不适用"`，`warnings` 含制造周期/不能买卖依据语义，`prototype == "unknown"`

#### Scenario: 保险与持仓同标准压制

- **WHEN** 分析 `601318`（industry 含保险）且无覆盖
- **THEN** `methodology_applicable is False`，`assessment == "方法暂不适用"`，warnings 含 EV/NBV 与不用于买卖决策语义

#### Scenario: 茅台不受影响

- **WHEN** 分析 `600519` 且路由为 `value_growth`
- **THEN** `methodology_applicable is True`，`assessment` 仍由 MOS 规则得出（可为低估/高估/数据不足等）

#### Scenario: 覆盖为 value_growth 时豁免压制

- **WHEN** `002594` 存在 override=`value_growth`
- **THEN** `methodology_applicable is True`（诚实压制不启用）

## MODIFIED Requirements

### Requirement: ValueAnalyzer 提供单一分析入口

`ValueAnalyzer.analyze(code: str) -> ValueAnalysisResult` SHALL 内部编排：
1. 调用 `StockDataProvider.get_stock_data(code)` 获取 `StockData`
2. 调用 `PrototypeRouter.route(stock)` 获取 prototype 和 method_keys 列表
3. 调用 `ValuationEngine.run_selected(method_keys, stock)` 运行方法
4. 调用 `ValuationAggregator.aggregate(results, current_price)` 聚合
5. 按诚实降级规则（见 ADDED「诚实降级时主评估与 methodology_applicable」）调整结果字段
6. 返回 `ValueAnalysisResult`（包含所有字段）

异常处理：
- 非 A 股代码 → 透传 `UnsupportedMarketError`
- 数据获取失败（provider 内部异常）→ 透传，不吞掉
- 单个估值方法失败 → 已由 engine 内部捕获，不影响整体

warning 生成规则：

- 若 `describe_honesty_gap(code, industry)` 命中且未因 override 豁免：追加该缺口的精确诚实文案（**不**再追加笼统「原型未识别」）
- 否则若 `prototype == "unknown"`：追加现有通用文案「原型未识别，使用通用方法集，置信度低」
- 保险/军工等行业缺口文案 MUST 含「不应用于买卖决策」语义（与 router 缺口说明一致）

#### Scenario: 正常分析（价值成长原型）

- **WHEN** code="600519"（茅台）且 StockData 包含足够的财务字段
- **THEN** 返回 `ValueAnalysisResult`，`prototype="value_growth"`，`methodology_applicable is True`，`fair_value_range` 非 None，`method_keys_used` 包含 "dcf"、"epv"、"owner_earnings" 等价值成长方法，`warnings` 列表不为 None

#### Scenario: 银行原型路由

- **WHEN** code="601398"（工行）且 StockDataProvider 返回高杠杆数据
- **THEN** `prototype="bank"`，`method_keys_used` 包含 "pb"、"residual_income"，不包含 "dcf"，`methodology_applicable is True`

#### Scenario: 非 A 股代码拒绝

- **WHEN** code="AAPL"
- **THEN** 抛出 `UnsupportedMarketError`，不返回结果

#### Scenario: 数据严重不足且行业信息缺失（unknown 原型，通用文案）

- **WHEN** StockData 关键字段（total_assets、dividend_yield、growth_rate）全为 None，且 `industry` 为空，且 code 不在诚实名单
- **THEN** `prototype="unknown"`，`method_keys_used` 包含 "graham_number"、"altman_z"、"value_trap"，`warnings` 包含"原型未识别，使用通用方法集，置信度低"，`methodology_applicable is True`（通用 unknown 不视为「已识别 V2 诚实降级」）

#### Scenario: 已识别 V2 行业但方法论暂缺（精确文案 + 主评估压制）

- **WHEN** `StockData(code="601318", industry="保险", ...)`，路由结果 `prototype="unknown"`
- **THEN** `warnings` 包含同时提及"保险"与"EV/NBV"以及不用于买卖决策的精确文案，**不包含**笼统的"原型未识别"措辞，且 `assessment == "方法暂不适用"`，`methodology_applicable is False`

### Requirement: ValueAnalysisResult 包含规定字段

`ValueAnalysisResult` SHALL 包含：`code`、`name`、`current_price`、`prototype`、`method_keys_used`、`fair_value_range`（ValuationRange 或 None）、`margin_of_safety`（float % 或 None）、`price_percentile`（0–100 或 None）、`assessment`（str）、`confidence`（"High"/"Medium"/"Low"/"不可信"）、`method_results`（dict）、`warnings`（list[str]）、`data_timestamp`、`fundamental_report_date`、`value_score`（预留，None）、`value_trap_alert`（str 或 None，默认 None；`value_trap` 方法 `overall_risk == "High"` 时非空的醒目提示文案，语义与生成规则见 `value-aggregator` capability）、`methodology_applicable`（bool，默认 `True`；诚实降级名单命中且未 override 豁免时为 `False`）。

#### Scenario: 输出类型校验

- **WHEN** 分析任意 A 股代码成功返回
- **THEN** result 为 `ValueAnalysisResult` 实例，所有必填字段不缺失（`warnings` 至少为空列表，`method_results` 至少为空字典，`value_trap_alert` 缺省为 `None`，`methodology_applicable` 缺省为 `True`）

#### Scenario: value_trap High 时字段透传

- **WHEN** `ValuationAggregator.aggregate()` 返回的 `AggregateResult.value_trap_alert` 非空
- **THEN** `ValueAnalyzer._analyze_stock()` 构造的 `ValueAnalysisResult.value_trap_alert` 与其完全一致（透传，不做二次加工）

#### Scenario: 非 High 风险时字段为 None

- **WHEN** 分析结果中 `value_trap` 方法 `overall_risk` 不是 `"High"`（或该方法未运行）
- **THEN** `ValueAnalysisResult.value_trap_alert is None`

#### Scenario: 诚实降级时 methodology_applicable 为 False

- **WHEN** 分析命中诚实名单（如 `002594`）且未豁免
- **THEN** `methodology_applicable is False`
