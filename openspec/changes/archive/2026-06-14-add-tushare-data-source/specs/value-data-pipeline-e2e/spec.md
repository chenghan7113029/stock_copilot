## ADDED Requirements

### Requirement: Tushare 落库读回验收

当配置启用 Tushare 且 Token 有效时，系统 SHALL 提供网络验收：对 `config/value_data_validation_stocks.yaml` 中全部样本股票执行 fetch → upsert → read，验证 `source=tushare` 快照存在且含非空基本面或行情字段。

#### Scenario: 样本清单全量 Tushare 落库

- **WHEN** 在具备网络与有效 Token 的环境运行 Tushare E2E 测试
- **THEN** 清单内每只股票的 SQLite 读回 SHALL 至少包含一条 `source=tushare` 的快照记录

#### Scenario: 读回字段非空

- **WHEN** Tushare fetch 对某样本股成功
- **THEN** 对应 `source=tushare` 快照 SHALL 含 `current_price` 或 `eps` 至少一项非 NULL，且与 FetchResult 写入值一致

#### Scenario: 无 Token 时跳过而非失败

- **WHEN** 未配置 Tushare Token 运行 Tushare E2E 测试
- **THEN** 测试 SHALL 被 skip 并说明原因，不得导致 CI/本地 pytest 失败

#### Scenario: 与现有 E2E 共存

- **WHEN** 同时启用 AKShare、Baostock、Tushare
- **THEN** 同一 `code` 的读回 SHALL 保留多条按 `source` 区分的记录，含独立的 `tushare` 行
