## Context

当前 `StockDataProvider` 多源合并与 `SourceManager` 并存，但 `KlineProvider` 硬编码 Baostock→AKShare，`RealtimeOverlayProvider` 默认 `AKShareFetcher()`，筹码/情绪仅门控 `is_data_source_enabled(akshare)`。Owner 确认（MRD D-1～D-3、D-6、§12.0）：选源只认 config；价值面合并、旁路 failover；**同一份 seed 上离线报告零漂移**。

利益相关方：Owner（验收口径）、实现 Agent、Reviewer。约束见 `docs/dev/engineering-conventions.md` 分层与 `docs/mrd/features/data-source-migration.md`。

## Goals / Non-Goals

**Goals:**

- 唯一选源真源：enabled + priority
- K 线/实时/筹码/情绪构造均经 Router；未启用源不实例化、不调用
- 价值面 merge 去 `override_field` 特例，严格 priority
- 迁移 baseline 采集 + 对比成为阶段 A PR 硬门禁
- 离线 SQLite 缓存契约不变（`report *` 读库路径）

**Non-Goals:**

- 实现 Tushare `fetch_kline` / `rt_k` / 情绪替代（阶段 B）
- 改默认 `app.example.yaml` 去掉 akshare（阶段 C）
- 物理删除 `src/data_provider/akshare/`
- 将价值面改为单源 failover

## Decisions

### D1. Router 落点：扩展 SourceManager + 显式 Strategy，而非平行第二套选源

- **选择**：在 `src/data_provider/` 新增 `router.py`（或扩展 `manager.py`）暴露 `from_config` → 排序后的 fetcher 列表；`ValueMergeStrategy` / `FailoverStrategy` 为纯函数或小组件
- **备选**：新建独立包名 `DataFetcherRouter` 完全替换 SourceManager — 也可，但需一次性迁移价值面调用点；本设计允许内部改名，对外保持 `StockDataProvider.from_config` 稳定
- **理由**：减少双轨选源；价值面已依赖 SourceManager

### D2. 能力协议：Protocol 声明，未实现则 Failover 跳过

- Fetcher 可选实现 `fetch_kline` / `fetch_realtime_quote` / `fetch_chip_distribution` / `fetch_market_sentiment`
- Failover 对「不支持」视为该源失败，继续下一源；全失败则按现有错误类型抛出或文档化降级

### D3. 命中源可观测

- Failover 成功后记录 `kline_source` / `quote_source`（日志 + sync 进度）；不改变离线报告数值字段（避免污染 S2）

### D4. override_field 删除时机

- 阶段 A 删除 merge 特例；若 Baostock 仍产出低可信财报字段，mock 合并 golden 须更新；**离线 seed 报告不应变**（读已落库快照）
- Baostock 侧停产这些字段可与阶段 B 同步交付（MRD 允许）

### D5. Baseline 样本

- 至少 `600519` / `601398` / `601939` 的 tech/value/dual JSON；规范化后剔除 `data_timestamp` 等非确定性字段

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| KlineProvider 重构破坏离线 report | S2 baseline 硬门禁；保持 `offline=True` 仅读 `KlineRepo` |
| SourceManager 与旧 `_fetch_with_fallback` 语义混淆 | 设计注释废弃未使用路径或重命名；单测锁定 merge vs failover |
| 删 override_field 改变联网 merge 数值 | 更新 mocked_merge golden；不把联网绝对值当 S2 门禁 |
| 情绪/筹码仍绑 AKShare 实现 | 本阶段只改构造/门控；能力矩阵留给 B |

## Migration Plan

1. 合并前：在文档合入点或当前 main 跑 `capture_migration_baseline.py`，提交 fixture  
2. 落地 Router + 重构 Provider，保持默认 config 仍可含 akshare  
3. PR：`pytest -m "not network"` + `compare_migration_baseline.py`  
4. 回滚：恢复 Provider 构造路径即可；baseline 保留供后续阶段

## Open Questions

- OQ-5（MRD）：最终类名 `SourceManager` 扩展 vs `DataFetcherRouter` — 实现时在 design 注释中二选一并更新 conventions  
- Baostock 财报字段停产是否与 A 同 PR：建议 **A 去 override + B 停产** 分 PR，避免 A 范围膨胀
