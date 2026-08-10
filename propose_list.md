# Propose List（OpenSpec change 清单）

> 最后梳理：2026-08-10（`main` 已合入数据源迁移 A/B/C）  
> 对照：`docs/mrd/features/data-source-migration.md`、`docs/mrd/roadmap-todo.md`、`openspec/changes/`  
> 用法：待实现 → `/opsx-apply <change-name>`；已实现仅差归档 → `/opsx-archive <change-name>`

---

## 当前结论（一句话）

**数据源迁移三阶段（A/B/C）已合入 `main` 并归档。**  
原 P0–P2 能力大多已落地，多数 change 只差 `/opsx-archive`。  
**真正还没 apply 的**，目前是：飞书常看推送、K 线形态、布林带；另有若干需先 explore / 待规划项。

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
| `add-feishu-watchlist-push` | 交付通道（通勤） | 家里 PC 交易日定时：`watchlist` → 本地 MD → 飞书新建文档 + 一票一消息；CLI `feishu push`（含 dry-run） | proposal ✅ · tasks 0/21 |
| `add-pattern-recognition` | F-18 · V2 | 十字星/锤头/吊颈/吞没等规则识别；独立字段展示，**不进** `signal_score` | proposal ✅ · tasks 0/24 |
| `add-bollinger-bands` | F-19 · V2 | 布林带 + `BollingerStatus`；V1 只做指标与单状态，不做跨指标组合 | proposal ✅ · tasks 0/23 |

### 建议下一棒顺序

1. **`add-feishu-watchlist-push`** — 已有 watchlist + MD 报告形态，通勤交付缺口最大、ROI 最高  
2. `add-pattern-recognition` / `add-bollinger-bands` — 技术面 V2，彼此独立，可穿插；**不阻塞**飞书推送

---

## C. 已实现，待归档（housekeeping）

> 实现任务基本打满，残留多为「运行 `/opsx-archive`」。  
> `add-llm-comprehensive-report` 已归档（`archive/2026-08-01-…`）。

| Change | roadmap | 备注 |
|---|---|---|
| `add-stock-dashboard` | PO-01 / PO-08 CLI | `report dashboard` |
| `add-decision-checklist` | PO-04 | `checklist submit/show` |
| `add-fresh-entry-check` | PO-05 | `position set` + `entry-check` |
| `add-sentiment-module` | PO-06 | `sync market` + dual 三维解读；个股融资/龙虎榜/社媒见 §E |
| `add-anchor-defense` | PO-07 | 分位定性分档 + 历史最高价默认隐藏（`--show-anchor-price`）※ |
| `add-value-trap-high-alert` | T-2 | `value_trap_alert` + confidence 降级 |
| `add-industry-prototype-router` | T-7 | 行业→原型短路；保险不再误判 bank |
| `add-prototype-override-persistence` | T-8 | `value override` + `prototype_overrides` |
| `add-prototype-fallback-message` | T-15 | 保险/军工等精确降级文案 |
| `add-trade-review-attribution` | PO-09 | `trade record` / `report trade-review` |
| `add-portfolio-correlation` | PO-10 | `report portfolio`（复用 `TradeRecord`） |
| `add-chip-distribution` | F-17 | 筹码管道；不进 `signal_score` |
| `add-llm-narrative-core` | LLM 基建 | 已被 summary `--narrate` 消费；建议随归档一并收口 |

※ `docs/mrd/roadmap-todo.md` 里 PO-07 仍标「待建」，与代码 / `product-overview` 不一致，归档时请改成已实现。

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
| T-1 | 安全边际按原型差异化 | 「待设计」，先 `openspec-explore` |
| PO-11 | 宏观/政策/治理事件层 | 「待规划」，范围未定 |
| PO-12 | 个股融资融券余额 | 情绪面 V1 之后的扩展；未立 change |
| PO-13 | 龙虎榜情绪信号 | 同上 |
| PO-14 | 社媒/新闻文本情绪 | 需单独评估 NLP/LLM 管线 |
| E | REST API / Web 看板 | change 名待定；依赖 Web 层整体决策 |
| T-4～T-6 / T-12 等 | 价值面 V2 原型方法 | 保险 EV/NBV、军工订单、成长 PEG 等，明确后置 |

---

## F. 依赖关系（仍有效）

- **持仓两套表勿混**：`TradeRecord`（复盘/组合）≠ `PositionRecord`（入场检查最小成本表）；组合相关性只复用前者。  
- **行业路由链**：Router（已落地）→ Override（已落地）→ Fallback 文案（已落地）；归档顺序随意。  
- **飞书推送**：只消费既有 sync/report/watchlist/summary；**不**把 Cursor Skill 红蓝互驳塞进定时管道。  
- **形态 / 布林带**：独立于飞书与决策护航，可随时穿插，但勿污染 `signal_score`（proposal 已写死）。  
- **S2 真源**：同一份 seed DB → tech/value/dual 零漂移（迁移后仍适用）。

---

## G. 归档小抄

对 §C 中任一 change：

```text
/opsx-archive <change-name>
```

建议一次归档一批已打满 tasks 的 change，并顺手把 `roadmap-todo.md` 的 PO-07 / §8 统计摘要更新到与代码一致。
