# 价值面分析模块 — 需求细则（MRD）

> 最后更新：2026-06-13  
> 状态：细则 v1（探索沉淀，待 propose 转技术设计）  
> 上级文档：[product-overview.md](../product-overview.md) §5.1.1  
> 关联设计：[value-analysis-integration.md](../design/value-analysis-integration.md)  
> 参考实现：`valueinvest/`、`FinanceToolkit/`

## 变更记录

| 日期 | Change | 摘要 |
|------|--------|------|
| 2026-05-31 | init | 从接入方案提取需求摘要 |
| 2026-06-13 | value-explore | 基于自选股探索，确立估值原型分类、方法论路由、输出规格、范围与优先级 |
| 2026-06-14 | add-tushare-data-source | §9 补充 Tushare Pro 数据源与 Token 配置 |

---

## 1. 模块目标

**一句话：** 基于公开数据与"按股票类型匹配的"估值方法论，对单只股票产出 **合理估值区间 + 安全边际 + 当前价所处分位** 的价值面判断，作为双轨分析的价值面输入。

**要解决的核心问题：**

- 买股票即买公司一部分，需识别公司合理价值，在价格显著低于价值时发现机会；
- 过滤垃圾股 / 暴雷风险；
- 大跌时提供"核心竞争力未变"的长期持有依据；
- **不同类型的股票必须用不同的估值方法**（银行不能用 DCF、保险要看内含价值等）。

---

## 2. 范围与优先级

### 2.1 第一版范围（V1）

聚焦自选股中占比最大、`valueinvest` 最成熟的 **3 类估值原型**：

| 原型 | 自选样本 | V1 |
|------|----------|----|
| 银行 | 工行、交行、建行、招行 | ✅ |
| 高股息·类债 | 长江电力 | ✅ |
| 高质量价值成长 | 贵州茅台 | ✅ |

### 2.2 后续版本（V2 待补）

| 原型 | 自选样本 | 状态 | 原因 |
|------|----------|------|------|
| 保险 | 中国平安 | 🔜 V2 | `valueinvest` 无内含价值（EV/NBV）模型，需新增 |
| 军工·订单驱动 | 中船科技 | 🔜 V2 | DCF 在此类股票不稳，靠在手订单 + 资产重估 |
| 成长（科技） | 华测导航 | 🔜 V2 | PEG/PS/Rule of 40，valueinvest 已有方法，待接入 |
| 成长 + 制造周期 | 比亚迪 | 🔜 V2 | 成长 + 周期叠加，需情景化 DCF |
| 周期 + 资产 | 北大荒 | 🔜 V2 | 大宗周期 + 土地重估 |
| 现金流 + 广告周期 | 分众传媒 | 🔜 V2 | 轻资产高 FCF 但顺周期 |

> V1 未覆盖的原型，分类时应**显式标注"该原型方法论暂缺，降级为相对估值并提示置信度低"**，不得静默套用错误方法。

---

## 3. 估值原型分类体系

价值面分析的前提是**先确定股票属于哪种估值原型**，再路由到对应方法论。

### 3.1 原型定义（完整 9 类，标注版本）

| # | 原型 | 关键特征 | 不适用的方法 | 版本 |
|---|------|----------|--------------|------|
| 1 | 银行 | 高杠杆、净息差驱动 | DCF、自由现金流类 | V1 |
| 2 | 高股息·类债 | 现金流极稳、高分红 | 高成长假设类 | V1 |
| 3 | 高质量价值成长 | 高 ROIC、强护城河、稳定 FCF | NCAV、纯周期 | V1 |
| 4 | 保险 | 内含价值、新业务价值 | PB/PE 直接套用 | V2 |
| 5 | 军工·订单驱动 | 在手订单、资产重估 | DCF（极不稳） | V2 |
| 6 | 成长（科技） | 高研发、份额扩张 | NCAV、DDM | V2 |
| 7 | 成长 + 制造周期 | 资本开支大、产能扩张 | 单点 DCF | V2 |
| 8 | 周期 + 资产 | 大宗商品周期、资产重估 | 静态 PE | V2 |
| 9 | 现金流 + 广告周期 | 轻资产、顺经济周期 | 静态外推 | V2 |

### 3.2 分类机制：自动建议 + 人工可覆盖

