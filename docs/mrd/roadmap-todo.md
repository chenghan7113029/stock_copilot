# stock_copilot 功能待办清单（Roadmap TODO）

> 最后更新：2026-06-28  
> 用途：对照 MRD 与代码库，跟踪**尚未实现**的能力；实现完成后勾选并追加变更记录。  
> 权威需求来源：[product-overview.md](product-overview.md)、[features/value-analysis.md](features/value-analysis.md)、[features/tech-analysis.md](features/tech-analysis.md)  
> OpenSpec 活跃 change：`add-cli-core`（✅ 已实现，待归档）

---

## 变更记录

| 日期 | 摘要 |
|------|------|
| 2026-06-28 | 初稿：汇总 P0–V2 待办；标记 F-16/F-20/双轨 Facade 已交付 |
| 2026-06-28 | 新增 §5.1 CLI 核心设计（add-cli-core 提案）；更新 §5 阶段 A 状态 |
| 2026-06-28 | add-cli-core 实现完成：sync / report tech / report value |
| 2026-06-28 | fix-baostock-data-quality 实现：historical_pe、FCF 推导链、CAGR、Aggregator 可信度守卫 |

---

## 1. 已交付快照（便于对照）

实现完成后从此节核对，**不必重复立项**。

### 1.1 价值面

- [x] 23 种估值方法（Phase 0–8，`src/service/value/valuation/`）
- [x] `ValueAnalyzer` + `Aggregator` + `PrototypeRouter`（`add-value-analyzer-core`）
- [x] 数据层：`ValueDataProvider`、Baostock/AKShare/Tushare、SQLite 持久化

### 1.2 技术面

- [x] P0 核心：K 线缓存、`IndicatorCalculator`、`BullTrendScorer`、`TechAnalyzer`（`add-tech-analyzer-core`）
- [x] F-16 实时行情融合：`fetch_realtime_quote` + `RealtimeOverlayProvider` + `use_realtime`（`add-realtime-overlay`）
- [x] F-20 周 K 线：`WeeklyKlineAggregator` + 周线空头过滤（`add-weekly-kline`）

### 1.3 双轨与融合

- [x] `DualTrackAnalyzer` + `SignalFusion` + `DualTrackReport`（`add-dual-track-analyzer`）

### 1.4 尚未交付（产品级入口）

- [ ] REST API / Web 看板
- [x] CLI 核心（`sync` / `report tech` / `report value`，`add-cli-core`）
- [ ] LLM 综合报告
- [ ] 情绪面整模块
- [ ] 决策护航（红蓝对抗、Checklist、首开仓评估）

---

## 2. 产品级待办（最高优先级）

来源：[product-overview.md](product-overview.md) §5–§7

### 2.1 P0 — 综合呈现与决策护航

| ID | 能力 | 说明 | 状态 |
|----|------|------|------|
| PO-01 | 多维立体看板 | 单票一页：价值 + 技术 + 情绪 + 综合摘要 | [ ] 待建 |
| PO-02 | LLM 综合报告 | 确定性结果 → ContextPack → 可读叙述；**数值以计算模块为准** | [ ] 待建 |
| PO-03 | 红蓝军对抗 | 多空报告互攻；用户须声明采纳方及理由 | [ ] 待建 |
| PO-04 | 结构化 Checklist | 价值理由 ≥2、技术面、情绪位、止损止盈；不合规拦截 | [ ] 待建 |
| PO-05 | 假设今日首开仓 | 隐藏成本价/盈亏%，对抗沉没成本 | [ ] 待建 |

### 2.2 P1 — 情绪与交互

| ID | 能力 | 说明 | 状态 |
|----|------|------|------|
| PO-06 | **情绪面量化（整模块）** | 融资融券、涨跌停、恐慌贪婪等；须与技术+价值联合解读 | [ ] 待建 |
| PO-07 | 锚定防御 | 模糊区间概率估值，减少盯成本/历史高点 | [ ] 待建 |
| PO-08 | Web / CLI | 发起分析、看板、Checklist、红蓝对抗 | [ ] 待建 |

### 2.3 P2 — 复盘与扩展信息面

| ID | 能力 | 说明 | 状态 |
|----|------|------|------|
| PO-09 | 复盘归因 | 交易后胜率、badcase、规则反哺 Checklist | [ ] 待建 |
| PO-10 | 组合级相关性 | 单票决策对整体组合的影响 | [ ] 待建 |
| PO-11 | 宏观/政策/治理事件层 | product-overview §4.3 开放项 | [ ] 待规划 |

---

## 3. 技术面待办

来源：[features/tech-analysis.md](features/tech-analysis.md) §2.2–§2.3

