# tech-kline-provider Specification

## Purpose
TBD - created by archiving change add-tech-analyzer-core. Update Purpose after archive.
## Requirements
### Requirement: K 线数据获取（Baostock 主，AKShare 备）
`KlineProvider` 的 `get_kline(code, days, use_realtime=False, offline=False, persist_today=False)` 方法 SHALL 通过 DataFetcherRouter / FailoverStrategy，按配置 `priority` 依次调用已启用源上可用的 `fetch_kline`（或等价），**首次成功即停止**；全部失败时 SHALL 抛出 `KlineUnavailableError`。系统 MUST NOT 无条件实例化 `BaostockFetcher()` 或硬编码「仅 Baostock→AKShare」顺序；未启用的源 MUST NOT 被调用。Failover 链 SHALL 能调用已启用的 `TushareFetcher.fetch_kline`；当更高 priority 源失败或未启用时，Tushare 成功即视为 K 线获取成功，缓存契约（列名、SQLite upsert）保持不变。

当 `offline=True` 时，SHALL 跳过所有外部调用，仅读缓存（见「offline 模式」需求）。

当 `use_realtime=True` 时，SHALL 在正常流程完成后调用经 Router 注入的 `RealtimeOverlayProvider.overlay()` 将实时价格叠加到 DataFrame 末端。

当 `persist_today=True` 且 `use_realtime=True` 时，SHALL 将当日行写入 `KlineRepo`（upsert）。

返回的 DataFrame SHALL 包含列：`date`（str，YYYY-MM-DD）、`open`、`high`、`low`、`close`、`volume`（均为 float），按 `date` 升序排列，且为前复权数据。返回签名为 `(DataFrame, list[str], str)`，第三元素为 `quote_mode`（`"eod"` / `"realtime"` / `"eod_fallback"`）。实现 SHOULD 在日志或进度回调中暴露实际 `kline_source`。

#### Scenario: 最高 priority 源正常返回（EOD 模式）
- **WHEN** `get_kline("600519", days=90)` 被调用且最高 priority 且支持 K 线的源可用
- **THEN** 返回包含约 60 行（交易日）的 DataFrame，列完整，按日期升序排列，`quote_mode = "eod"`

#### Scenario: 实时叠加模式
- **WHEN** `get_kline("600519", days=90, use_realtime=True)` 被调用
- **THEN** 末端行为当日实时价格，`quote_mode = "realtime"` 或 `"eod_fallback"`

#### Scenario: 高优先级失败自动切换下一源
- **WHEN** `get_kline("600519", days=90)` 被调用且最高 priority 源抛出异常、下一启用源成功
- **THEN** 返回相同格式的 DataFrame，且不调用未启用源

#### Scenario: Tushare 作为 failover 成功
- **WHEN** Baostock K 线失败且 Tushare 启用并成功
- **THEN** 返回合法 OHLCV DataFrame，`offline=False` 路径可写入缓存

#### Scenario: 全部启用源均失败
- **WHEN** `get_kline("600519", days=90)` 被调用且所有启用且支持 K 线的源均失败
- **THEN** 抛出 `KlineUnavailableError`，携带失败原因信息

#### Scenario: 未启用 AKShare 时不调用
- **WHEN** 配置未启用 `akshare` 且 Baostock（或其他启用源）成功
- **THEN** 不实例化、不调用 `AKShareFetcher`

#### Scenario: offline 仍不联网
- **WHEN** `offline=True`
- **THEN** 不调用 Tushare 或任何外部源，仅读 `KlineRepo`

### Requirement: K 线本地 SQLite 缓存
`KlineProvider` SHALL 使用 `KlineRepo` 将历史 K 线（日期 < 当日）持久化到 SQLite `kline` 表（`code + trade_date` 联合主键）。每次调用 `get_kline()` 时 SHALL 先查询缓存，仅对缺失的历史日期发起 API 请求。当日数据 SHALL 始终实时拉取，不写入缓存。

#### Scenario: 历史数据全部命中缓存
- **WHEN** 所请求历史日期均已在 `kline` 表中存在
- **THEN** 直接从 DB 返回，不调用任何外部 API（当日数据仍实时拉取）

#### Scenario: 部分历史缓存命中
- **WHEN** 部分历史日期在缓存中，其余缺失
- **THEN** 仅对缺失日期调用 API，获取后写入 `kline` 表，再合并返回

#### Scenario: 缓存完全为空（首次运行）
- **WHEN** `kline` 表中无该股票任何数据
- **THEN** 调用 API 拉取完整区间，写入所有历史日期，返回完整 DataFrame

---

### Requirement: 历史数据空洞检测与自动回填
当程序多日未运行时，`KlineProvider` SHALL 自动识别 DB 中缺失的历史交易日（空洞）并批量拉取回填，无需外部调用方感知此过程。空洞识别 SHALL 基于 API 返回的实际交易日集合与已缓存日期集合的差集，不依赖独立的交易日历表。

#### Scenario: 程序停运后再次运行（空洞场景）
- **WHEN** DB 中最新记录为 6/16，今日为 6/21，`get_kline("600519", 90)` 被调用
- **THEN** 自动识别 6/17~6/20 为缺失交易日，批量拉取并写入 DB，返回含 6/17~6/20 的完整序列

#### Scenario: 空洞拉取失败且缺口超过 5 日
- **WHEN** 空洞 > 5 个交易日且 API 拉取失败
- **THEN** 返回当前可用数据（不报错阻塞），`result.warnings` 中包含「K 线数据存在缺口，指标计算可能不准确」

#### Scenario: 非交易日不作为空洞
- **WHEN** 请求区间内包含周末或节假日
- **THEN** 这些日期不被识别为空洞（API 本身不返回这些日期，差集计算自动排除）

---

### Requirement: offline 模式（仅读缓存）
`get_kline(code, days, offline: bool = False)` 新增 `offline` 参数。当 `offline=True` 时，SHALL 仅从 `KlineRepo` 查询缓存，不调用任何外部 API 或 `RealtimeOverlayProvider`。

#### Scenario: offline=True 且缓存有数据
- **WHEN** `get_kline("600519", 90, offline=True)` 被调用且 KlineRepo 有缓存
- **THEN** 返回缓存 DataFrame，不触发任何网络调用，`quote_mode = "eod"`

#### Scenario: offline=True 且缓存为空
- **WHEN** `get_kline("600519", 90, offline=True)` 被调用且 KlineRepo 无数据
- **THEN** 返回空 DataFrame（0 行），warnings 含「无缓存数据」，`quote_mode = "eod"`
- **THEN** 不抛异常

### Requirement: persist_today 模式（sync 路径写当日行）
`get_kline()` 内部在 `use_realtime=True` 且 `persist_today=True` 时，SHALL 将最终末行（实时叠加后的当日行）写入 `KlineRepo`（upsert 语义，`trade_date = today`）。

**注**：`persist_today=False` 为默认值，保持现有行为（当日不写缓存）不变。

#### Scenario: sync --realtime 后当日行持久化
- **WHEN** `get_kline("600519", 90, use_realtime=True, persist_today=True)` 被调用
- **THEN** 当日行写入 `kline` 表（upsert）
- **THEN** 后续 `get_kline("600519", 90, offline=True)` 能读到该行

#### Scenario: persist_today=False（默认）不写当日行
- **WHEN** `get_kline("600519", 90, use_realtime=True)` 被调用（默认 persist_today=False）
- **THEN** 当日行不写入缓存，现有行为不变

