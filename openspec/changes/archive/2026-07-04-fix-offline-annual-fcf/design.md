## Context

`fix-valuation-assumptions` 修复了 EPS/WACC/growth 假设，但茅台离线 FCF 仍为 263 亿。核验发现：

```
DB 快照（tushare）:
  report_period=20260331, fetched_at=09:19 → FCF=263亿（Q1 cashflow）
  report_period=20251231, fetched_at=08:35 → FCF=584亿（FY2025 年报）✅

当前逻辑: 取 fetched_at 最新 → 263亿 ❌
在线逻辑: _fetch_latest 优先 1231 年报 → 584亿 ✅
```

FY2025 官方数据：OCF 615.22 亿 − capex 31.28 亿 = FCF **583.94 亿**。

## Goals / Non-Goals

**Goals:**
- 离线合并与在线 fetcher 对齐：财报字段优先最新年报（`report_period` 以 `1231` 结尾）
- 行情字段仍用 `fetched_at` 最新快照
- 600519 离线 FCF 恢复 ~584 亿

**Non-Goals:**
- 不改动在线 `get_stock_data()` 合并逻辑（已正确）
- 不改动 Tushare fetcher 年报优先逻辑
- 不实现跨 source 的复杂字段级时间序列（V2）

## Decisions

### 决策 1：分层选快照（行情 vs 财报）

**选择**：`get_stock_data_offline()` 对每个 source 的快照列表：
1. **行情快照** = `max(snapshots, key=fetched_at)` → 合并非财报字段
2. **财报快照** = 在 `report_period.endswith("1231")` 的快照中取 `max(report_period)`；若无年报则 fallback 到 `max(fetched_at)` → 用 `override_field` 合并 `FINANCIAL_STATEMENT_FIELDS`

**理由**：
- 与 `TushareFetcher._fetch_latest` 语义一致
- 最小改动，不破坏 fix-baostock-data-quality 中「fetched_at 最新行情」修复
- Q1 sync 可更新现价，但不污染 FCF

**备选（单快照 fetched_at）**：当前行为，放弃。

**备选（合并所有快照按 report_period 降序）**：更通用但复杂度高，V1 不需要。

### 决策 2：复用 FINANCIAL_STATEMENT_FIELDS 常量

财报字段集合已存在于 `provider.py`，离线分层合并直接复用，避免重复定义。

## Risks / Trade-offs

- **[风险] 仅有季报无年报时**：fallback 到 fetched_at 最新，与现行为一致。
- **[风险] 年报快照 fetched_at 很旧**：财报用旧年报、行情用新价，属合理（TTM 以最近完整年报为准）。
- **[权衡] Baostock 季频数据**：Baostock 快照 `report_period` 可能非 1231；无年报时仍用最新快照。

## Migration Plan

1. 代码部署后无需 re-sync；现有 DB 中 20251231 年报快照会被自动选用
2. 无 schema 变更
3. 用户 re-sync 后 Q1 快照不再覆盖年报 FCF
