## Purpose

A 股价值面数据接入层：统一数据模型、多源 fetcher 管理与配置驱动选源，支撑 V1 三原型估值方法的确定性取数。
## Requirements
### Requirement: 统一 A 股股票估值数据模型
系统 SHALL 提供一个统一的股票估值数据模型，覆盖 MRD §7 中 V1 三原型（银行 / 高股息·类债 / 高质量价值成长）所有估值方法所需的字段，包括：基础行情（当前价、总股本、市值）、每股指标（EPS、BVPS、每股分红）、盈利（营收、净利润、ROE/ROIC）、现金流（自由现金流、经营现金流、capex）、资产负债（总资产、总负债、净负债、股东权益）、分红（股息率、派息率、分红历史）、历史估值序列（历史 PE / PB）、质量与风险明细（Altman-Z / Piotroski-F / Beneish-M 所需输入）。

该模型为确定性数据结构，MUST NOT 由 LLM 生成或修改。

新增字段（向后兼容追加，默认 None）：
- `historical_pe: list[float] | None`：历史滚动 PE 序列（最近 N 期，降序），供相对估值方法使用
- `historical_pb: list[float] | None`：历史滚动 PB 序列（最近 N 期，降序），供相对估值方法使用

#### Scenario: 模型字段覆盖 V1 方法需求
- **WHEN** 价值面估值方法（PB、剩余收益、DDM、DCF、EPV、Owner Earnings、Graham、相对估值、Altman-Z、Piotroski-F、Beneish-M）声明其输入字段
- **THEN** 数据模型 SHALL 为每个字段提供对应属性，且类型明确（数值/序列/日期）

#### Scenario: 数据模型不可由 LLM 改写
- **WHEN** 数据模型实例被传入下游
- **THEN** 其数值字段 SHALL 仅来自 data_provider 的确定性取数，不经任何 LLM 环节

#### Scenario: historical_pe / historical_pb 字段缺失时相关估值方法返回 Not Applicable
- **WHEN** `StockData.historical_pe = None`（data_provider 尚未支持历史数据获取）
- **THEN** `PERelativeValuation.calculate()` 返回 `applicability = "Not Applicable"`，不抛异常，不阻断其他方法运行

#### Scenario: historical_pe / historical_pb 字段有值时相对估值方法正常运行
- **WHEN** `StockData.historical_pe = [18.5, 20.1, 15.3, 22.0, 16.8]`（5 期历史 PE）
- **THEN** `PERelativeValuation.calculate()` 正常输出公允价区间，`applicability = "Applicable"`

### Requirement: 多数据源独立管理与配置驱动选源

系统 SHALL 以独立 fetcher 管理多个 A 股数据源，并通过配置（`config/app.yaml` 的 `data_sources`）指定启用哪些数据源及其优先级。运行态选源顺序 MUST 完全来自配置 `priority`（及 Router），MUST NOT 依赖 fetcher 类硬编码默认 priority 决定合并顺序。取数时价值面 SHALL 对已启用源并行/全量拉取后按 priority 做字段级合并；K 线等旁路 SHALL 使用 Failover（见 `data-fetcher-router`）。需 token 的源 MUST 显式配置且提供有效 Token 后才实例化。

所有 fetcher 的 `fetch_all` 方法 SHALL 使用统一签名 `(code: str, exchange: str) -> FetchResult`。Provider 对每个已实例化的 fetcher SHALL 分别调用并独立落库（来源维度），不因优先级而跳过低位源的持久化。

合并阶段 MUST NOT 对财报字段集合执行「来源为 tushare 则 `override_field` 无视已合并高优先级值」的特例；字段冲突一律以 priority 为准。

#### Scenario: 按配置启用数据源

- **WHEN** 配置中仅启用部分数据源
- **THEN** 系统 SHALL 只从已启用的数据源采集，未启用的源不被调用

#### Scenario: 按优先级合并字段并记录命中源

- **WHEN** 同一字段可由多个已启用数据源提供
- **THEN** 系统 SHALL 优先采用优先级更高的数据源，高优先级已提供的字段不被低优先级覆盖，并在元数据中记录每字段实际命中的源

#### Scenario: 不再 Tushare 强制覆盖已合并财报字段

- **WHEN** 高优先级非 Tushare 源已写入某 `FINANCIAL_STATEMENT_FIELDS` 字段，随后 Tushare 亦提供该字段
- **THEN** 合并结果保留高优先级已有值，不调用 `override_field` 覆盖

#### Scenario: fetch_all 接口一致

- **WHEN** SourceManager 或 StockDataProvider 调用任一 fetcher 的 `fetch_all`
- **THEN** 调用签名与返回类型在各源间一致，不因源而分支异常

