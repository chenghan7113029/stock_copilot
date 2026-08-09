## Context

依赖阶段 A 的 Router / Failover / 去 override。Owner 生产可用性为 Tushare → Baostock → AKShare。本阶段补齐 Tushare 能力，使 `tushare+baostock` 可独立完成 `sync` / 价值面 / `report tech`，不依赖 AKShare。离线报告仍以 §12.0 S2 为零漂移硬门禁。

## Goals / Non-Goals

**Goals:**

- Issue #1：仅 tushare（或 Baostock 失败时）可拉取并缓存 K 线
- `rt_k` 实时路径；无权限 → 明确警告 + EOD，不用 daily 冒充
- Baostock 停产低可信财报字段；字段矩阵文档落地
- 情绪 V1 在无 AKShare 时可写入快照（允许分量 missing）
- S2 baseline 仍通过；联网完备性不回归（有容差）

**Non-Goals:**

- 删除 AKShare 默认配置（阶段 C）
- `cyq_chips` 全价位分布、`limit_list_d` 精确涨跌停（5000 分后置）
- 与 AKShare 历史情绪指数绝对值一致

## Decisions

### D1. K 线用 `pro_bar(qfq)` 对齐列名

- 输出列：`date,open,high,low,close,volume`；失败抛 `DataProviderError` 供 Failover

### D2. 实时只用 `rt_k`

- 探测无权限：单测 skip / CLI 警告；降级 EOD；**禁止** silent `daily`

### D3. Baostock 财报字段在 fetcher 侧缺失

- 不写入 `FetchResult.data` 中的 `FINANCIAL_STATEMENT_FIELDS`，从源头避免污染 merge

### D4. 情绪近似可接受偏差

- `daily` 聚合涨跌停 + `margin` 两融；与 legu 数值不同须在 warnings / 设计说明中登记 re-baseline

### D5. 筹码

- 积分不足则跳过联网 + 缓存降级；不阻塞 B 的 P0

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 前复权与 Baostock 微小差异 | 报告保留 `kline_source`；容差 ≤0.5%（联网） |
| rt_k 未开通体验下降 | CLI 明示；文档 OQ-1 |
| 情绪指数需重标定 | S6 不比绝对值；结构一致 |

## Migration Plan

1. 确认阶段 A 已合并且 baseline 绿  
2. 实现 Tushare K 线/实时 → e2e → 关 Issue #1  
3. Baostock 字段收敛 + 矩阵文档  
4. 情绪替代 → `sync market` 无 akshare 可跑  
5. 回滚：禁用 tushare enabled 即可退回 Baostock/AKShare 链

## Open Questions

- OQ-1：`rt_k` 是否已开通  
- OQ-2：是否冲 5000 分接 `cyq_perf`  
- OQ-3：涨跌停近似精度是否满足 Owner