```text
            ┌──────────────────────────┐
输入股票 →  │  自动分类器                │
            │  · 行业/板块代码映射        │
            │  · 财务特征启发（高杠杆=银行 │ → 建议原型 + 置信度
            │    高分红低成长=高股息 等）  │
            └────────────┬─────────────┘
                         │
                         ▼
            ┌──────────────────────────┐
            │  人工覆盖（可选）           │  ← 用户可手动指定/纠正原型
            │  · 记录覆盖原因             │     （如"招行=优质银行"）
            └────────────┬─────────────┘
                         ▼
                  最终原型 → 方法论路由
```

**需求点：**

- **VA-CLS-1**：系统按行业代码 + 财务特征自动建议估值原型，并给出置信度；
- **VA-CLS-2**：用户可手动覆盖原型，覆盖结果与原因须可持久化、可追溯；
- **VA-CLS-3**：自动分类无法判定或落入 V2 暂缺原型时，显式标注并降级，不静默误用方法。

> `valueinvest` 已有 `get_recommended_methods()` 做粗路由（银行/分红/成长/价值），可作为自动分类器起点，但需补 A 股行业映射与人工覆盖层。

---

## 4. 方法论清单与适用边界

`valueinvest` 已实现以下方法论，V1 直接复用，按原型挑选子集：

| 方法 | 类别 | 适用原型 | valueinvest |
|------|------|----------|-------------|
| PB 估值 | 相对/绝对 | 银行 | ✅ `bank.PBValuation` |
| 剩余收益模型 | 绝对 | 银行 | ✅ `bank.ResidualIncome` |
| DDM / 两阶段 DDM | 绝对 | 高股息、银行 | ✅ `ddm` |
| EPV（盈利能力价值） | 绝对 | 高股息、价值成长 | ✅ `epv` |
| Owner Earnings | 绝对 | 价值成长、高股息 | ✅ `quality.OwnerEarnings` |
| DCF / Reverse DCF | 绝对 | 价值成长、成长 | ✅ `dcf` |
| Graham Number / Formula / NCAV | 绝对 | 价值、银行辅助 | ✅ `graham` |
| PEG / GARP / Rule of 40 | 成长 | 成长（V2） | ✅ `growth` |
| EV/EBITDA | 相对 | 成长、价值成长 | ✅ `growth.EVEBITDA` |
| 相对估值（PE/PB 历史分位） | 相对 | 全部（分位计算） | ✅ `relative` |
| Altman-Z / Piotroski-F | 质量/风险 | 全部（财务健康） | ✅ `quality` |
| Beneish-M | 造假风险 | 全部（红旗） | ✅ `mscore` |
| 价值陷阱检测 | 风险 | 全部 | ✅ `value_trap`（见 §8 TODO） |
| 周期调整估值（PB/PE/FCF/股息） | 周期 | 周期类（V2） | ✅ `cyclical` |

**缺口（需后续新增）：** 保险内含价值（EV/NBV）模型、军工订单/资产重估模型。

---

## 5. 原型 → 方法论路由（V1 详细）

> 每个原型按"主方法 / 辅助方法 / 风险校验"分层。最终估值区间由主方法 + 辅助方法的结果聚合（见 §6）。

### 5.1 银行

| 层级 | 方法 |
|------|------|
| 主方法 | PB 估值、剩余收益模型 |
| 辅助方法 | DDM / 两阶段 DDM、Graham Number |
| 风险校验 | Altman-Z（财务健康）、相对估值（PB 历史分位） |
| 明确排除 | DCF、Reverse DCF、Magic Formula、Rule of 40 |

### 5.2 高股息·类债

| 层级 | 方法 |
|------|------|
| 主方法 | DDM、两阶段 DDM |
| 辅助方法 | EPV、Owner Earnings、Graham Number |
| 风险校验 | 股息可持续性（派息率、FCF 覆盖）、Altman-Z |
| 明确排除 | Rule of 40、高成长 DCF |

### 5.3 高质量价值成长

| 层级 | 方法 |
|------|------|
| 主方法 | DCF、EPV、Owner Earnings |
| 辅助方法 | Graham Formula、相对估值（PE 历史分位）、EV/EBITDA |
| 风险校验 | Piotroski-F、Beneish-M、护城河/ROIC 稳定性 |
| 明确排除 | NCAV |

---

## 6. 估值输出规格

> 与产品总览"反锚定 → 模糊区间概率估值"一致：**不输出单一公允价**，输出区间 + 安全边际 + 分位。

### 6.1 输出字段