### Requirement: 仅支持国内 A 股市场（V1）

系统 SHALL 在 V1 范围内仅支持国内 A 股（上交所 / 深交所 / 北交所）股票代码。对非 A 股标的，系统 MUST 明确拒绝并提示暂不支持，而非返回不可靠数据。

#### Scenario: A 股代码正常受理

- **WHEN** 传入合法 A 股代码（如 `600519`、`601398`、`002594`）
- **THEN** 系统 SHALL 标准化代码、识别交易所并返回数据

#### Scenario: 非 A 股标的被拒绝

- **WHEN** 传入非 A 股标的（如美股 `AAPL`）
- **THEN** 系统 SHALL 返回"V1 暂不支持该市场"的明确错误，不返回猜测数据

### Requirement: 字段缺失降级与来源/时效元数据

每条取数结果 MUST 携带数据来源标识与时效（行情时间戳 / 财报报告期）。当某字段无法获取时，系统 SHALL 显式标注该字段缺失，而非以 0 或默认值静默填充导致下游误判（对应 MRD VA-DATA-1/2）。

#### Scenario: 缺失字段被显式标注

- **WHEN** 某数据源未能提供模型中的某字段
- **THEN** 结果 SHALL 在 `missing_fields`（或等价结构）中列出该字段，下游方法据此将自身标注为"数据缺失不可靠"

#### Scenario: 结果携带来源与时效

- **WHEN** 取数成功返回
- **THEN** 结果 SHALL 包含数据来源名称、行情时间戳与财报报告期

### Requirement: 数据完备性验收（交付门槛一）

交付前，系统 SHALL 通过数据完备性校验：对 MRD 指定的样本股票（银行=工商银行/招商银行、高股息=长江电力、价值成长=贵州茅台），接入的数据 SHALL 满足其对应原型全部估值方法的输入字段需求；任何必需字段缺失须可被识别并报告。

#### Scenario: 样本股票字段完备

- **WHEN** 对每只样本股票执行取数并按其原型的方法字段需求校验
- **THEN** 校验报告 SHALL 显示该原型所有必需字段均已获取，或明确列出缺失字段及影响的方法

#### Scenario: 完备性校验可复跑

- **WHEN** 运行完备性校验脚本/测试
- **THEN** 系统 SHALL 输出每只样本股票按原型分类的字段覆盖结果，作为交付判据

### Requirement: 与参考项目数据一致性验收（交付门槛二）

交付前，系统 SHALL 通过一致性校验：本数据接入层用 AKShare 对样本股票的取数结果，与参考项目 `ref/valueinvest` 的 `Stock.from_api`（同为 AKShare 源）的对应结果在**相对误差 0.1%** 内一致，财报口径**不放宽**。校验逻辑通过对比方式调用参考项目（仅用于验证），MUST NOT 在生产代码中 import `ref/`。跨数据源差异（如 AKShare vs Baostock）属正常，由选源优先级处理，不纳入本门槛。

#### Scenario: 关键字段与参考项目一致

- **WHEN** 对样本股票分别用本层（AKShare）与 `ref/valueinvest`（AKShare）取数，并对比同名关键字段（如当前价、EPS、BVPS、净利润、营收、股息率等）
- **THEN** 各字段相对误差 SHALL ≤ 0.1%，否则标记为不一致并报告具体字段与数值

#### Scenario: 缺失语义归一化

- **WHEN** 参考侧以 0 填充而本侧标注为缺失（None）
- **THEN** 校验 SHALL 将该字段归一化为"参考缺失"，不计入差异，但在报告中标注

#### Scenario: 一致性校验不依赖 ref 的运行时 import

- **WHEN** 生产数据接入层代码运行
- **THEN** 其 SHALL NOT import `ref/` 下任何模块；参考项目仅在独立的验证脚本/测试中被调用用于对比

### Requirement: Baostock 季频财务有效参数

Baostock fetcher 在查询季频财务接口（profit/growth/cashflow/balance）时 SHALL 使用有效的 `(year, quarter)`（quarter 为 1–4）。当最近季度无数据时，系统 SHALL 向前回溯有限个季度直至取得数据或明确标注缺失，MUST NOT 使用 `year=0, quarter=0`。

#### Scenario: 季频财务写入非空 eps 或 roe

- **WHEN** 对 Baostock 支持的 A 股（如 `600519`）执行 `fetch_fundamentals` 且网络正常
- **THEN** 返回的 `FetchResult.data` SHALL 包含 `eps` 或 `roe` 至少一项非 None，或于 `missing_fields` 中明确列出失败原因

