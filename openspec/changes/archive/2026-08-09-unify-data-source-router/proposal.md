## Why

价值面走配置化多源合并，但 K 线/实时/筹码/情绪仍硬编码 Baostock 或 AKShare，与 `data_sources.enabled` + `priority` 分裂。架构不统一就无法安全地把 Tushare 接到旁路，也无法在换源后保证「同一份缓存 → 报告零漂移」。阶段 A 先统一选源语义，为后续对齐与退役 AKShare 铺路。

权威需求：[docs/mrd/features/data-source-migration.md](../../../docs/mrd/features/data-source-migration.md) §5.A / §12。

## What Changes

- 新建统一选源入口（`DataFetcherRouter` 或扩展 `SourceManager`）：按 config `enabled` + `priority` 实例化 fetcher
- 明确两种策略：**ValueMergeStrategy**（多源并行 + 字段级 priority 合并）与 **FailoverStrategy**（逐源尝试至成功）
- 重构 `KlineProvider` / `RealtimeOverlayProvider` / 筹码与情绪 Provider：禁止无参默认 `AKShareFetcher()`；源列表来自 Router
- 删除价值面 merge 中 Tushare `override_field` 特例（合并完全按 priority）；与 Baostock 字段收敛的实现细节可与阶段 B 同步，但本 change 须去掉特例语义
- **前置**：采集并提交离线 migration golden baseline；PR 门禁 `compare_migration_baseline.py`（S2 零漂移）
- 本阶段**不**要求去除 AKShare，也**不**实现 Tushare K 线/`rt_k`（阶段 B）

## Capabilities

### New Capabilities

- `data-fetcher-router`：统一 Router、ValueMerge / Failover 策略、能力协议与命中源标签（`kline_source` / `quote_source`）
- `migration-baseline-gate`：迁移基线采集/对比脚本与离线报告零漂移门禁（对齐 MRD §12.0 / §12.3）

### Modified Capabilities

- `tech-kline-provider`：K 线取源改为 Router failover，不再硬编码 Baostock→AKShare
- `tech-realtime-overlay`：实时叠加由 Router 注入 failover 链，禁止默认单绑 AKShare
- `value-data-provider`：合并顺序严格按 config priority；移除 `FINANCIAL_STATEMENT_FIELDS` 的 Tushare `override_field` 特例

## Impact

- **代码**：`src/data_provider/manager.py`、新建 router/strategy 模块、`kline_provider.py`、`realtime_overlay_provider.py`、`provider.py`、筹码/情绪 Provider 构造路径
- **测试**：Router/failover/merge golden 单测；`scripts/capture_migration_baseline.py`、`scripts/compare_migration_baseline.py`；`test/fixtures/migration_baseline/**`
- **文档**：`docs/mrd/features/data-source-migration.md` 阶段 A 勾选；若目录分层有变则更新 `docs/dev/engineering-conventions.md`
- **依赖**：无新外部包；仍可保留 akshare 于配置中
- **后续**：`align-tushare-coverage`（B）、`retire-akshare-default`（C）