| ID | 功能 | 优先级 | 说明 | 建议 OpenSpec | 状态 |
|----|------|--------|------|---------------|------|
| F-17 | 筹码分布 | P2 | AKShare `stock_cyq_em`；获利/套牢比例 | `add-chip-distribution` | [ ] 待建 |
| F-18 | K 线形态识别 | V2 | 锤头、吞没、十字星等 | `add-pattern-recognition` | [ ] 待建 |
| F-19 | 布林带 | V2 | 均值 ± N×σ；波动率收缩/扩张 | `add-bollinger-bands` | [ ] 待建 |
| — | 月 K 线 | — | D-7 已决策：**暂不实现** | — | 已决策不做 |

### 3.1 技术面对外交付（与产品 PO-08 重叠）

| 项 | 说明 | 状态 |
|----|------|------|
| Tech API/CLI | 暴露 `TechAnalyzer.analyze(code, offline=True)` | [x] CLI `report tech` |
| 双轨入口 | 暴露 `DualTrackAnalyzer.analyze(code)` | [ ] 待建 |

---

## 4. 价值面待办

来源：[features/value-analysis.md](features/value-analysis.md) §14

### 4.1 V1.x 增强（非阻塞，提升完整度）

| ID | 项 | 说明 | 建议 change | 状态 |
|----|-----|------|-------------|------|
| T-1 | 安全边际按原型差异化 | 当前统一 MOS 阈值 | — | [ ] 待设计 |
| T-2 | value_trap High 专项提示 | 摘要已进 warnings；High 级专项逻辑待做 | — | [ ] 待建 |
| T-3 | 银行指标 E2E 验证 | 净息差/不良率等完整度 | value-bank-e2e | [x] 路由+聚合 ✅；专项指标 🔧 常 missing |
| T-7 | 行业代码映射 Router | SW/CS 行业 → 原型（替代纯财务启发） | — | [ ] 待建 |
| T-8 | 人工覆盖持久化 | VA-CLS-2，落 dao | — | [ ] 待建 |
| T-15 | V2 原型显式降级 | 如平安 →「保险方法论暂缺」 | — | [ ] 待建 |

### 4.2 数据与集成

| ID | 项 | 说明 | 建议 change | 状态 |
|----|-----|------|-------------|------|
| D-E | 历史 PE/PB 序列 | Baostock 季末价÷epsTTM → `historical_pe`；解锁 `pe_relative` | `fix-baostock-data-quality` | [x] Baostock 层已实现 |
| D-F | FCF 推导链 | operCashTTM → CFOToOR×revenue → net_income×fcf_rate | `fix-baostock-data-quality` | [x] 已实现 |
| D-G | 聚合可信度守卫 | 核心方法全 N/A 时标「不可信」 | `fix-baostock-data-quality` | [x] 已实现 |
| D-H | Tushare 财报补全 | income/cashflow/balance → 真实财报字段 | `add-tushare-financials` | [x] 已实现 |
| E | REST API | `POST /api/v1/analysis/value` 等 | `add-value-api`（待定） | [ ] 待建 |
| F | CLI / 看板 | `python -m apps.cli sync/report ...` | 与 PO-08 合并 | [x] CLI 核心 |
| G | LLM ContextPack | 价值面块注入双轨 + LLM 叙述 | 与 PO-02 合并 | [ ] 待建 |

### 5.2 数据质量修复（fix-baostock-data-quality）

> OpenSpec change：`openspec/changes/fix-baostock-data-quality/`  
> 状态：✅ 已实现

| 修复项 | 说明 | 验证（600519） |
|--------|------|----------------|
| `net_income` TTM | `epsTTM × shares_outstanding`（Provider 层跨源合并后推导） | ~825 亿 |
| `historical_pe` | 季末收盘价 ÷ epsTTM，最近 2 年 8 季 | 8 个有效值 |
| `growth_rate` | 2 年 epsTTM CAGR，退化 YOYNI | ~3.1% |
| FCF 推导链 | operCashTTM → CFOToOR×revenue → net_income×fcf_rate | DCF 可运行 |
| Aggregator 守卫 | dcf + pe_relative 均 N/A → confidence「不可信」 | — |
| sync 稳定性 | 禁用 AKShare、Baostock 单 session fetch_all、CLI 静默 WARNING | sync ~30s |

**600519 验证结果（2026-06-28）：**

- pe_relative：1452.78（目标 1380–1480，✅）
- DCF：773.44（可运行，FCF 仍为 fallback 估算）
- 聚合中位：810（较修复前 405 翻倍；全方法 ±5% 待层 B）

### 5.3 Tushare 财报接入（add-tushare-financials）

