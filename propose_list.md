# Propose List（OpenSpec change 清单）

> 最后梳理：2026-09-27（对照 `openspec list`、`openspec/changes/`、`src/` 代码与 git 分支全量核对）
> 对照：`docs/mrd/roadmap-todo.md`、`docs/mrd/features/*`
> 用法：待实现 → `/opsx-propose <change-name>` → `/opsx-apply <change-name>` → `/opsx-archive <change-name>`

---

## 当前结论（一句话）

**OpenSpec 队列已清空——没有「已 propose 待实现」的 change。**  
`openspec list` 返回 `No active changes found.`；51 个 change 全部归档，90 个 capability spec 均有对应实现；`release` 与 `main` 无差异，所有分支均已合入。

**仍未实现的能力都还没立项**（无 proposal），清单见 D 区。

---

## A. 队列状态核对（2026-09-27）

| 项 | 值 |
|---|---|
| `openspec list` | `No active changes found.` |
| `openspec/changes/` | 仅 `archive/`，无活跃 change 目录 |
| 已归档 change | 51 |
| `openspec/specs/` capability | 90 |
| 分支 | `release` == `main`；`git branch --no-merged release` 为空 |

---

## B. 近期已归档（2026-08-15 起；完整索引见 `openspec/changes/archive/`）

| Change | 能力 | 归档路径 |
|---|---|---|
| `add-mos-thresholds-by-prototype` | T-1 MOS 按原型差异化阈值 | `archive/2026-08-15-add-mos-thresholds-by-prototype` |
| `add-value-v2-prototype-methods` | 价值 V2 P1–P5 专用方法 | `archive/2026-08-15-add-value-v2-prototype-methods` |
| `add-feishu-watchlist-push` | `feishu push`：本地 MD → lark-cli 文档 + 一票一消息 | `archive/2026-08-15-add-feishu-watchlist-push` |
| `add-confrontation-declaration` | `confront declare` / `confront show` + `--confrontation-id` 软链 | `archive/2026-08-29-add-confrontation-declaration` |
| `add-confrontation-narrate-api` | `report confront [--narrate]` + numbered evidence + `ConfrontationRecord` | `archive/2026-08-29-add-confrontation-narrate-api` |
| `add-confrontation-persona-stress-test` | `report persona-stress [--narrate]`（3 lens） | `archive/2026-08-29-add-confrontation-persona-stress-test` |
| `fix-migration-baseline-as-of` | L3 门禁钉 `as_of`，与墙钟解耦 | `archive/2026-08-29-fix-migration-baseline-as-of` |
| `add-html-briefing-report` | `report briefing` 周末深复盘自包含 HTML | `archive/2026-09-13-add-html-briefing-report` |
| `add-pattern-recognition` | F-18 K 线形态（十字星/锤头/吊颈/吞没） | `archive/2026-09-13-add-pattern-recognition` |
| `add-bollinger-bands` | F-19 布林带 + `BollingerStatus` | `archive/2026-09-13-add-bollinger-bands` |
| `polish-html-briefing-ux` | HTML briefing UX（价格情境、多空分栏、讲解） | `archive/2026-09-13-polish-html-briefing-ux` |

---

## C. 归档 change 中残留的未勾选 task（非功能缺口）

归档目录里有 15 个 `tasks.md` 存在未勾选项，经逐条核对，全部是**归档手续**（「跑 `openspec archive xxx`」「合并 delta spec 到 docs/mrd」）或**事后验证项**，不表示功能没做。唯一实质待补项：

| Change | 未勾选项 | 说明 |
|---|---|---|
| `2026-07-04-add-tushare-financials` | `7.5 验证全方法聚合中位数 ≈1,300 元，与 Gemini 参考 1,340–1,474 误差 ≤±5%` | 数据层已验证（见 `roadmap-todo.md` §5.3「600519 验证」），但该条聚合中位数断言未留下勾选记录 |

---

## D. 未实现且尚未立项（真正的待办 · 详见 `docs/mrd/roadmap-todo.md`）

| ID | 能力 | 现状 | 建议 change |
|---|---|---|---|
| PO-11 | 宏观 / 政策 / 治理事件层 | 待规划，范围未定 | —（需先澄清） |
| PO-12 | 个股融资融券余额 | 未建；现有情绪仅市场级两融（`macro_china_market_margin_sh/sz`） | `add-stock-margin-data`（待定） |
| PO-13 | 龙虎榜情绪信号 | 未建；`src/` 无 `top_list`/`top_inst` 相关代码 | `add-top-list-sentiment`（待定） |
| PO-14 | 社媒 / 新闻文本情绪 | 未建，需独立评估 NLP/LLM 管线 | —（需先澄清） |
| PO-08 / E | REST API + Web 看板 | 未建；`src/controller/` 仅有 docstring 占位 | `add-value-api`（待定） |
| PO-05b | entry-check 回答落库 | 未建（「今日仍愿买吗」Y/N + 理由未持久化） | `add-entry-check-response` |
| PO-09b | 复盘规则反哺建议 | 未建（Badcase → Checklist 规则建议） | `add-trade-review-rule-hints` |
| — | Level 2 多轮辩论 | 未建（P2） | `add-confrontation-debate-v2` |
| — | decision-history 视图 | 未建（P2） | `add-decision-history` |
| — | 周期 + 资产重估原型（北大荒） | 未建（`PrototypeRouter` 无该原型） | 待定 |
| T-12 | Cyclical 4 方法补齐 | 已做 `cyclical_pe` / `cyclical_fcf`；`pb` / `dividend` 未做 | 待定 |
| T-11 | ValueScore 综合评分 | 未实现，`ValueAnalysisResult.value_score` 仅占位 | 待定 |

---

## E. 已决策不做

| 项 | 决策 |
|---|---|
| 月 K 线分析 | D-7：级别过大，暂不实现 |
| 编排式 `decision audit` 单命令 | Owner 决策：不做；命令分散，仅 ID 关联 |
| 19 Agent persona / 自动 Fund | 不跟随竞品 ai-hedge-fund 路线 |
| LLM 自动填写 declare 或 Checklist 硬规则 | 不做 |

---

## F. 依赖关系（仍有效）

- **持仓两套表勿混**：`TradeRecord`（复盘/组合）≠ `PositionRecord`（入场检查最小成本表）；组合相关性只复用前者。
- **行业路由链**：Router → Override → Fallback 文案，三段均已落地。
- **飞书推送**：只消费既有 sync/report/watchlist/summary/confront/persona-stress；**不**把 Cursor Skill 红蓝互驳塞进定时管道。
- **形态 / 布林带**：已交付，独立字段展示，**不参与** `signal_score`。
- **S2 真源**：同一份 seed DB → tech/value/dual 零漂移（迁移后仍适用）。
- **Web / REST API 是唯一阻塞产品级入口的缺口**：`src/controller/` 空，PO-01 Web 看板与 PO-08 Web 均依赖它。