| 字段 | 说明 |
|------|------|
| `fair_value_range` | 合理估值区间 [下界, 中枢, 上界]，由多方法结果聚合（中位/分布） |
| `current_price` | 当前价 |
| `margin_of_safety` | 安全边际 = (估值中枢 − 当前价) / 估值中枢，正值表示低估 |
| `price_percentile` | 当前价在估值区间中的所处分位（0%=区间下界，100%=上界） |
| `assessment` | 低估 / 合理 / 高估（基于安全边际阈值） |
| `confidence` | 置信度（可靠方法数、方法间一致性、数据完整度） |
| `method_breakdown` | 各方法的公允价、是否可靠、适用性，供解释与追溯 |
| `warnings` | 数据缺失、原型降级、红旗信号等提示 |

### 6.2 区间聚合规则（需求层，算法细节留技术设计）

- **VA-OUT-1**：区间须由"该原型路由命中的多个方法"的可靠结果聚合，单一方法不得直接作为区间；
- **VA-OUT-2**：剔除明显不适用 / 数据缺失的方法结果后再聚合；
- **VA-OUT-3**：安全边际阈值**按原型可差异化**（如银行/高股息容忍度与成长股不同），V1 可先用统一阈值并标注为 TODO；
- **VA-OUT-4**：分位用于反锚定展示，须避免暴露"历史最高/最低价"等易锚定数字（呼应产品总览 §5.2 锚定防御）。

### 6.3 与确定性原则一致

- 所有数值来自确定性估值计算（`data_provider` → 估值方法），**不经 LLM 生成**；
- LLM 仅负责叙述与多空论述，引用本模块的数值结果。

---

## 7. 方法论 → 数据需求（V1）

> 字段来自 `valueinvest.Stock` 数据模型，按 V1 三原型所需汇总。数据**获取方式**见 §9（留 propose）。

| 数据类别 | 字段（示例） | 银行 | 高股息 | 价值成长 |
|----------|--------------|:----:|:-----:|:-------:|
| 基础行情 | 当前价、总股本、市值 | ✅ | ✅ | ✅ |
| 每股指标 | EPS、BVPS、每股分红 | ✅ | ✅ | ✅ |
| 盈利 | 营收、净利润、ROE/ROIC | ✅ | ✅ | ✅ |
| 现金流 | 自由现金流、经营现金流、capex | — | ✅ | ✅ |
| 资产负债 | 总资产、总负债、净负债 | ✅ | ✅ | ✅ |
| 分红 | 股息率、派息率、分红历史 | ✅ | ✅ | ⚪ |
| 历史估值 | 历史 PE / PB 序列（算分位） | ✅ | ✅ | ✅ |
| 银行专用 | 净息差、不良率、拨备覆盖率* | ✅ | — | — |
| 质量/风险 | Altman-Z、Piotroski、Beneish 所需明细 | ✅ | ✅ | ✅ |

✅必需 ⚪可选 —不适用 *`valueinvest` 现模型未必用到，列为银行原型数据完整性 TODO

**需求点：**

- **VA-DATA-1**：每个方法须声明所需字段；字段缺失时该方法标注"数据缺失不可靠"，不参与区间聚合；
- **VA-DATA-2**：数据须带**来源与时效**标注（呼应产品总览数据时效要求）；
- **VA-DATA-3**：A 股财报数据完整度（尤其银行专用指标、历史 PE/PB 序列）须在 propose 阶段验证。

---

## 8. 价值陷阱检测（TODO，非 V1 重点）

> 用户 user_story 明确点出"便宜但不涨/越跌越便宜"是价值面最大短板。

- `valueinvest` 已有 `value_trap.ValueTrapDetector`（营收 CAGR、利润率趋势、ROE 趋势、市场份额、行业 AI 脆弱性等）。
- **TODO（V1.x / V2）**：将价值陷阱检测作为价值面输出的风险校验项，命中时降低置信度并在 `warnings` 提示"疑似价值陷阱"。
- 第一期可不实现，但 MRD 保留该需求位，避免后续遗漏。

---

## 9. 数据获取方式（V1 已确定）

> 已通过 change `add-value-data-provider-v1` 完成实现，本节为归档后的正式记录。

### 数据源

| 数据源 | 优先级 | Token 需求 | 说明 |
|--------|--------|-----------|------|
| AKShare | 1（主源） | 无 | 行情 + 三大财报 + 分红 + 财务指标；字段最全 |
| Baostock | 2（第二源） | 无 | 行情 + 季频财务；交叉校验用 |
| Tushare Pro | 3（第三源，可上调） | **是** | 财报兜底强；需 Token，见下方配置 |

