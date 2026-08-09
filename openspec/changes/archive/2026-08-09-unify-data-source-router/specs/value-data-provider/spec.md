## MODIFIED Requirements

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
