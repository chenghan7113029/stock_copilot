# Propose List（OpenSpec change 清单）

> 最后梳理：2026-08-09（本分支：`cursor/fix-kline-tushare-source-6f59`）  
> 对照：`docs/mrd/features/data-source-migration.md`、`docs/mrd/roadmap-todo.md`、`openspec/changes/`  
> 用法：待实现 → `/opsx-apply <change-name>`；已实现仅差归档 → `/opsx-archive <change-name>`

---

## A. 数据源迁移（本分支优先 · 已立项）

权威 MRD：`docs/mrd/features/data-source-migration.md`（含 §12.0 Owner 口径：结构可改、离线报告零漂移）。

| Change | 阶段 | 简介 | 状态 |
|---|---|---|---|
| `unify-data-source-router` | A 架构统一 | Router + ValueMerge/Failover；去 override；migration baseline 门禁 | proposal ✅ · **下一步 apply** |
| `align-tushare-coverage` | B Tushare 对齐 | K 线 `pro_bar`、实时 `rt_k`、情绪替代、字段矩阵；关 Issue #1 | proposal ✅ · 依赖 A |
| `retire-akshare-default` | C 退役默认 AKShare | 默认仅 tushare+baostock；去硬门控；legacy 测试隔离 | proposal ✅ · 依赖 B |

**建议顺序**：A → B → C。每阶段 PR 须过 `pytest -m "not network"` + `compare_migration_baseline.py`（A 开工前先采集 baseline）。

---

## B. 其他待 apply（有 proposal，未开工）

| Change | 来源 | 简介 |
|---|---|---|
| `add-feishu-watchlist-push` | 交付通道 | watchlist → 飞书新建文档 + 一票一消息（若本分支无目录，以 `main` 为准） |
| `add-pattern-recognition` | F-18 | K 线形态；不进 `signal_score` |
| `add-bollinger-bands` | F-19 | 布林带；V1 单状态 |

> 与数据源迁移并行时：**先完成阶段 A/B**，避免选源重构与飞书/技术指标改动互相踩踏。

---

## C. 已实现待归档（housekeeping · 多在 main）

原 P0–P2 一批（dashboard、checklist、sentiment、anchor、chip、portfolio 等）代码已落地，多数仅差 `/opsx-archive`。详见 `main` 上梳理后的清单；合入 main 后勿重复 apply。

---

## D. 尚未 propose / 需先澄清

| ID | 名称 | 原因 |
|---|---|---|
| T-1 | 安全边际按原型差异化 | 待设计 |
| PO-11～14 | 宏观/融资/龙虎榜/社媒情绪 | 待规划或扩展 |
| E | REST API / Web | 待定 |
| 价值 V2 原型方法 | 保险 EV/NBV 等 | 明确后置 |

---

## E. 迁移依赖提醒

- **S2 真源**：同一份 seed DB → tech/value/dual 零漂移贯穿 A/B/C  
- **Issue #1** 归阶段 B  
- **rt_k / 5000 分筹码** 为阶段 B 开放问题，apply 前 Owner 确认  
- 飞书推送只消费既有 report，不阻塞迁移，但不要与 A 同 PR 大乱斗
