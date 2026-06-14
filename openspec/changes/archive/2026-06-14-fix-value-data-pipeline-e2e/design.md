## Context

V1 数据层（`add-value-data-provider-v1`）已交付 AKShare/Baostock fetcher、SourceManager、StockDataProvider、StockSnapshotRepo 与 SQLite ORM。实际验证暴露：

| 问题 | 现象 | 根因（初步） |
|------|------|-------------|
| 默认库为空 | `data/stock_copilot.db` 0 行 | 无 bootstrap 配置/脚本；E2E 从未跑通 |
| fetch_all 失败 | Provider 日志「takes 2 positional arguments but 3 were given」 | `BaseFetcher.fetch_all(code)` vs 调用方传 `(code, exchange)` |
| Baostock 仅落行情 | verify.db 只有 `current_price` | `query_*_data(year=0, quarter=0)` 被 API 拒绝 |
| SQLite locked | upsert 失败 | 长耗时网络 fetch 与同一 Session 写库并发；或多进程争用 |
| AKShare 偶发失败 | JSON parse error | 空响应/限频；错误未阻断 E2E 验收 |

本 change 聚焦**打通并验收**整条管道，不扩展新数据源或估值逻辑。

## Goals / Non-Goals

**Goals:**

- 开发者执行一条命令（或等价脚本）即可完成：加载配置 → 拉取样本股 → upsert → 从 DB 读回并打印/断言。
- 修复已知 fetcher / provider / manager 缺陷，使 AKShare 或 Baostock 至少一方能写入**含基本面字段**的快照。
- 持久化路径在单进程 E2E 下无 `database is locked`。
- 新增 `@pytest.mark.network` E2E 测试，作为交付门槛；离线测试覆盖接口签名与会话边界。

**Non-Goals:**

- 新增 Tushare 等 token 源。
- 历史 PE/PB 序列（V1.x）。
- Web API / FastAPI 暴露。
- 重写 AKShare 全部映射（除非阻塞 E2E）。

## Decisions

### D1：统一 `fetch_all(code, exchange)` 签名

- **选择**：在 `BaseFetcher.fetch_all(self, code, exchange)` 内调用 `normalize_stock_code`（若 code 已 6 位则 exchange 可来自参数或推断）；SourceManager / Provider 统一传 `(code, exchange)`。
- **理由**：与 `fetch_quote` / `fetch_fundamentals` 一致；避免 Manager 特殊分支。
- **备选**：仅传 `code`（弃：exchange 对 BJ 等边界场景已在使用）。

### D2：Baostock 季频参数 — 取最近可用财报季

- **选择**：计算「上一完整季度」`(year, quarter)`，失败时向前回溯最多 4 个季度；不用 `year=0, quarter=0`。
- **理由**：Baostock API 文档要求 1–4；验证日志已确认 0 无效。
- **备选**：仅保留 Baostock 行情、财务全靠 AKShare（弃：削弱多源 failover）。

### D3：落库与拉数分离 Session 边界

- **选择**：Provider 流程改为「先完成所有 fetcher 的 `fetch_all` 收集 `FetchResult` 列表 → 再开短生命周期 Session 批量 upsert → commit」。fetch 阶段不持有 SQLAlchemy Session。
- **理由**：消除 fetch 期间（数十秒 Baostock login 循环）占锁。
- **备选**：每源 fetch 后立即 upsert 但用独立 Session（可接受 fallback，优先批量写）。

### D4：E2E 入口放在 `scripts/fetch_value_data.py`

- **选择**：CLI：`python scripts/fetch_value_data.py --code 600519 [--codes ...]`；读取 `config/app.yaml`（不存在则从 example 复制并提示）；自动 `create_all`；结束打印读回摘要。
- **理由**：符合 engineering-conventions「scripts 做 devops」；比临时 python -c 可复跑。
- **备选**：`src/apps/cli.py`（可后续合并，本 change 先 scripts）。

### D5：E2E 验收标准 — V1 全字段覆盖（跨样本聚合）

- **选择**：
  - 样本清单真源：`config/value_data_validation_stocks.yaml`（601398/601328/601939/600036 银行，600900 高股息，600519 价值成长）。
  - 验收字段全集 = `field_requirements.py` 中 bank ∪ high_dividend ∪ value_growth 的必需字段并集。
  - **并集覆盖**：每个字段至少在一只样本股上非空，且读回与写入一致；报告中逐字段列出 `code + source + 值`。
  - **分原型**：每只样本另需满足其绑定原型的必需字段（或与并集规则一致，缺失则失败）。
  - **blocked 缺口**：全源全样本仍无法获取的字段 → `reports/value-data-field-gaps-*.json`，E2E 标记 blocked，交付前反馈用户决策，不得静默通过。
- **理由**：用户要求验证「数据需求中的字段都能拿到」，而非单字段敷衍通过。
- **备选**：仅验 600519 单股（弃：无法覆盖银行/高股息字段集）。

### D6：配置 bootstrap

- **选择**：`scripts/fetch_value_data.py` 启动时若缺 `config/app.yaml`，从 `app.example.yaml` 复制并创建 `data/` 目录；文档说明 `app.yaml` 不入库。
- **理由**：降低「库为空因未配 config」的踩坑率。

## Risks / Trade-offs

- [AKShare 接口不稳定] → 重试 + E2E 允许 Baostock 补位；报告标注实际命中源。
- [Baostock 季频与 AKShare 财报期不一致] → 来源维度独立存储，不跨源覆盖；E2E 按源断言。
- [多进程同时跑 fetch 脚本] → 文档警告单进程；SQLite WAL + busy_timeout 已启用。
- [E2E 依赖网络] → 标 `network`；CI 可选；交付前本地必跑。

## Migration Plan

- Bugfix + 新脚本，无破坏性 API 变更。
- 已有空库可直接重跑 fetch 脚本填充。
- 工作区若已有未提交的 `fetch_all` 修复，合并进本 change 并补测试。

## Open Questions

- （无）Baostock 季频回溯策略、Session 边界、E2E 入口均已在上文决策；实现阶段若 AKShare 持续不可用，以 Baostock 财务 + 报告说明为主源降级。