#### Scenario: 无效季度参数被拒绝

- **WHEN** Baostock API 因参数无效返回错误
- **THEN** fetcher SHALL 尝试下一有效季度或返回带 `error`/`missing_fields` 的结果，不得静默仅返回行情价并假装基本面成功

### Requirement: AKShare 取数失败可观测

AKShare fetcher 在遇到空响应或 JSON 解析失败时 SHALL 记录可诊断错误，并在 `FetchResult.error` 或等价字段中返回，以便 E2E 与 failover 区分「网络/API 失败」与「字段缺失」。

#### Scenario: 空响应不导致未捕获异常

- **WHEN** AKShare 接口返回空 body 或非 JSON
- **THEN** fetcher SHALL 返回 `ok=False` 的 FetchResult 或带 `error` 的结果，Provider 可 failover 至下一源

### Requirement: Tushare Pro 数据源接入

系统 SHALL 提供 `TushareFetcher`（`source_name=tushare`），通过 Tushare Pro API 获取 A 股行情与基本面，映射至 `FetchResult.data` 与 `StockData` 字段。Fetcher SHALL 实现 `fetch_quote`、`fetch_fundamentals`、`fetch_all(code, exchange)`，缺失字段用 None 并列入 `missing_fields`。

#### Scenario: 合法 Token 下取数成功

- **WHEN** 配置提供有效 Tushare Token 且请求合法 A 股代码（如 `600519`）
- **THEN** `fetch_all` SHALL 返回 `ok=True` 的 FetchResult，且 `data` 含至少一项行情或基本面非空字段

#### Scenario: API 错误可观测

- **WHEN** Tushare API 返回错误或超积分限制
- **THEN** FetchResult SHALL 携带可诊断 `error` 或 `missing_fields`，不得未捕获异常导致 Provider 中断

#### Scenario: 字段映射遵循 None 语义

- **WHEN** Tushare 某字段无数据或为 NaN
- **THEN** 该字段 SHALL 为 None 而非 0，并视情况加入 `missing_fields`

### Requirement: Tushare Token 配置与安全

Tushare Token SHALL 从以下来源读取（优先级从高到低）：`data_sources.enabled` 中 tushare 条目的 `token` 字段 → 环境变量 `TUSHARE_TOKEN`。Token MUST NOT 写入 Git 跟踪文件；`config/app.example.yaml` 仅展示占位说明。

#### Scenario: 从 app.yaml 读取 Token

- **WHEN** `config/app.yaml` 中 tushare 配置了非空 token
- **THEN** TushareFetcher SHALL 使用该 token 初始化 pro_api

#### Scenario: 从环境变量读取 Token

- **WHEN** app.yaml 未填 token 但设置了 `TUSHARE_TOKEN`
- **THEN** TushareFetcher SHALL 使用环境变量 token 初始化

#### Scenario: Token 不入库

- **WHEN** 任意采集或持久化流程运行
- **THEN** Token SHALL NOT 写入 SQLite 或日志明文（允许 debug 级别掩码输出）

### Requirement: 离线价值面数据重建
`StockDataProvider` SHALL 提供 `get_stock_data_offline(code: str) -> StockData | None` 方法，从 `StockSnapshotRepo.find_by_code(code)` 读取所有来源的历史快照，合并为 `StockData` 对象，不触发任何网络请求。

合并字段优先级 SHALL 与联网路径 `_merge_result()` 保持一致（高优先级 source 的字段不被低优先级覆盖）。

#### Scenario: 有快照数据时离线重建
- **WHEN** `get_stock_data_offline("600519")` 被调用且 `StockSnapshotRepo` 有该代码的快照
- **THEN** 返回合并后的 `StockData` 对象，字段优先级与联网路径一致
- **THEN** 不调用任何外部 API

#### Scenario: 无快照数据时返回 None
- **WHEN** `get_stock_data_offline("600519")` 被调用且 `StockSnapshotRepo` 无该代码的数据
- **THEN** 返回 `None`，不抛异常

#### Scenario: 离线重建结果与联网结果字段一致性
- **WHEN** 对同一代码执行联网 `get_stock_data()` 后再执行 `get_stock_data_offline()`
- **THEN** 关键字段（eps、roe、current_price 等）的值 SHALL 一致（偏差在浮点精度内）

