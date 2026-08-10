## ADDED Requirements

### Requirement: AKShare 筹码分布数据获取
`AKShareFetcher.fetch_chip_distribution(code)` SHALL 调用 `ak.stock_cyq_em(symbol=code, adjust="qfq")`，返回标准化列名（`trade_date`/`winner_ratio`/`avg_cost`/`concentration_90`/`concentration_70`/`cost_90_low`/`cost_90_high`/`cost_70_low`/`cost_70_high`）的历史序列 DataFrame。复权口径 SHALL 与现有 `fetch_kline()` 一致（前复权）。接口返回空或调用异常时 SHALL 抛出 `DataProviderError`，不静默返回空 DataFrame。

#### Scenario: 正常获取筹码分布历史序列
- **WHEN** `fetch_chip_distribution("600519")` 被调用且 AKShare 返回非空数据
- **THEN** 返回 DataFrame 包含标准化列名，`trade_date` 为 `YYYY-MM-DD` 字符串，数值列为 float

#### Scenario: AKShare 接口异常
- **WHEN** `ak.stock_cyq_em` 抛出异常或返回空 DataFrame
- **THEN** `fetch_chip_distribution` 抛出 `DataProviderError`

---

### Requirement: ChipDistributionProvider 缓存与主键
`ChipDistributionProvider` SHALL 通过 `ChipDistributionRepo` 将 `fetch_chip_distribution()` 返回的历史行按 `(code, trade_date)` 复合主键 upsert 到 SQLite `chip_distribution` 表；`get_latest(code, offline=False)` SHALL 返回最新一行数据（dict 或 `None`）与 `warnings` 列表。`offline=True` 时 SHALL 只读本地缓存，不触发任何网络调用。

#### Scenario: 联网模式首次拉取并缓存
- **WHEN** `get_latest("600519", offline=False)` 被调用且本地无缓存
- **THEN** 调用 `fetch_chip_distribution()`，将返回历史行写入 `chip_distribution` 表，返回最新一行

#### Scenario: 离线模式只读缓存
- **WHEN** `get_latest("600519", offline=True)` 被调用
- **THEN** 不调用任何 AKShare 接口，仅从 `ChipDistributionRepo` 查询最新一行；若无缓存返回 `(None, ["无缓存数据"])`

#### Scenario: 获取失败时优雅降级
- **WHEN** `offline=False` 且 `fetch_chip_distribution()` 抛出 `DataProviderError`，但本地有历史缓存
- **THEN** 返回本地缓存中的最新一行，`warnings` 追加拉取失败原因

#### Scenario: 无缓存且获取失败
- **WHEN** `offline=False` 且 `fetch_chip_distribution()` 失败，且本地无任何缓存
- **THEN** 返回 `(None, warnings)`，`warnings` 包含失败原因，不抛出异常

---

### Requirement: ChipStatus 筹码集中度分类
`classify_chip_status(concentration_90, params)` SHALL 基于 90% 成本集中度数值，按 `IndicatorParams` 中可配置的阈值（`chip_concentration_strong`、`chip_concentration_weak`）返回 `ChipStatus` 枚举（`HIGHLY_CONCENTRATED` / `CONCENTRATED` / `NORMAL` / `DISPERSED`）。`concentration_90` 为 `None` 时 SHALL 返回 `None`（不猜测默认值）。

#### Scenario: 高度集中
- **WHEN** `concentration_90 <= chip_concentration_strong`（默认 10.0）
- **THEN** 返回 `ChipStatus.HIGHLY_CONCENTRATED`

#### Scenario: 筹码分散
- **WHEN** `concentration_90 >= chip_concentration_weak`（默认 30.0）
- **THEN** 返回 `ChipStatus.DISPERSED`

#### Scenario: 输入缺失
- **WHEN** `concentration_90` 为 `None`
- **THEN** 返回 `None`，不抛出异常、不返回默认枚举值