> OpenSpec change：`openspec/changes/add-tushare-financials/`  
> 状态：✅ 数据层已实现（2026-07-04）

| 能力 | 说明 |
|------|------|
| 四表接入 | `income` / `cashflow` / `balancesheet` / `fina_indicator`（需 ≥2000 积分） |
| net_debt | `money_cap` + 短/长期借款推导 |
| 年报优先 | income/cashflow/balance/fina 优先取 1231 年报 |
| 多源合并 | Tushare 财报字段覆盖 Baostock 估算；离线按 `fetched_at` 取最新快照 |

**600519 验证（Tushare priority=1，2026-07-04）：**

| 字段/方法 | 实测 | 备注 |
|-----------|------|------|
| revenue | 1,688 亿 | Tushare 年报 |
| fcf | 584 亿 | Tushare 年报 OCF − capex |
| net_debt | -517 亿 | 净现金 |
| pe_relative | 1,440 | ✅ 对齐 Gemini |
| ev_ebitda | 1,628 | ✅ 含净现金溢价 |
| 聚合中位 | 838 | DCF/EPV 仍偏低（growth_rate/WACC 假设，非数据缺口） |

**600519 验证（fix-valuation-assumptions，2026-07-04）：**

| 字段/方法 | 修复前 | 修复后 | 备注 |
|-----------|--------|--------|------|
| eps | 21.76（季报） | 65.85（TTM） | derived:ttm |
| pe_relative | 477 | 1,444 | ✅ 对齐 Gemini |
| DCF | 329 | 899 | β-CAPM 5.4% + g floor 8% |
| 聚合中位 | 521 | 1,012 | ✅ task 7.5 已解决 |

**600519 验证（fix-offline-annual-fcf，2026-07-04）：**

| 字段/方法 | 修复前 | 修复后 | 备注 |
|-----------|--------|--------|------|
| FCF（离线） | 263（Q1 误用） | 584 | 年报 20251231 优先 |
| DCF | 899 | 1,950 | FCF 基数修正 |
| 聚合中位 | 1,012 | 1,404 | ✅ 对齐 LLM 1340–1474 |
| 根因 | fetched_at 最新 Q1 覆盖年报 | 分层合并 + 优先级守卫 | — |

**CLI 进度**：`sync`/`report` 默认输出阶段性进度（`logging.cli_progress`），可用 `--quiet` 关闭。

### 4.3 V2 原型与方法（明确后置）

| ID | 项 | 样本股 | 状态 |
|----|-----|--------|------|
| T-4 | 保险 EV/NBV 模型 | 中国平安 | [ ] V2 |
| T-5 | 军工·订单驱动模型 | 中船科技 | [ ] V2 |
| T-6 | 成长（科技）PEG/PS/Rule of 40 | 华测导航 | [ ] V2 |
| — | 成长 + 制造周期情景 DCF | 比亚迪 | [ ] V2 |
| — | 周期 + 资产重估 | 北大荒 | [ ] V2 |
| — | 现金流 + 广告周期 | 分众传媒 | [ ] V2 |
| T-12 | Cyclical 4 方法 + `CyclicalStock` | `cyclical_pb/pe/fcf/dividend` | [ ] V2 |

---

## 5. 建议实施顺序（ROI 参考）

按「先能用、再完整、后护航」排列；可按实际情况调整。

| 阶段 | 建议项 | 理由 | 状态 |
|------|--------|------|------|
| **A** | CLI 核心入口（`add-cli-core`） | 已有 `DualTrackAnalyzer`，缺对外入口 | ✅ 已实现 |
| **B** | LLM 综合报告（PO-02 / G） | 双轨结果可直接打包；情绪维可后补 | ⬜ 待立项 |
| **C** | 历史 PE/PB（D-E） | 解锁 relative 估值，价值面完整度提升明显 | ✅ Tushare 5 年季末采样 + DCF/EPV 语义注释（add-historical-multiples-5yr） |
| **C2** | Tushare 财报补全（D-H） | 真实 revenue/fcf/net_debt；pe_relative + ev_ebitda 达标 | ✅ add-tushare-financials |
| **C3** | 估值假设层修复 | TTM EPS、β-CAPM、growth floor；聚合中位对齐 LLM | ✅ fix-valuation-assumptions |
| **C4** | 离线年报 FCF 合并 | Q1 快照不再覆盖 1231 年报 FCF | ✅ fix-offline-annual-fcf |
| **D** | F-17 筹码分布 | 数据源明确，技术面 P2 增量 | ⬜ 待立项 |
| **E** | 情绪面（PO-06） | 补全三维框架 | ⬜ 待立项 |
| **F** | 决策护航（PO-03~05） | Checklist / 红蓝对抗 / 首开仓 | ⬜ 待立项 |
| **G** | Web 看板（PO-01 / PO-08） | 依赖前述 API 与报告形态稳定 | ⬜ 待立项 |
| **H** | 价值 V2 原型 / 技术 V2 指标 | 非 V1 阻塞 | ⬜ 待立项 |

