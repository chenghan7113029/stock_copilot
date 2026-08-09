## ADDED Requirements

### Requirement: 配置驱动的 DataFetcherRouter
系统 SHALL 提供统一的数据源 Router（扩展现有 `SourceManager` 或新建等价入口），从 `config/app.yaml` 的 `data_sources` 读取 `enabled` 与 `priority`，仅实例化已启用且凭证满足的 fetcher，并按 priority 升序（数值越小优先级越高）排序。Fetcher 类上的默认 `priority` 属性 MUST NOT 作为运行态选源依据（仅可在 config 缺失字段时作文档化回退）。

#### Scenario: 仅启用 baostock
- **WHEN** 配置 `enabled` 仅包含 `baostock`
- **THEN** Router 仅实例化 BaostockFetcher，不实例化 AKShareFetcher 或 TushareFetcher

#### Scenario: 按 priority 排序
- **WHEN** 配置 `tushare` priority=1 且 `baostock` priority=2 且二者均启用
- **THEN** Router 返回的有序列表以 tushare 为先、baostock 为后

### Requirement: ValueMergeStrategy 字段级合并
对价值面取数，系统 SHALL 对所有已启用源各调用一次 `fetch_all`（或等价），并按 priority **从高到低**写入字段：高优先级已写入的非空字段 MUST NOT 被低优先级覆盖。系统 MUST NOT 再对 `FINANCIAL_STATEMENT_FIELDS` 执行「Tushare 无视已有值强制 override」特例。

#### Scenario: 高优先级先写不被覆盖
- **WHEN** 高优先级源已提供 `revenue`，低优先级源也提供不同 `revenue`
- **THEN** 合并结果保留高优先级值，并在字段来源元数据中记录该源

#### Scenario: 低优先级仅补缺失
- **WHEN** 高优先级源缺少 `industry`，低优先级源提供 `industry`
- **THEN** 合并结果采用低优先级的 `industry`

### Requirement: FailoverStrategy 逐源尝试
对 K 线、实时报价、筹码、情绪等非价值面合并数据项，系统 SHALL 按 priority 依次尝试支持该能力的 fetcher，**首次成功即停止**；全部失败时 SHALL 抛出既有错误类型或按该数据项既有降级约定处理，并 MUST 记录实际命中源标识（如 `kline_source` / `quote_source`）于日志或 sync 进度回调。

#### Scenario: 第一源失败第二源成功
- **WHEN** 最高 priority 源的 `fetch_kline` 失败，下一源成功
- **THEN** 返回成功 DataFrame，且命中源标识为第二源

#### Scenario: 全失败
- **WHEN** 所有支持 K 线的源均失败
- **THEN** 抛出 `KlineUnavailableError`（或该路径既有等价错误），不静默返回空成功

### Requirement: 未启用源零实例化
当某数据源未在 `enabled` 中时，系统 MUST NOT 实例化对应 Fetcher，MUST NOT 发起该源的网络调用（含实时、筹码、情绪路径）。`import akshare` 等模块导入 MAY 保留。

#### Scenario: disabled akshare 无网络
- **WHEN** `akshare` 未启用，且执行 K 线/实时/筹码/情绪相关单测（mock 环境）
- **THEN** `AKShareFetcher` 未被构造（可用 mock 断言）