### 关键设计决策

- **多源独立管理**：每个数据源独立存储（来源维度），按 `priority` 排序 + 自动 failover，对齐 `daily_stock_analysis.DataFetcherManager`；
- **缺失语义**：字段无法获取时置 `None`（区别于真实零值），加入 `missing_fields`；下游方法据此判断可靠性；
- **持久化**：SQLAlchemy + SQLite（默认），`db.url` 可配置切换 MySQL；唯一键 `(code, source, report_period)` upsert；**禁止写本地 csv**；
- **配置驱动**：`config/app.yaml` 的 `data_sources.enabled` 控制启用哪些源及其优先级；

### Tushare Token 配置

1. 在 [tushare.pro](https://tushare.pro) 注册并获取 Token
2. 本地编辑 `config/app.yaml`（已在 `.gitignore`），在 `data_sources.enabled` 中启用 tushare 并填写 `token`
3. 或设置环境变量 `TUSHARE_TOKEN`（CI / 临时验证）
4. **切勿**将 Token 提交到 Git 或粘贴到公开渠道

验收命令：

```bash
pytest -m network test/e2e/test_tushare_pipeline.py -v
```

无 Token 时该测试自动 skip，不影响离线 CI。

**Tushare 积分要求**：新账号需在 [tushare.pro](https://tushare.pro) 完成实名认证并积累积分后，方可调用 `stock_basic`、`daily`、`fina_indicator` 等接口。积分不足时网络 E2E 会 skip 并提示「无接口权限」。

### 关键修复（fix-value-data-pipeline-e2e）

- **`fetch_all` 签名统一**：`BaseFetcher.fetch_all(code, exchange)` 与 `fetch_quote`/`fetch_fundamentals` 对齐；
- **Baostock 季频参数**：`query_*_data` 使用有效 `(year, quarter)` 参数（1–4），支持最多 4 季回溯；单次 session 减少登录次数；
- **Provider 持久化解耦**：先完成全部网络取数，再开短生命周期 Session 批量 upsert，消除 SQLite `database is locked`；
- **Config Bootstrap**：`src/common/config_loader.py` 在 `app.yaml` 缺失时自动从 example 复制；

### E2E 验收与字段缺口报告

通过 `pytest -m network test/e2e/` 可运行端到端验收，产出两份报告：

| 报告 | 路径 | 内容 |
|------|------|------|
| 字段覆盖率 | `reports/value-data-field-coverage-*.json` | 每只样本股 + 跨样本聚合的字段覆盖详情 |
| 字段缺口 | `reports/value-data-field-gaps-*.json` | blocked 字段清单，供产品决策 |

**当前已知缺口（AKShare 不稳定时）**：bvps, dividend_*, ebit, fcf, market_cap, operating_margin, revenue, roic, shareholder_equity, shares_outstanding, total_assets/liabilities。这些字段需等 AKShare API 稳定后重新验证，或引入备选数据源。

使用方法：

```bash
# 采集全部样本（6 只）并打印摘要
python scripts/fetch_value_data.py

# E2E 验收并生成报告
pytest -m network test/e2e/ -v -s
```

### 代码落点

| 模块 | 路径 |
|------|------|
| 数据模型 | `src/common/models/stock_data.py` |
| AKShare fetcher | `src/data_provider/akshare/` |
| Baostock fetcher | `src/data_provider/baostock/` |
| 多源管理 | `src/data_provider/manager.py` |
| Provider Facade | `src/data_provider/provider.py` |
| 完备性校验 | `src/data_provider/validation/completeness.py` |
| 字段覆盖分析 | `src/data_provider/validation/field_coverage.py` |
| DAO 持久化 | `src/dao/` |
| 配置加载器 | `src/common/config_loader.py` |
| E2E 采集脚本 | `scripts/fetch_value_data.py` |

---

## 10. 验收标准（Given/When/Then）

### 场景 1：银行股价值面分析

- **Given** 用户请求分析 `工商银行 601398`
- **When** 调用价值面分析
- **Then** 系统自动判定原型为"银行"，路由到 PB / 剩余收益 / DDM，**排除 DCF**，输出估值区间 + 安全边际 + 当前价分位，并附各方法明细与置信度

### 场景 2：高股息股价值面分析

- **Given** 用户请求分析 `长江电力 600900`
- **When** 调用价值面分析
- **Then** 原型判定为"高股息·类债"，以 DDM 为主，输出区间 + 股息可持续性校验

### 场景 3：价值成长股价值面分析

- **Given** 用户请求分析 `贵州茅台 600519`
- **When** 调用价值面分析
- **Then** 原型判定为"高质量价值成长"，以 DCF/EPV/Owner Earnings 为主，输出区间，并含 Piotroski-F / Beneish-M 风险校验

### 场景 4：人工覆盖原型

- **Given** 自动分类将某股判为原型 A
- **When** 用户手动覆盖为原型 B 并填写原因
- **Then** 系统按原型 B 重新路由方法论并重算，覆盖记录可持久化追溯

### 场景 5：V2 暂缺原型降级

- **Given** 用户请求分析 `中国平安 601318`（保险，V2）
- **When** 调用价值面分析
- **Then** 系统标注"保险原型方法论暂缺"，降级为相对估值并明确提示置信度低，**不静默套用 PB/PE 误判**

### 场景 6：输出反锚定

- **Given** 任一股票的价值面结果
- **When** 展示给用户
- **Then** 以估值区间 + 分位呈现，不直接暴露历史最高/最低价等易锚定数字

---

## 11. 开放问题 / TODO 清单

| 编号 | 项 | 阶段 |
|------|----|------|
| T-1 | 安全边际阈值是否按原型差异化（§6.2 VA-OUT-3） | V1.x |
| T-2 | 价值陷阱检测接入（§8） | V1.x / V2 |
| T-3 | 银行专用指标（净息差/不良率等）数据完整度验证 | propose |
| T-4 | 保险内含价值（EV/NBV）模型 | V2 |
| T-5 | 军工·订单驱动估值模型 | V2 |
| T-6 | 数据源选型与字段映射 | propose |
| T-7 | 自动分类器的 A 股行业映射规则 | propose |
| T-8 | 人工覆盖的持久化方案（落 dao） | 技术设计 |

---

## 12. 与现有资产映射

| MRD 需求 | 复用资产 | 缺口 |
|----------|----------|------|
| 方法论清单 | `valueinvest.valuation.*`（23 种） | 保险、军工模型 |
| 原型路由 | `ValuationEngine.get_recommended_methods()` | A 股行业映射、人工覆盖层 |
| 数据模型 | `valueinvest.Stock` | A 股字段完整度 |
| 数据获取 | `daily_stock_analysis/data_provider/`、valueinvest fetcher | 选型留 propose |
| 价值陷阱 | `valueinvest.value_trap` | 接入编排 |

---

## 13. 方法论实现计划（Phase 0–8）

> 本节记录方法论代码层的实现路线，供后续 propose 使用。方法论不含原型路由，
> 仅关注"计算器库"的建设；路由层（§5）作为独立 change 后置实现。
>
> 代码落点：`src/service/value/valuation/`（对齐 §3.1 目录约定）
> 参考文档：[docs/design/valuation-methods-reference.md](../design/valuation-methods-reference.md)

### 13.1 设计决策（已确定）

#### D-A：缺失参数配置化 + WACC 推导

所有估值方法的假设参数（折现率、增长率、股权成本等）均通过 `AssumptionProvider` 配置化，
并从 `StockData` 字段按以下优先级推导：

| 参数 | 推导来源（优先级高→低） |
|------|------------------------|
| `discount_rate` / WACC | `interest_expense/total_debt` → CAPM(β·ERP) → `cost_of_capital` 字段 → 配置默认 10% |
| `growth_rate_1_5` | `StockData.growth_rate` × 放大系数 → 配置默认 5% |
| `growth_rate_6_10` | 配置默认 3% |
| `terminal_growth` | 配置默认 2% |
| `dividend_growth_rate` | `StockData.dividend_growth_rate` → 配置默认 3% |
| 无风险利率 | A 股：中国 10 年期国债收益率（配置，默认 1.80%）；USD：4.30% |
| 股权风险溢价 | 配置默认 6.0% |
| AAA 债券收益率（负债成本 fallback） | 配置默认 5.30% |
| 税率 | `StockData.tax_rate` → 配置默认 25% |

WACC 计算公式（port 自 `ref/valueinvest/valueinvest/roic/wacc.py`）：

```
WACC = (E/V) × Re + (D/V) × Rd × (1 - T)
Re = Rf + β × ERP（有 β 时），或直接用 cost_of_capital（简化）
Rd = interest_expense / total_debt（有数据时），或 aaa_corporate_yield（fallback）
```

#### D-B：历史 PE/PB 序列

`pe_relative` / `pb_relative` 两种相对估值方法依赖历史倍数序列（`historical_pe: List[float]`）。
本期 V1 方法论实现中：

- 在 `StockData` 扩展 `historical_pe` / `historical_pb` 字段（可空列表）
- data_provider 层需新增历史 K 线 + 历史财报逐季计算支持（**独立 change**，非本期）
- 本期实现中若字段为空，`pe_relative` / `pb_relative` 返回 `applicability="Not Applicable"`（不阻断其他方法）
- 单元测试级别：fixture 注入历史序列，验证计算结果与 `ref/valueinvest` ±0.1% 一致

#### D-C：验收标准

| 情形 | 标准 |
|------|------|
| 相同输入（fixture）vs ref/valueinvest | 公允价差异 ≤ ±0.1% |
| `StockData.xxx = None` 触发缺失 | 方法返回 `missing_fields` 含该字段，`fair_value=0`，不抛异常 |
| `StockData.xxx = 0.0`（真实零值） | 按真实 0 处理，不作为缺失（区别 None 语义） |
| applicability="Not Applicable" | 不参与区间聚合，但记录在 `method_breakdown.warnings` |

#### D-D：None vs 0 贯穿全库

原 `ref/valueinvest` 的 `DataValidator` 把 `value == 0` 视为缺失。
Port 时必须改为：`None` = 缺失，`0.0` = 真实零值。

### 13.2 实现 Phase 划分

> **状态（2026-06-21）**：Phase 0–3 已在 `add-valuation-methods-core` 归档完成；Phase 4–7 已在 `add-valuation-methods-full` 实现（Owner Earnings、DCF 族、质量评分、成长/相对估值共 13 种 method_key 已注册至 `default_engine()`）。

#### Phase 0 — 基础设施 ✅

目标：建立方法论层骨架，可离线跑通最小 fixture。

| 任务 | 文件 | 说明 |
|------|------|------|
| Port `ValuationResult`、`ValuationRange`、`BaseValuation` | `valuation/base.py` | 改 None 语义（D-D） |
| 新增 `AssumptionProvider` | `valuation/assumptions.py` | 配置化参数（D-A） |
| 新增 `StockDataAdapter` | `valuation/adapter.py` | `StockData` → 估值输入的 duck-typing |
| Port `ValuationEngine`（注册表骨架）| `valuation/engine.py` | `run_single` / `run_all` |
| 单元测试：None 语义、adapter 转换 | `test/service/value/test_base.py` | — |

#### Phase 1 — Graham 体系（字段轻、最快验证） ✅

| 任务 | 文件 | 关键输入 |
|------|------|----------|
| Port `GrahamNumber` | `valuation/graham.py` | eps, bvps |
| Port `GrahamFormula` | `valuation/graham.py` | eps, growth_rate, aaa_yield |
| Port `NCAV` | `valuation/graham.py` | current_assets, total_liabilities |
| 单元测试 ±0.1% | `test/service/value/test_graham.py` | fixture 贵州茅台、工商银行 |

#### Phase 2 — 银行专用 ✅

| 任务 | 文件 | 关键输入 |
|------|------|----------|
| Port `PBValuation` | `valuation/bank.py` | bvps, roe, cost_of_equity |
| Port `ResidualIncome` | `valuation/bank.py` | bvps, roe, 预测期 |
| 单元测试 ±0.1% | `test/service/value/test_bank.py` | fixture 工商银行 601398 |

#### Phase 3 — 股息模型 ✅

| 任务 | 文件 | 关键输入 |
|------|------|----------|
| Port `DDM` | `valuation/ddm.py` | dividend_per_share, dividend_growth_rate, cost_of_capital |
| Port `TwoStageDDM` | `valuation/ddm.py` | 同上 + 两阶段参数 |
| 单元测试 ±0.1% | `test/service/value/test_ddm.py` | fixture 长江电力 600900 |

#### Phase 4 — 盈利力价值 ✅

| 任务 | 文件 | 关键输入 |
|------|------|----------|
| Port `EPV` | `valuation/epv.py` | revenue, operating_margin, tax_rate, capex, cost_of_capital |
| Port `OwnerEarnings` | `valuation/quality.py` | net_income, depreciation, capex, nwc |
| 单元测试 ±0.1% | `test/service/value/test_epv.py` | fixture 茅台 + 长江电力 |

#### Phase 5 — DCF 族（最重，依赖 WACC） ✅

| 任务 | 文件 | 关键输入 |
|------|------|----------|
| Port WACC 计算 | `valuation/wacc.py` | StockData 字段推导（D-A） |
| Port `DCF` | `valuation/dcf.py` | fcf, shares, WACC, 三阶段增长率 |
| Port `ReverseDCF` | `valuation/dcf.py` | 同上 + current_price |
| 单元测试 ±0.1% | `test/service/value/test_dcf.py` | fixture 贵州茅台 |

#### Phase 6 — 质量/风险评分 ✅

> 这些方法产出分数而非公允价，不参与区间聚合，进入 `warnings`。

| 任务 | 文件 | 关键输入 |
|------|------|----------|
| Port `AltmanZScore` | `valuation/quality.py` | 资产负债各字段 |
| Port `PiotroskiFScore` | `valuation/quality.py` | 当期 + prior_* 对比字段 |
| Port `BeneishMScore` | `valuation/mscore.py` | Beneish 8 组件字段 |
| 单元测试 | `test/service/value/test_quality.py` | 阈值断言（Z>2.99 安全等） |

#### Phase 7 — 成长/相对估值 ✅

| 任务 | 文件 | 关键输入 |
|------|------|----------|
| Port `PEG`, `GARP`, `RuleOf40` | `valuation/growth.py` | eps, growth_rate, revenue_growth |
| Port `EVEBITDA` | `valuation/growth.py` | ebitda, net_debt, 行业基准倍数 |
| Port `MagicFormula` | `valuation/magic_formula.py` | ebit, ev, invested_capital |
| Port `PERelativeValuation` | `valuation/relative.py` | historical_pe（D-B：空时返回 Not Applicable） |
| Port `PBRelativeValuation` | `valuation/relative.py` | historical_pb（同上） |
| 单元测试 | `test/service/value/test_growth.py` | fixture 含历史序列 |

#### Phase 8 — 后置（非 V1 阻塞项）（ValueTrap + SBC 已完成；Cyclical 延迟至 V2）

> **状态（2026-06-21）**：`ValueTrapDetector`（value_trap）和 `SBCAnalysis`（sbc）已在 `add-valuation-methods-phase8` 实现。`default_engine()` 共注册 **23 个** method_key。Cyclical 4 种方法因依赖 V2 `CyclicalStock` 延迟至独立 change。

| 任务 | 文件 | 说明 | 状态 |
|------|------|------|------|
| Port `ValueTrapDetector` | `valuation/value_trap.py` | 5 维度陷阱检测 | 完成 |
| Port `SBCAnalysis` | `valuation/sbc.py` | 股权激励稀释分析 | 完成 |
| Cyclical 4 种方法 | `valuation/cyclical.py` | 依赖独立 `CyclicalStock`，V2 | V2 待做 |

### 13.3 V1 三原型冒烟清单（路由后置时的手动验证）

实现 Phase 0–7 后，可用以下 method_key 组合手动验证三原型覆盖：

| 原型 | 应跑通的 method_key |
|------|---------------------|
| 银行（工行 601398） | `pb`, `residual_income`, `ddm`, `graham_number`, `altman_z`, `pb_relative` |
| 高股息（长江电力 600900） | `ddm`, `two_stage_ddm`, `epv`, `owner_earnings`, `graham_number` |
| 价值成长（茅台 600519） | `dcf`, `epv`, `owner_earnings`, `graham_formula`, `ev_ebitda`, `piotroski_f`, `beneish_m` |

---

## 14. 下一步

1. 本 MRD 细则评审确认；
2. 对 V1 方法论层发起 OpenSpec 提案（推荐分两期）：
   - **Phase 0–2**：`/opsx-propose add-valuation-methods-core`（Graham + 银行，最小可交付）
   - **Phase 3–7**：`/opsx-propose add-valuation-methods-full`（完整 20 种方法）
3. 数据层扩展（历史 PE/PB）：`/opsx-propose add-historical-multiples-provider`
4. 归档后将本细则增量合并回 [product-overview.md](../product-overview.md) §5.1.1 与 [engineering-conventions.md](../../dev/engineering-conventions.md)。