---

### 5.1 CLI 核心设计（add-cli-core）

> OpenSpec change：`openspec/changes/add-cli-core/`  
> 状态：✅ 已实现（运行 `/opsx-archive add-cli-core` 归档）

#### 命令签名

```bash
# 同步单票数据（唯一联网路径）
python -m apps.cli sync <code>              # 拉价值快照 + K线，写缓存
python -m apps.cli sync <code> --realtime   # 同上 + 叠加当日实时报价，写当日行

# 技术面报告（严格离线，不联网）
python -m apps.cli report tech <code>
python -m apps.cli report tech <code> --json
python -m apps.cli report tech <code> --output reports/<code>_tech.txt

# 价值面报告（严格离线，不联网）
python -m apps.cli report value <code>
python -m apps.cli report value <code> --json
python -m apps.cli report value <code> --output reports/<code>_value.txt
```

#### 核心设计决策

| 决策 | 描述 |
|------|------|
| **D-1 sync/report 严格分离** | `report` 永不联网；要新数据必须先 `sync` |
| **D-2 sync 写当日 K 线** | `sync --realtime` 结果持久化写入 `KlineRepo`（`persist_today=True`），供后续 `report tech` 离线读取 |
| **D-3 离线价值面重建** | 新增 `StockDataProvider.get_stock_data_offline(code)`，从 snapshot 合并读取，不联网 |
| **D-4 Formatter 纯函数** | `src/apps/formatters.py` 两个纯函数，与 CLI 解耦，支持 text / JSON 两种输出 |
| **D-5 argparse 不引入额外依赖** | 使用标准库 `argparse`，V1 无需 `typer` / `click` |
| **D-6 数据时效水印** | 报告头部输出「K线末行: YYYY-MM-DD \| quote_mode: eod/realtime」 |

#### 受影响文件

| 文件 | 变更类型 |
|------|----------|
| `src/apps/cli.py` | 新建 |
| `src/apps/formatters.py` | 新建 |
| `src/data_provider/kline_provider.py` | 新增 `offline` + `persist_today` 参数 |
| `src/data_provider/provider.py` | 新增 `get_stock_data_offline()` |
| `scripts/fetch_value_data.py` | 重构为薄包装 |
| `test/apps/test_cli_*.py` | 新建 |

---

## 6. 文档与代码对齐提醒

以下 MRD 段落**可能滞后于代码**，更新功能后请同步：

| 文档 | 位置 | 已知滞后 |
|------|------|----------|
| [tech-analysis.md](features/tech-analysis.md) | §10 路线图 | F-16/F-20/双轨仍标「待建」，实际已 ✅ |
| [product-overview.md](product-overview.md) | 最后更新 2026-05-31 | 双轨 Facade 已交付，情绪/LLM/看板仍待建 |
| [value-analysis.md](features/value-analysis.md) | §14 待实现 | 部分 T-* 项状态需随实现更新 |

---

## 7. 检查方式

1. **功能是否完成**：在本文件对应 `[ ]` 改为 `[x]`，并在「变更记录」追加一行。  
2. **是否需 OpenSpec**：非 trivial 功能先 `/opsx-propose <change-name>`，实现后 `/opsx-archive`。  
3. **是否需更新 MRD 细则**：归档时合并 delta spec → `docs/mrd/features/*.md`。  
4. **快速代码核对**：
   - 价值面：`src/service/value/analyzer.py`
   - 技术面：`src/service/tech/analyzer.py`
   - 双轨：`src/service/dual_track/analyzer.py`
   - 活跃 change：`openspec list`

---

## 8. 统计摘要（2026-06-28）

| 类别 | 已交付（核心） | 待办（粗计） |
|------|----------------|--------------|
| 产品级 P0 | 双轨 Facade | 5 项（看板、LLM、红蓝、Checklist、首开仓） |
| 产品级 P1 | — | 3 项（情绪、锚定、Web/CLI） |
| 技术面 V1.x | F-16、F-20 | 3 项（F-17~19，含 V2） |
| 价值面 V1.x 增强 | 编排 P0 | ~6 项（T-1/2/3/7/8/15 + D-E） |
| 价值面 V2 | — | 7+ 项（原型与方法扩展） |

**OpenSpec 队列：** `add-tushare-financials`（层 B，待 Token 升级后实施）
