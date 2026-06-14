## Purpose

A 股价值面数据接入层：统一数据模型、多源 fetcher 管理与配置驱动选源，支撑 V1 三原型估值方法的确定性取数。

## Requirements

### Requirement: 统一 A 股股票估值数据模型

系统 SHALL 提供一个统一的股票估值数据模型，覆盖 MRD §7 中 V1 三原型（银行 / 高股息·类债 / 高质量价值成长）所有估值方法所需的字段，包括：基础行情（当前价、总股本、市值）、每股指标（EPS、BVPS、每股分红）、盈利（营收、净利润、ROE/ROIC）、现金流（自由现金流、经营现金流、capex）、资产负债（总资产、总负债、净负债、股东权益）、分红（股息率、派息率、分红历史）、历史估值序列（历史 PE / PB）、质量与风险明细（Altman-Z / Piotroski-F / Beneish-M 所需输入）。

该模型为确定性数据结构，MUST NOT 由 LLM 生成或修改。

#### Scenario: 模型字段覆盖 V1 方法需求

- **WHEN** 价值面估值方法（PB、剩余收益、DDM、DCF、EPV、Owner Earnings、Graham、相对估值、Altman-Z、Piotroski-F、Beneish-M）声明其输入字段
- **THEN** 数据模型 SHALL 为每个字段提供对应属性，且类型明确（数值/序列/日期）

#### Scenario: 数据模型不可由 LLM 改写

- **WHEN** 数据模型实例被传入下游
- **THEN** 其数值字段 SHALL 仅来自 data_provider 的确定性取数，不经任何 LLM 环节

### Requirement: 多数据源独立管理与配置驱动选源

系统 SHALL 以独立 fetcher 管理多个 A 股数据源，V1 至少接入 AKShare 与 Baostock（均免 token）。系统 SHALL 通过配置（`config/app.yaml` 的 `data_sources`）指定启用哪些数据源及其优先级。选源优先级遵循：**无需 token > 有 token 但免费 > 有 token 且收费**；系统 SHALL 默认仅启用免 token 源，需 token 的源 MUST 显式配置后才启用。取数时 SHALL 按优先级选源并在某源失败时自动 failover 到下一源。

所有 fetcher 的 `fetch_all` 方法 SHALL 使用统一签名 `(code: str, exchange: str) -> FetchResult`，与 `fetch_quote` / `fetch_fundamentals` 一致；SourceManager 与 StockDataProvider MUST NOT 因签名不一致导致取数异常。

#### Scenario: 默认仅用免 token 源

- **WHEN** 未配置任何 token 且请求某 A 股股票数据
- **THEN** 系统 SHALL 使用免 token 源（AKShare/Baostock）完成取数，不因缺少 token 而失败

#### Scenario: 按配置启用数据源

- **WHEN** 配置中仅启用部分数据源
- **THEN** 系统 SHALL 只从已启用的数据源采集，未启用的源不被调用

#### Scenario: 按优先级选源并记录命中源

- **WHEN** 同一字段可由多个已启用数据源提供
- **THEN** 系统 SHALL 优先采用优先级更高的数据源，高优先级已提供的字段不被低优先级覆盖，并在元数据中记录每字段实际命中的源

#### Scenario: 高优先级源失败时自动 failover

- **WHEN** 优先级最高的数据源对某股票取数失败
- **THEN** 系统 SHALL 自动尝试下一优先级数据源，直至成功或全部耗尽

#### Scenario: fetch_all 接口一致

- **WHEN** SourceManager 或 StockDataProvider 调用任一 fetcher 的 `fetch_all`
- **THEN** 调用 SHALL 使用 `(code, exchange)` 且不得因参数个数错误而中断整条取数链路

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
