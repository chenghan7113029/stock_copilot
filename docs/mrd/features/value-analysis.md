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
| 2026-06-14 | fix-value-data-pipeline-e2e | §9 补充 E2E 验收机制与字段缺口说明 |

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

### 关键设计决策

- **多源独立管理**：每个数据源独立存储（来源维度），按 `priority` 排序 + 自动 failover，对齐 `daily_stock_analysis.DataFetcherManager`；
- **缺失语义**：字段无法获取时置 `None`（区别于真实零值），加入 `missing_fields`；下游方法据此判断可靠性；
- **持久化**：SQLAlchemy + SQLite（默认），`db.url` 可配置切换 MySQL；唯一键 `(code, source, report_period)` upsert；**禁止写本地 csv**；
- **配置驱动**：`config/app.yaml` 的 `data_sources.enabled` 控制启用哪些源及其优先级；

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

## 13. 下一步

1. 本 MRD 细则评审确认；
2. 对 V1 三原型发起 OpenSpec 提案：`/opsx-propose add-value-analysis-v1`，在 design 阶段定数据源与模块边界；
3. 归档后将本细则增量合并回 [product-overview.md](../product-overview.md) §5.1.1 与 [engineering-conventions.md](../../dev/engineering-conventions.md)（若涉及模块边界）。