### Requirement: 离线快照按来源分层选快照（行情 vs 财报）
`get_stock_data_offline()` 在同 `source` 存在多条 `report_period` 快照时，SHALL 对字段类型分层选源：
- **行情字段**：选取该 source 下 `fetched_at` 最新的一条快照（通过 `_pick_quote_snapshot`），经 `_merge_result` 合并非财报字段。
- **财报字段**（`FINANCIAL_STATEMENT_FIELDS`）：优先选取 `report_period` 以 `1231` 结尾的最新年报快照（通过 `_pick_financial_snapshot`）；若无年报快照，fallback 到行情快照。年报财报字段 SHALL 经 `_merge_offline_financials` 覆写，且 MUST NOT 覆盖更高优先级 source 已写入的同名字段。

#### Scenario: 同 source 多 report_period — 行情取最新、FCF 取年报
- **WHEN** `tushare` 同时存在 `report_period=20260331`（fetched_at 较新，fcf=263亿）与 `report_period=20251231`（fcf=584亿）
- **THEN** 离线合并 SHALL 使用 20260331 的 `current_price`（若更新），但 `fcf=584亿` 来自 20251231 年报

#### Scenario: 同 source 仅行情快照与年报快照
- **WHEN** `tushare` 存在 `report_period=20260628`（仅行情，fetched_at 较新）与 `report_period=20251231`（含完整财报）
- **THEN** 离线合并 SHALL 使用 20260628 的 `current_price` 与 20251231 的财报字段，`revenue`/`total_assets`/`fcf` 非空

#### Scenario: 无年报快照时 fallback
- **WHEN** 某 source 仅有季报快照（无 `1231` report_period）
- **THEN** 财报字段 fallback 到 `fetched_at` 最新快照，系统不报错

#### Scenario: 低优先级源不得覆盖高优先级源年报 FCF
- **WHEN** `tushare`（priority=1）年报 fcf=584亿已合并，`baostock`（priority=2）仅有非年报估算 fcf=239亿
- **THEN** 最终 `StockData.fcf` SHALL 保持 584亿，来源 `tushare`

### Requirement: Tushare 财报字段覆盖 Baostock 估算值
`StockDataProvider._merge_fields()` 对 `FINANCIAL_STATEMENT_FIELDS`（`revenue`、`fcf`、`capex`、`net_debt`、`ebit`、`depreciation`、`total_assets`、`total_liabilities`、`bvps`、`roic`、`net_income`）SHALL 允许 Tushare 的非 None 值通过 `override_field()` 覆盖 Baostock 的估算值，即使 Baostock 优先级更高且已写入该字段。

#### Scenario: Tushare revenue 覆盖 Baostock 估算
- **WHEN** Baostock 先写入 `revenue=1000亿`（CFOToOR 估算），Tushare 后写入 `revenue=1688亿`（年报）
- **THEN** 合并后 `StockData.revenue = 1688亿`，`field_sources["revenue"] = "tushare"`

### Requirement: Tushare 财报接口优先取年报
`TushareFetcher._fetch_latest()` 对 `income`、`cashflow`、`balancesheet`、`fina_indicator` SHALL 优先返回 `end_date` 以 `1231` 结尾的最新年报行；无年报时取最近一期季报。

#### Scenario: 存在年报与季报
- **WHEN** `income` 返回含 `20260331` 季报与 `20231231` 年报
- **THEN** SHALL 选用 `20231231` 年报写入 `revenue` 等字段

### Requirement: TTM EPS 推导覆写季报单季 EPS
在所有数据源 merge 完成后，`StockDataProvider` SHALL 检查 `stock.net_income` 与 `stock.shares_outstanding` 是否均为有效正值；若是，SHALL 用 `net_income / shares_outstanding` 计算 TTM EPS 并覆写 `stock.eps`，来源标注为 `"derived:ttm"`。原始 `fina_indicator.eps`（季报单季值）不再直接作为估值输入。

#### Scenario: 年报净利润与总股本均可用时推导 TTM EPS
- **WHEN** merge 完成后 stock.net_income=82320000000（823.2亿），stock.shares_outstanding=1250000000（12.5亿股）
- **THEN** stock.eps SHALL 被覆写为 65.86，stock.field_sources["eps"] = "derived:ttm"

#### Scenario: net_income 缺失时保留原始 EPS
- **WHEN** merge 完成后 stock.net_income=None，stock.eps=21.76（fina_indicator季报值）
- **THEN** stock.eps 保持 21.76 不变，不进行 TTM 推导

#### Scenario: TTM EPS 推导对离线模式同样生效
- **WHEN** 调用 get_stock_data_offline() 且快照中有 net_income 与 shares_outstanding
- **THEN** TTM EPS 推导逻辑 SHALL 同样执行，结果与在线模式一致

