# 数据源迁移 — 本地 Cursor 交接文档

> 最后更新：2026-08-09  
> 交接方：Cursor Cloud Agent  
> 接手方：本地 Cursor / Owner  
> **状态：仅文档已交付，零生产代码改动**

---

## 1. 一句话任务

在 **不降低离线报告确定性** 的前提下，将数据源架构从「AKShare 隐式优先 + 旁路硬编码」迁移为 **配置驱动的 `tushare(1) + baostock(2)`**，分三阶段完成；Issue [#1](https://github.com/chenghan7113029/stock_copilot/issues/1) 归属阶段 B。

---

## 2. Git 与分支

| 项 | 值 |
|----|-----|
| **工作分支** | `cursor/fix-kline-tushare-source-6f59` |
| **基于** | `main`（交接时） |
| **已 push** | 是 → `origin/cursor/fix-kline-tushare-source-6f59` |
| **本分支改动** | **仅文档**（3 个 MRD 文件，+585 行） |
| **PR** | 尚未创建（可按需从该分支开 docs PR，或合并后再从 `main` 开实现 PR） |

### 本分支 commits（从新到旧）

```
be9537f docs(mrd): add data-source migration entry to roadmap changelog
61218da docs(mrd): cross-link data-source migration testing plan in MRD index
8e891eb docs(mrd): add three-phase testing strategy for data source migration
f96d87e docs(mrd): add three-phase data source migration requirements
```

### 本地接手建议

```bash
git fetch origin
git checkout cursor/fix-kline-tushare-source-6f59
# 或合并到本地 main 后再新建实现分支：
# git checkout main && git merge origin/cursor/fix-kline-tushare-source-6f59
```

实现阶段建议新建分支（勿与纯文档分支混用），例如：

```bash
git checkout -b cursor/unify-data-source-router-6f59 origin/main
# 先 merge 文档 commit，再写代码
```

---

## 3. 权威文档（必读顺序）

| 顺序 | 文档 | 内容 |
|------|------|------|
| 1 | [docs/mrd/features/data-source-migration.md](../mrd/features/data-source-migration.md) | **需求真源**：三阶段范围、Owner 决策 D-1～D-8、§12 测试方案 |
| 2 | [docs/dev/engineering-conventions.md](engineering-conventions.md) | 目录分层、`data_provider/` 约定 |
| 3 | [.cursor/CLOUD_AGENT.md](../../.cursor/CLOUD_AGENT.md) | 环境/bootstrap（本地可略读） |
| 4 | [AGENTS.md](../../AGENTS.md) | Agent 协作入口 |

OpenSpec 立项前可读 skill：`/.cursor/skills/openspec-propose/SKILL.md`

---

## 4. 问题背景（给接手 Agent 的上下文）

### 4.1 GitHub Issue #1

- **标题**：`bug: KlineProvider 不支持 Tushare 数据源，Baostock 故障时 K 线完全不可用`
- **根因**：`KlineProvider._fetch_from_sources` 硬编码 Baostock→AKShare；`TushareFetcher` 无 `fetch_kline`
- **归属**：阶段 B P0（但依赖阶段 A 的 Router）

### 4.2 实际可用性（Owner 实测）

```
代码隐含顺序：  AKShare → Baostock → Tushare
实际可用性：    Tushare → Baostock → AKShare（AKShare 接口超时/不维护）
```

### 4.3 为何 Owner 觉得「Tushare 从未成功」

1. 默认 `config/app.yaml` 长期只有 `akshare + baostock`，**tushare 注释掉**
2. K 线/实时/筹码/情绪 **四条旁路从不走 Tushare**
3. 即使启用 tushare，也常为 priority=3，价值面 merge 后感知不强

---

## 5. Owner 已确认决策（不可擅自推翻）

| ID | 决策 |
|----|------|
| D-1 | 代码层数据源**等价**；priority **仅来自 config** |
| D-2 | **价值面保留多源合并**（各源都拉），字段按 priority 合并，高优先级先写 |
| D-3 | K 线/实时/筹码/情绪用 **failover**（成功即停） |
| D-4 | 实时用 Tushare **`rt_k`**；**禁止 `daily` 冒充实时** |
| D-5 | **Baostock 不支持实时**；`rt_k` 失败 → EOD 降级 + 警告 |
| D-6 | AKShare 未在 config 启用 → **不实例化、不调用**（import 可保留） |
| D-7 | 目标默认配置：`tushare(1) + baostock(2)`，**去掉 akshare** |
| D-8 | 删除 merge 阶段 `override_field` 特例 → **Baostock 不产出** `FINANCIAL_STATEMENT_FIELDS` 低可信字段 |

`FINANCIAL_STATEMENT_FIELDS` 见 `src/data_provider/provider.py`：

```python
{"revenue", "fcf", "capex", "net_debt", "ebit", "depreciation",
 "total_assets", "total_liabilities", "bvps", "roic", "net_income"}
```

---

## 6. 三阶段实施路线

```mermaid
flowchart LR
  A[阶段 A<br/>unify-data-source-router] --> B[阶段 B<br/>align-tushare-coverage]
  B --> C[阶段 C<br/>retire-akshare-default]
```

| 阶段 | OpenSpec change | 核心交付 | 代码量 |
|------|-----------------|----------|--------|
| **A** | `unify-data-source-router` | `DataFetcherRouter`、Kline/Realtime 走 config、去除隐式 AKShare | 中 |
| **B** | `align-tushare-coverage` | `fetch_kline`、`rt_k`、Baostock 字段收敛、情绪 Tushare 替代、**关 Issue #1** | **大** |
| **C** | `retire-akshare-default` | 默认 yaml、bootstrap、CLI 去 AK 硬依赖 | 小 |

**禁止跳阶段 C**：未完成 B 的 Tushare 替代前，不要改默认配置去掉 akshare。

---

## 7. 测试与一致性（§12 摘要）

### 7.1 硬门禁（每阶段 PR 必过）

```bash
pytest -q -m "not network"
python scripts/compare_migration_baseline.py   # 待实现，阶段 A 开工前应先实现
```

### 7.2 核心原则

| 类型 | 要求 |
|------|------|
| **离线 seed 报告**（`600519/601398/601939` 三板 `--json`） | 三阶段全程 **零漂移**（golden baseline） |
| **相同 mock 输入** | merge / failover 语义一致 |
| **联网换源后数值** | 完备性不回归 + 文档容差（见 MRD §12.4 阶段 B 表） |

### 7.3 阶段 A 开工前必须先做

1. 实现 `scripts/capture_migration_baseline.py`
2. 在 **当前 `main`（或合入文档后的基线）** 采集 `test/fixtures/migration_baseline/`
3. 实现 `scripts/compare_migration_baseline.py`
4. **再** 动 Router 代码

详见 MRD §12.3、§12.7 待建工件表。

---

## 8. 关键代码位置（现状）

| 模块 | 路径 | 现状问题 |
|------|------|----------|
| 价值面合并 | `src/data_provider/provider.py` | 多源 merge；Tushare `override_field` 特例待删 |
| 源管理 | `src/data_provider/manager.py` | 仅价值面用；K 线未接入 |
| K 线 | `src/data_provider/kline_provider.py` | 硬编码 Baostock→AKShare；Issue #1 |
| 实时 | `src/data_provider/realtime_overlay_provider.py` | 默认 `AKShareFetcher()` |
| 筹码 | `src/data_provider/chip_distribution_provider.py` | 仅 AKShare |
| 情绪 | `src/data_provider/sentiment/` | `AkshareSentimentFetcher` 独占 |
| Tushare | `src/data_provider/tushare/fetcher.py` | 无 `fetch_kline` / `fetch_realtime_quote` |
| CLI | `src/apps/cli.py` | `sync market` 硬依赖 akshare（L189-195） |
| 配置 | `config/app.example.yaml` | 默认 **tushare(1)+baostock(2)**；akshare 仅注释回滚 |

### 现有测试可复用

- `test/data_provider/test_provider.py` — merge 语义（含待改的 override 测例）
- `test/data_provider/test_kline_provider.py` — K 线 failover
- `test/e2e/test_tushare_pipeline.py` — Tushare 价值面 E2E（需 Token）
- `test/e2e/test_value_data_pipeline.py` — 字段覆盖 E2E
- `data/fixtures/stock_copilot_seed.db` — 离线 baseline 真源

---

## 9. Owner 环境要点

| 项 | 说明 |
|----|------|
| Tushare 积分 | **2000+** |
| `rt_k` 实时权限 | **需单独开通**（约 200 元/月，非积分自带）— 开放问题 OQ-1 |
| `cyq_perf` 筹码 | 需 **5000 积分** — 开放问题 OQ-2；阶段 B 可降级 |
| Token | `config/app.yaml` 或 `TUSHARE_TOKEN` 环境变量 |
| AKShare | Owner 判定**不可用**；勿再作为默认路径 |

---

## 10. 开放问题（实现前请 Owner 确认）

| ID | 问题 |
|----|------|
| OQ-1 | `rt_k` 是否已开通？未开通时 `sync --realtime` 是否接受永久 EOD 降级？ |
| OQ-2 | 筹码：冲 5000 分接 `cyq_perf`，还是长期接受无联网筹码？ |
| OQ-3 | 情绪涨跌停：`daily` 聚合近似 vs `limit_list_d` 精度要求 |
| OQ-4 | `akshare` 是否移至 optional extra（阶段 C） |
| OQ-5 | Router 扩展 `SourceManager` vs 新建 `DataFetcherRouter`（阶段 A 设计 1 页） |

---

## 11. 建议本地 Cursor 起手流程

```text
1. 阅读 docs/mrd/features/data-source-migration.md 全文（尤其 §2、§5、§12）
2. checkout 分支 / merge 文档 commits
3. /opsx-propose unify-data-source-router（阶段 A）
4. 实现 capture_migration_baseline + compare_migration_baseline
5. 在 main 上采集 baseline 并提交 test/fixtures/migration_baseline/
6. 实现 Router + 重构 KlineProvider（阶段 A 代码）
7. pytest -q -m "not network" + compare_migration_baseline 全绿
8. /opsx-propose align-tushare-coverage（阶段 B）→ 实现 Tushare kline/rt_k → 关 Issue #1
9. 阶段 C：改 app.example.yaml + retire-akshare-default
```

### 本地验证命令（常规）

```bash
python scripts/cloud_bootstrap.py
pytest -q -m "not network"
python -m apps.cli report tech 600519      # 离线，需 seed DB
python -m apps.cli report value 600519
# 联网（需 Token）：
python -m apps.cli sync 600519
python scripts/trial_cli_workflow.py --code 600519
```

---

## 12. 明确未做事项（避免重复劳动）

- [ ] 任何 `src/` 生产代码修改
- [ ] `capture_migration_baseline.py` / `compare_migration_baseline.py`
- [ ] OpenSpec change 目录（`openspec/changes/unify-*` 等）
- [ ] Issue #1 修复
- [ ] PR 创建
- [ ] 默认配置改为 tushare+baostock（阶段 C）

---

## 13. 相关链接

- Issue：https://github.com/chenghan7113029/stock_copilot/issues/1
- 需求 MRD：`docs/mrd/features/data-source-migration.md`
- Roadmap 变更记录：`docs/mrd/roadmap-todo.md`（2026-08-09 行）
- Tushare `rt_k` 文档：https://tushare.pro/document/2?doc_id=372

---

## 14. 交接确认清单

接手方完成阅读后，建议自检：

- [ ] 已读 `data-source-migration.md` §2（决策）与 §12（测试）
- [ ] 理解阶段 A 必须先采 baseline 再改代码
- [ ] 理解价值面 **merge** vs 其他路径 **failover** 的区别
- [ ] 已知 Baostock **不能**接实时 failover
- [ ] 已从 `origin` 拉取分支 `cursor/fix-kline-tushare-source-6f59`
- [ ] 已确认本地 `TUSHARE_TOKEN` / `rt_k` 权限状态（OQ-1）
