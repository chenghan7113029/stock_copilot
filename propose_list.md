# Propose List（OpenSpec change 清单）

> 最后梳理：2026-08-10（`main` 已合入数据源迁移 A/B/C）  
> 对照：`docs/mrd/features/data-source-migration.md`、`docs/mrd/roadmap-todo.md`、`openspec/changes/`  
> 用法：待实现 → `/opsx-apply <change-name>`；已实现仅差归档 → `/opsx-archive <change-name>`

---

## 当前结论（一句话）

**数据源迁移三阶段（A/B/C）已合入 `main` 并归档；原 P0–P2 已落地 change 已于 2026-08-10 批量归档。**  
**真正还没 apply 的**，目前是：价值 V2 专用方法（P2+）、飞书常看推送、K 线形态、布林带。
T-1 MOS 与 V2 P1（比亚迪浅情景）在 `feature/apply-mos-and-value-v2-methods` 推进中。

---

## A. 数据源迁移（已完成 · 已归档）

权威 MRD：`docs/mrd/features/data-source-migration.md`（§12.0：结构可改、离线报告零漂移）。

| Change | 阶段 | 归档路径 |
|---|---|---|
| `unify-data-source-router` | A | `archive/2026-08-09-unify-data-source-router` |
| `align-tushare-coverage` | B | `archive/2026-08-09-align-tushare-coverage` |
| `retire-akshare-default` | C | `archive/2026-08-10-retire-akshare-default` |

默认配置：`tushare(1) + baostock(2)`；AKShare 仅紧急回滚。回归门禁：`pytest -m "not network"` + `compare_migration_baseline.py`。

---

## B. 待 apply（有 proposal，实现任务未开工）

| Change | roadmap / 来源 | 简介 | 状态 |
|---|---|---|---|
| `add-mos-thresholds-by-prototype` | T-1 / VA-OUT-3 | 银行/高股息/价值成长 MOS 评估与双轨阈值按原型差异化 | apply 中（feature 分支，近完成） |
| `add-value-v2-prototype-methods` | value V2 · T-4～T-12 | 专用方法总立项：P1 比亚迪情景 → P2 分众/Cyclical → P3 军工 → P4 保险 → P5 华测 | apply 中 · P1 进行中 |
| `add-feishu-watchlist-push` | 交付通道（通勤） | 家里 PC 交易日定时：`watchlist` → 本地 MD → 飞书新建文档 + 一票一消息；CLI `feishu push`（含 dry-run） | proposal ✅ · tasks 0/21 |
| `add-pattern-recognition` | F-18 · V2 | 十字星/锤头/吊颈/吞没等规则识别；独立字段展示，**不进** `signal_score` | proposal ✅ · tasks 0/24 |
| `add-bollinger-bands` | F-19 · V2 | 布林带 + `BollingerStatus`；V1 只做指标与单状态，不做跨指标组合 | proposal ✅ · tasks 0/23 |

### 建议下一棒顺序

1. **`add-mos-thresholds-by-prototype`（T-1）** — 近完成  
2. **`add-value-v2-prototype-methods` P1** — 比亚迪浅情景（进行中）  
3. **同 change P2+** 或 **`add-feishu-watchlist-push`**  
4. 形态 / 布林带 — 可穿插

---

## C. 已实现并已归档（2026-08-10 housekeeping）

| Change | roadmap | 归档路径 |
|---|---|---|
| `add-v2-honesty-degrade` | value V2 · 第 0 刀诚实层 | `archive/2026-08-10-add-v2-honesty-degrade` |
| `add-stock-dashboard` | PO-01 / PO-08 CLI | `archive/2026-08-10-add-stock-dashboard` |
| `add-decision-checklist` | PO-04 | `archive/2026-08-10-add-decision-checklist` |
| `add-fresh-entry-check` | PO-05 | `archive/2026-08-10-add-fresh-entry-check` |
| `add-sentiment-module` | PO-06 | `archive/2026-08-10-add-sentiment-module` |
| `add-anchor-defense` | PO-07 | `archive/2026-08-10-add-anchor-defense` |
| `add-value-trap-high-alert` | T-2 | `archive/2026-08-10-add-value-trap-high-alert` |
| `add-industry-prototype-router` | T-7 | `archive/2026-08-10-add-industry-prototype-router` |
| `add-prototype-override-persistence` | T-8 | `archive/2026-08-10-add-prototype-override-persistence` |
| `add-prototype-fallback-message` | T-15 | `archive/2026-08-10-add-prototype-fallback-message` |
| `add-trade-review-attribution` | PO-09 | `archive/2026-08-10-add-trade-review-attribution` |
| `add-portfolio-correlation` | PO-10 | `archive/2026-08-10-add-portfolio-correlation` |
| `add-chip-distribution` | F-17 | `archive/2026-08-10-add-chip-distribution` |
| `add-llm-narrative-core` | LLM 基建 | `archive/2026-08-10-add-llm-narrative-core` |

---

## D. 本轮已交付、但不在原 propose 表里（对照用）

| 能力 | 落点 | 说明 |
|---|---|---|
| 常看列表 | `config/watchlist.yaml` + `watchlist` / `--watchlist` | 已进 `main`；飞书推送将消费它 |
| 红蓝对抗 V1 | `report dual` + Cursor Skill | 已归档 `add-red-blue-confrontation`；Level‑1 叙事仍靠会话 Skill |
| 报告 Markdown 默认输出 | `switch-reports-to-markdown` | 已归档（2026-08-02） |
| 报告内嵌讲解 | `add-report-inline-explainers` | 已归档（2026-08-02） |
| LLM 综合摘要 | `report summary [--narrate]` | 已归档 `add-llm-comprehensive-report` |
| 数据源迁移 A/B/C | Router / Tushare 对齐 / 退役默认 AKShare | 已归档（2026-08-09～10） |

---

## E. 尚未 propose / 需先澄清（不要直接 apply）

| Change | 来源 | 简介 |
|---|---|---|
| PO-11 | 宏观/政策/治理事件层 | 「待规划」，范围未定 |
| PO-12 | 个股融资融券余额 | 情绪面 V1 之后的扩展；未立 change |
| PO-13 | 龙虎榜情绪信号 | 同上 |
| PO-14 | 社媒/新闻文本情绪 | 需单独评估 NLP/LLM 管线 |
| E | REST API / Web 看板 | change 名待定；依赖 Web 层整体决策 |

> T-1 与价值 V2 专用方法已立项：见 B 区 `add-mos-thresholds-by-prototype`、`add-value-v2-prototype-methods`。

---

## F. 依赖关系（仍有效）

- **持仓两套表勿混**：`TradeRecord`（复盘/组合）≠ `PositionRecord`（入场检查最小成本表）；组合相关性只复用前者。  
- **行业路由链**：Router（已落地）→ Override（已落地）→ Fallback 文案（已落地）。  
- **飞书推送**：只消费既有 sync/report/watchlist/summary；**不**把 Cursor Skill 红蓝互驳塞进定时管道。  
- **形态 / 布林带**：独立于飞书与决策护航，可随时穿插，但勿污染 `signal_score`（proposal 已写死）。  
- **S2 真源**：同一份 seed DB → tech/value/dual 零漂移（迁移后仍适用）。