### Requirement: historical_pb 字段来源从 None 变为 Tushare 提供
`StockDataProvider` merge 层 SHALL 将 Tushare 返回的 `historical_pb` 合并到 `StockData.historical_pb`，优先级高于 Baostock（Baostock 无法提供 PB 序列）。

#### Scenario: Tushare 提供 historical_pb 后字段不再为 None
- **WHEN** Tushare 启用且 `daily_basic` 成功拉取 5 年 PB 序列
- **THEN** `StockData.historical_pb` 不为 None，`field_sources["historical_pb"] = "tushare"`

#### Scenario: Tushare 不可用时 historical_pb 为 None
- **WHEN** 仅 Baostock 启用
- **THEN** `StockData.historical_pb` 保持 None，不报错，pb_relative = Not Applicable

### Requirement: prior_* 字段从始终 None 变为可由 Tushare 提供
`StockDataProvider` merge 层 SHALL 将 Tushare 返回的 `prior_*` 字段合并到 `StockData` 对应属性。这些字段不参与 `_derive_*` 推导；直接来自 Tushare API。`StockSnapshot` ORM SHALL 持久化 6 个 prior 字段并在离线重建时回放。

#### Scenario: Tushare 提供 prior_roa 后字段非空
- **WHEN** sync 600519，Tushare 成功返回 prior_roa
- **THEN** `StockData.prior_roa is not None`，`field_sources["prior_roa"] = "tushare"`

#### Scenario: 仅 Baostock 时 prior_* 为 None
- **WHEN** Tushare 未启用
- **THEN** 所有 `prior_*` 字段为 None，Piotroski/Beneish 部分指标退化为 Not Applicable

### Requirement: 银行专项字段从始终 None 变为可由 Tushare 提供
`StockDataProvider` merge 层 SHALL 将 Tushare 返回的 `net_interest_margin`、`npl_ratio`、`provision_coverage` 合并到 `StockData` 对应属性（优先级：Tushare > Baostock；Baostock 无此字段，不冲突）。

#### Scenario: sync 601398 后银行专项字段非空
- **WHEN** Tushare 启用且 601398 `fina_indicator` 含 `netint_margin`
- **THEN** `StockData.net_interest_margin` 不为 None，可被 bank 原型估值方法使用

#### Scenario: 银行方法缺少 NIM 时优雅降级
- **WHEN** `net_interest_margin = None`（接口无权限或无数据）
- **THEN** 依赖 NIM 的指标评分降级为 Not Applicable，聚合不崩溃

### Requirement: industry 字段从 Tushare stock_basic 提供
`StockDataProvider` merge 层 SHALL 将 Tushare `stock_basic.industry` 合并到 `StockData.industry`，供 `PrototypeRouter` 行业分类使用；`StockSnapshot` ORM SHALL 持久化 `industry` 并在离线重建时回放。

#### Scenario: sync 后 industry 非空
- **WHEN** Tushare 启用且 `stock_basic` 返回 `industry="银行"`
- **THEN** `StockData.industry = "银行"`，`field_sources["industry"] = "tushare"`

### Requirement: Baostock 不产出低可信财报字段
`BaostockFetcher` 在 fundamentals / `fetch_all` 结果中 MUST NOT 写入下列字段的有效数值（可省略键或显式 missing）：`revenue`、`fcf`、`capex`、`net_debt`、`ebit`、`depreciation`、`total_assets`、`total_liabilities`、`bvps`、`roic`、`net_income`（与代码中 `FINANCIAL_STATEMENT_FIELDS` 保持同步）。在 `tushare` priority 高于 `baostock` 的配置下，这些字段 SHALL 由 Tushare（若提供）主导。

#### Scenario: Baostock 输出不含财报特例字段
- **WHEN** 仅解析 Baostock `FetchResult.data`
- **THEN** 上述字段集合不出现有效 float 值

#### Scenario: tushare 优先时行业等来自 tushare
- **WHEN** 配置 tushare(1)+baostock(2) 且 Tushare 提供 `industry`
- **THEN** 合并后 `field_sources`（或等价元数据）显示 `industry` 来自 tushare

### Requirement: 默认选源叙述对齐 Tushare + Baostock
规范层对「默认启用哪些源」的描述 SHALL 与产品目标态一致：默认启用 `tushare`（有 token 时）与 `baostock`；AKShare 为可选遗留源，MUST 显式配置才启用。免 token 优先的历史默认叙述（默认仅 AKShare/Baostock）在本 change 后不再作为运行默认。

#### Scenario: 文档与 example 一致
- **WHEN** 阅读 `app.example.yaml` 与 value-data-provider 相关说明
- **THEN** 默认示例为 tushare priority=1、baostock priority=2，akshare 不在默认 enabled 中

