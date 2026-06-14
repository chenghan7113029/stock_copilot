## Purpose

价值面数据端到端管道验收：样本清单驱动、fetch→upsert→read 全链路、V1 全字段覆盖与缺口报告。

## Requirements

### Requirement: 验证样本股票清单（单一真源）

系统 SHALL 在 `config/value_data_validation_stocks.yaml` 维护 V1 E2E 与完备性验证用的样本股票清单（代码、名称、原型），与 MRD §2.1 自选样本对齐。E2E 测试与采集脚本 MUST 从该文件读取样本，不得硬编码分散在多处。

#### Scenario: 清单驱动 E2E

- **WHEN** 运行 E2E 或默认批量采集
- **THEN** 系统 SHALL 读取 `config/value_data_validation_stocks.yaml` 中的全部条目并逐股执行 fetch → upsert → read

#### Scenario: 增删样本仅改清单文件

- **WHEN** 产品侧调整 V1 验证样本
- **THEN** 维护者 SHALL 仅更新该 YAML 文件即可同步 E2E 与脚本，无需改多处测试常量

### Requirement: 端到端采集持久化读回

系统 SHALL 提供可复跑的端到端流程：加载配置 → 对清单内 A 股代码拉取多源数据 → 按来源维度 upsert 至 SQLite → 从数据库读回快照并可供校验/展示。该流程 MUST NOT 依赖临时内联脚本或手工 PYTHONPATH 拼装。

#### Scenario: 单股采集并读回

- **WHEN** 操作者执行项目提供的采集入口并指定清单内合法 A 股代码
- **THEN** 系统 SHALL 在配置的 SQLite 库中写入至少一条该代码的快照，且读回结果包含 `code`、`source` 与本次实际获取到的字段值

#### Scenario: 多源独立落库可读

- **WHEN** 配置启用 AKShare 与 Baostock 且两者均对同一股票返回成功
- **THEN** 读回 SHALL 显示按 `source` 区分的多条记录，而非互相覆盖为单行

### Requirement: V1 全字段覆盖验收（跨样本聚合）

E2E 验收 SHALL 以 MRD §7 / `field_requirements.py` 中 **V1 三原型（bank、high_dividend、value_growth）各自必需字段的并集** 为验收字段全集。不要求单条快照或单只股票包含全部字段，但 **整次验收运行**（清单内所有样本 × 已启用数据源，合并 Provider 层 `StockData` 或读回 DB 后的字段并集）SHALL 满足：

1. **并集覆盖**：验收字段全集中的每一个字段，至少在一只样本股上取得非空值，且该值经读回验证与写入一致；
2. **分原型覆盖**：每只样本股 SHALL 满足其绑定原型（见清单 `prototype`）的全部必需字段，或在该股报告中标为缺失并计入缺口报告；
3. **逐字段验证**：每个被判定为「已覆盖」的字段 MUST 在验收报告中列出「覆盖该字段的 code + source（或 field_sources）+ 实际值」，证明该字段已被实际取数并落库可读。

验收 MUST NOT 以「单股至少一个字段非空」作为通过条件。

#### Scenario: 跨样本并集覆盖全部 V1 必需字段

- **WHEN** 对清单内全部样本完成 fetch → upsert → read，且 AKShare/Baostock 至少一方可用
- **THEN** 验收报告 SHALL 表明 V1 三原型必需字段并集中的每个字段，均至少在一只股票上出现非空值，并附覆盖来源

#### Scenario: 单股满足所属原型必需字段

- **WHEN** 对清单中 `prototype: bank` 的样本（如 `601398`）执行验收
- **THEN** 该股合并后的数据 SHALL 满足 `get_required_fields("bank")` 中的全部必需字段，或缺口报告 SHALL 明确列出该股缺失的银行原型字段

#### Scenario: 单股不满足时 E2E 失败并报告

- **WHEN** 某样本股缺失其原型任一必需字段，且该字段在并集层面亦未被其他样本覆盖
- **THEN** E2E SHALL 失败，并在报告中列出缺失字段、影响的原型及已尝试的数据源

### Requirement: 不可获取字段缺口报告

若经当前已启用全部数据源（AKShare、Baostock 等）尝试后，某 V1 必需字段在清单内所有样本上均为空，系统 SHALL 生成 **缺口报告**（写入 `reports/`，如 `reports/value-data-field-gaps-<date>.json` 或等价格式），包含：字段名、关联原型、尝试过的数据源、最后一次错误/缺失原因。E2E 对该字段 SHALL 标记为 **blocked（待产品决策）** 而非静默通过；交付前 MUST 将缺口清单反馈给产品/用户以决定后续数据源或需求调整。

#### Scenario: 全源均无法获取的字段进入缺口报告

- **WHEN** 某必需字段在所有样本、所有已启用源上均为 None
- **THEN** 验收 SHALL 输出缺口报告条目，且 E2E 结果中该字段状态为 blocked，并说明「所有已知接口均无法获取，待决策」

#### Scenario: 缺口报告可复跑对比

- **WHEN** 修复 fetcher 或新增数据源后重跑 E2E
- **THEN** 新报告 SHALL 可对比此前 blocked 字段是否已变为 covered

### Requirement: 开发环境 bootstrap

系统 SHALL 在缺少本地 `config/app.yaml` 时，提供从 `config/app.example.yaml` 初始化配置的机制（复制或等价引导），并确保 SQLite 文件目录（如 `data/`）存在后再落库。

#### Scenario: 首次运行自动就绪

- **WHEN** 操作者首次运行采集入口且不存在 `config/app.yaml`
- **THEN** 系统 SHALL 从 example 生成可用配置（或给出明确一步复制指令）并继续或提示后重试，避免因缺配置导致静默空库

### Requirement: E2E 网络验收测试

系统 SHALL 包含标 `@pytest.mark.network` 的端到端测试：读取 `config/value_data_validation_stocks.yaml`，对清单内全部样本执行 fetch → upsert → read，执行全字段覆盖验收并生成覆盖/缺口报告。测试失败 MUST 给出可诊断信息（code、source、prototype、缺失字段列表）。

#### Scenario: 全清单 E2E 与字段覆盖报告

- **WHEN** 在具备网络的环境运行 E2E 测试套件
- **THEN** 测试 SHALL 对清单内全部股票执行管道验收，输出字段覆盖报告（每个 V1 必需字段的 covered/blocked 状态及证据）

#### Scenario: E2E 失败可诊断

- **WHEN** E2E 因取数、落库或字段覆盖不足失败
- **THEN** 失败信息 SHALL 包含股票代码、原型、数据源、缺失字段与是否为 blocked 缺口

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
