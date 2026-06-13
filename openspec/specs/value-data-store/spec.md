## ADDED Requirements

### Requirement: 价值面数据持久化到 SQLite（禁止本地 csv）

系统 SHALL 将采集到的 A 股价值面数据持久化到关系型数据库，V1 使用 SQLite。系统 MUST NOT 将数据写为本地 csv / Excel 等散落文件。持久化 SHALL 通过 SQLAlchemy 实现。

#### Scenario: 采集结果落库

- **WHEN** 数据接入层成功获取某股票某数据源的数据
- **THEN** 系统 SHALL 将其写入 SQLite，且不产生本地 csv 文件

#### Scenario: 禁止 csv 落地

- **WHEN** 任何采集/持久化流程运行
- **THEN** 系统 SHALL NOT 调用 `to_csv` 或将原始数据写入本地散文件

### Requirement: 数据库后端可配置（预留 MySQL）

数据库后端 SHALL 由配置（`config/app.yaml` 的 `db.url`）决定，默认 SQLite 文件。切换到其他后端（如 MySQL）SHALL 仅需修改配置，不改业务代码。持久化实现 SHALL 仅使用 SQLAlchemy 通用能力，避免 SQLite 专有 SQL，以保证可迁移。

#### Scenario: 默认 SQLite

- **WHEN** 未显式配置 `db.url`
- **THEN** 系统 SHALL 使用默认 SQLite 文件作为存储后端

#### Scenario: 切换后端仅改配置

- **WHEN** 将 `db.url` 改为 MySQL 连接串并提供建表
- **THEN** 同一持久化代码 SHALL 可在 MySQL 后端运行，无需修改业务逻辑

### Requirement: 来源维度的原始快照存储

系统 SHALL 按数据源维度保留原始快照：每条记录以 `(股票代码, 数据源, 报告期或采集时间)` 唯一标识，不同数据源对同一股票的数据 SHALL 独立成行而非互相覆盖。系统 SHALL 支持按数据源查询与逐源对比。

#### Scenario: 多源数据独立留存

- **WHEN** 同一股票分别由 AKShare 与 Baostock 采集
- **THEN** 两源数据 SHALL 各自成行留存，可分别查询，互不覆盖

#### Scenario: 同源重复采集按唯一键 upsert

- **WHEN** 同一 `(股票代码, 数据源, 报告期/采集时间)` 再次采集
- **THEN** 系统 SHALL 按唯一键更新（upsert），不产生重复行

#### Scenario: 按来源查询

- **WHEN** 指定股票代码与数据源查询
- **THEN** 系统 SHALL 返回该源对应的快照记录及其来源/时效元数据
