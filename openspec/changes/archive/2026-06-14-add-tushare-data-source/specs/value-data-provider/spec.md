## MODIFIED Requirements

### Requirement: 多数据源独立管理与配置驱动选源

系统 SHALL 以独立 fetcher 管理多个 A 股数据源，V1 至少接入 AKShare 与 Baostock（均免 token），并 MAY 接入 Tushare Pro（需 Token，有 token 但免费档）。系统 SHALL 通过配置（`config/app.yaml` 的 `data_sources`）指定启用哪些数据源及其优先级。选源优先级遵循：**无需 token > 有 token 但免费 > 有 token 且收费**；系统 SHALL 默认仅启用免 token 源，需 token 的源 MUST 显式配置且提供有效 Token 后才实例化。取数时 SHALL 按优先级选源并在某源失败时自动 failover 到下一源。

所有 fetcher 的 `fetch_all` 方法 SHALL 使用统一签名 `(code: str, exchange: str) -> FetchResult`，与 `fetch_quote` / `fetch_fundamentals` 一致；SourceManager 与 StockDataProvider MUST NOT 因签名不一致导致取数异常。

Provider 对每个已实例化的 fetcher SHALL 分别调用并独立落库（来源维度），不因优先级而跳过低位源的持久化。

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

#### Scenario: Tushare 无 Token 时不实例化

- **WHEN** 配置启用 `tushare` 但 token 为空且环境变量 `TUSHARE_TOKEN` 未设置
- **THEN** 系统 SHALL 跳过 TushareFetcher 实例化并记录 warning，AKShare/Baostock 仍正常工作

## ADDED Requirements

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
