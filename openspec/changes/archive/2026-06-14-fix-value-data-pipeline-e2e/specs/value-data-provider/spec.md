## MODIFIED Requirements

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

## ADDED Requirements

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
