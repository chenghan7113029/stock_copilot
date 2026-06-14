## Why

`add-value-data-provider-v1` 已实现取数、多源管理与 DAO 持久化，但**端到端「拉数 → 落库 → 读回」链路未在真实环境验证通过**：默认库 `data/stock_copilot.db` 为空；Baostock 财务接口因 `year=0, quarter=0` 仅写入行情价；Provider 与 Fetcher 的 `fetch_all` 调用签名不一致导致取数失败；SQLite 在长耗时网络拉取期间出现 `database is locked`。在价值面估值方法开发之前，必须先打通并验收这条数据管道，否则后续所有估值都建立在未验证的假设上。

## What Changes

- 修复 **Fetcher 接口一致性**：统一 `fetch_all` 签名与 SourceManager / Provider 调用方式，补充回归测试。
- 修复 **Baostock 季频财务参数**：用有效 `year/quarter`（或等价 API）获取 eps/roe/营收等字段，不再静默只落 `current_price`。
- 增强 **AKShare 取数健壮性**：对空响应/JSON 解析失败给出明确错误与重试策略，避免整条链路无数据。
- 修复 **持久化会话与 SQLite 锁**：Provider 落库与长耗时 fetch 分离会话边界，避免 fetch 期间持有 DB 写锁。
- 新增 **端到端编排入口**：`scripts/` 或 `src/apps/` 提供可复跑的「采集并落库」命令；开发环境可从 `app.example.yaml` 一键初始化。
- 新增 **E2E 验收测试**：读取 `config/value_data_validation_stocks.yaml`，对清单内全部样本 fetch → upsert → read；**V1 必需字段并集逐字段验证**（跨样本聚合覆盖，非「单股至少一个字段」）；不可获取字段输出缺口报告至 `reports/` 待产品决策。
- 可选：将已验证的 `fetch_all` 修复提交并纳入本 change 的 tasks（若工作区已有未提交修复则合并验收）。

## Capabilities

### New Capabilities

- `value-data-pipeline-e2e`：端到端采集—持久化—读回编排、开发环境 bootstrap、E2E 验收场景。

### Modified Capabilities

- `value-data-provider`：Fetcher 接口一致性；Baostock 财务季频参数；AKShare 失败语义与重试。
- `value-data-store`：落库会话边界；SQLite 并发/锁处理；读回 API 与 E2E 可验证性。

## Impact

- **代码**：`src/data_provider/{base,manager,provider,baostock,akshare}/`、`src/dao/`、`scripts/` 或 `src/apps/`
- **测试**：`test/data_provider/`、`test/dao/`、新增 `test/e2e/` 或等价 network E2E
- **配置**：`config/app.example.yaml`（bootstrap 说明）、可选 `scripts/setup-dev-env.sh` 补充
- **文档**：归档时更新 `docs/mrd/features/value-analysis.md` §9 验收说明；若新增 scripts 入口则更新 `docs/dev/engineering-conventions.md`
- **依赖**：无新增运行时依赖；沿用 akshare、baostock、SQLAlchemy
