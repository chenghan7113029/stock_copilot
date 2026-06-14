## MODIFIED Requirements

### Requirement: 价值面数据持久化到 SQLite（禁止本地 csv）

系统 SHALL 将采集到的 A 股价值面数据持久化到关系型数据库，V1 使用 SQLite。系统 MUST NOT 将数据写为本地 csv / Excel 等散落文件。持久化 SHALL 通过 SQLAlchemy 实现。

在网络拉取阶段，系统 MUST NOT 长时间持有同一 SQLAlchemy Session 的写事务；SHALL 在 fetch 完成后再执行 upsert 与 commit，以避免 SQLite `database is locked`。

#### Scenario: 采集结果落库

- **WHEN** 数据接入层成功获取某股票某数据源的数据
- **THEN** 系统 SHALL 将其写入 SQLite，且不产生本地 csv 文件

#### Scenario: 禁止 csv 落地

- **WHEN** 任何采集/持久化流程运行
- **THEN** 系统 SHALL NOT 调用 `to_csv` 或将原始数据写入本地散文件

#### Scenario: 单进程 E2E 无锁失败

- **WHEN** 在单进程内顺序执行 fetch 与 upsert（标准 E2E 或采集脚本）
- **THEN** upsert SHALL 成功 commit，不得因 fetch 期间占锁而抛出 `database is locked`

## ADDED Requirements

### Requirement: 快照读回查询

系统 SHALL 提供从 SQLite 按股票代码读回已持久化快照的能力（Repository 或等价 API），支持列出最近 N 条或按 `(code, source)` 查询，供 E2E 与脚本展示。

#### Scenario: 按 code 读回多条来源

- **WHEN** 某 code 已有 AKShare 与 Baostock 两条快照
- **THEN** 读回 API SHALL 返回两条记录且 `source` 字段可区分

#### Scenario: 读回字段与写入一致

- **WHEN** upsert 写入了 `eps` 与 `current_price`
- **THEN** 读回同一 `(code, source, report_period)` 的记录 SHALL 包含相同非空字段值
