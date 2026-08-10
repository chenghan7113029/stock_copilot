# 价值面分析模块 — 需求细则（MRD）

> 最后更新：2026-06-21  
> 状态：细则 v3（方法论库 Phase 0–8 ✅；编排层 P0 ✅；上层集成 API/CLI/LLM 待建）  
> 上级文档：[product-overview.md](../product-overview.md) §5.1.1  
> 关联设计：[value-analysis-integration.md](../design/value-analysis-integration.md)  
> 参考实现：`valueinvest/`、`FinanceToolkit/`

## 变更记录

| 日期 | Change | 摘要 |
|------|--------|------|
| 2026-05-31 | init | 从接入方案提取需求摘要 |
| 2026-06-13 | value-explore | 基于自选股探索，确立估值原型分类、方法论路由、输出规格、范围与优先级 |
| 2026-06-14 | add-tushare-data-source | §9 补充 Tushare Pro 数据源与 Token 配置 |
| 2026-06-21 | valuation-methods-phase8 | §13 Phase 8 完成；新增 §14 实现现状与 Feature 缺口；更新 §8/§11/§12/§15 |
| 2026-06-21 | decision-historical-multiples | **D-E 已确定**：历史 PE/PB 序列由 Tushare Pro 提供（付费/积分由运营方承担） |
| 2026-06-21 | add-value-analyzer-core | 编排层 P0 交付：ValueAnalyzer Facade + ValuationAggregator + PrototypeRouter + ValueAnalysisResult；`ValuationEngine.run_selected()` 新增；§11/§12/§14 状态同步 |
| 2026-07-04 | add-tushare-financials | Tushare 四表财报接入（≥2000 积分）；net_debt 推导；多源财报覆盖；离线快照按 fetched_at 合并；600519 pe_relative/ev_ebitda 达标 |
| 2026-07-04 | fix-valuation-assumptions | TTM EPS 推导覆写季报 EPS；StockData.proto + β-CAPM 按原型折现率；growth_rate_1_5 按原型 floor；600519 聚合中位 ~1012、pe_relative ~1444、DCF ~899 |
| 2026-07-04 | fix-offline-annual-fcf | 离线合并分层选快照：行情取 fetched_at 最新、财报取 1231 年报；修复 Q1 FCF 263 亿覆盖年报 584 亿；600519 聚合中位 ~1404、DCF ~1950 |
| 2026-07-05 | add-historical-multiples-5yr | Tushare `daily_basic` 5 年季末采样 historical_pe/pb（20 点）；解锁 pb_relative（银行原型）；DCF/EPV 报告语义注释；600519 sync 后 pe/pb 各 20 点 |
| 2026-07-05 | add-prior-period-financials | Tushare 拉取 prior 年度（1231-1 年）财报，写入 6 个 prior_* 字段；600519 Piotroski F=6/9、Beneish M=-2.63 |
| 2026-08-01 | add-industry-prototype-router | 复用 Tushare 简化行业名称优先路由；保险、军工短路为 unknown，避免高杠杆误判为银行 |
| 2026-08-01 | add-prototype-fallback-message | 已识别但暂缺专用估值方法的保险/军工原型输出精确降级警告 |
| 2026-08-10 | add-v2-honesty-degrade | V2 第 0 刀诚实层：比亚迪/分众 code + 保险军工三层压制（警告、主评估「方法暂不适用」、双轨 UNKNOWN） |
| 2026-08-01 | add-value-trap-high-alert | value_trap High 生成独立高危警示并将 confidence 降一级；不改变 assessment 语义 |
| 2026-08-01 | add-prototype-override-persistence | 人工原型覆盖持久化：`prototype_overrides` + `value override` CLI；人工覆盖优先于行业与启发式判定 |
| 2026-07-05 | value-bank-e2e | `stock_basic` 写入 `industry`；Router 行业「银行」分类；Tushare 银行指标字段映射（NIM/NPL/拨备）；601398 offline report 银行原型 E2E |

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
- **VA-CLS-2**：✅ 用户可通过 `python -m apps.cli value override <code> <prototype> --reason "<原因>"` 手动覆盖原型；当前有效记录持久化于 `prototype_overrides`（`code`、`prototype`、`reason`、创建/更新时间），分析报告保留覆盖原因提示以便追溯；
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
| 价值陷阱检测 | 风险 | 全部 | ✅ `value_trap`（§13 Phase 8 已 port） |
| SBC 稀释分析 | 风险 | 成长/科技 | ✅ `sbc`（§13 Phase 8 已 port） |
| 周期调整估值（PB/PE/FCF/股息） | 周期 | 周期类（V2） | `ref/valueinvest` 有实现，V2 待 port（`CyclicalStock` 依赖） |

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
- **VA-DATA-3**：历史 PE/PB 序列数据源已确定为 Tushare Pro（§13.1 D-E）；银行专用指标：`industry` + 字段映射已接入，Tushare 标准 `fina_indicator` 对 601398 常无 NIM/NPL/拨备列（missing），估值不依赖该三字段。

---

## 8. 价值陷阱检测与 SBC 稀释分析

> 用户 user_story 明确点出"便宜但不涨/越跌越便宜"是价值面最大短板。

### 8.1 价值陷阱检测（已实现）

- **代码落点**：`src/service/value/valuation/value_trap.py` → `ValueTrapDetector`（method_key: `value_trap`）
- **五维度**：财务健康、业务恶化、护城河侵蚀、AI/技术脆弱性（占位）、股息可持续性
- **输出**：`details.output_type = "score"`；`details.overall_risk` = Low/Medium/High；不参与区间聚合
- **编排层现状**：评分摘要持续进入 `ValueAnalysisResult.warnings`（`ValuationAggregator` 实现）；`overall_risk=High` 时额外输出独立的「疑似价值陷阱」高危警示，并将 `confidence` 降一级（T-2 已实现）。`assessment` 仍仅表示估值安全边际结论，不混入风险标签。

### 8.2 SBC 稀释分析（已实现）

- **代码落点**：`src/service/value/valuation/sbc.py` → `SBCAnalysis`（method_key: `sbc`）
- **关键指标**：SBC/净利润、SBC/营收、年稀释率、调整后 EPS、稀释性评级
- **A 股注意**：多数公司 `StockData.sbc = None` → 返回 `applicability = "Not Applicable"`（预期行为）

---

## 9. 数据获取方式（V1 已确定）

> 已通过 change `add-value-data-provider-v1` 完成实现，本节为归档后的正式记录。

### 数据源

| 数据源 | 优先级 | Token 需求 | 说明 |
|--------|--------|-----------|------|
| AKShare | 1（主源） | 无 | 行情 + 三大财报 + 分红 + 财务指标；字段最全 |
| Baostock | 2（第二源） | 无 | 行情 + 季频财务；交叉校验用 |
| Tushare Pro | 3（第三源，可上调） | **是** | 财报兜底；**历史 PE/PB 序列主源（D-E）** |

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

**Tushare 积分要求**：财报接口（`income` / `cashflow` / `balancesheet` / `fina_indicator` / `dividend`）需 **≥2000 积分**（约 200 元/年）；120 积分档仅 `daily` 等基础接口。验证：`py scripts/verify_tushare_financials.py 600519`。

**历史 PE/PB（D-E）**：相对估值所需的 `historical_pe` / `historical_pb` 序列**仅通过 Tushare Pro 获取**；若接口需更高积分或付费包，由运营方自行解决，开发侧在 fetcher 中按权限 graceful 降级（字段保持 `None`）。

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

**当前已知缺口（value-bank-e2e 后）**：`historical_pe`/`historical_pb` 已由 Tushare 5 年季末采样提供；`pb_relative` 仅银行原型路由启用；DCF 与 EPV 分歧已在报告中标注语义；owner_earnings 偏高可能触发 IQR 过滤；Beneish 仍可能因 prior 期资产负债表细项不足而 Limited；银行 NIM/NPL/拨备覆盖率依赖 Tushare 接口字段，2000 积分 token 下 601398 常为 missing（不影响 PB/剩余收益/DDM 聚合）。

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

### 场景 5：V2 暂缺原型降级（三层诚实压制）

- **Given** 用户请求分析 `中国平安 601318`（保险）或 `比亚迪 002594`（成长+制造周期 code 白名单）或 `分众传媒 002027`
- **When** 调用价值面分析 / 双轨融合 / `report value`
- **Then** 系统同时满足：
  1. **精确警告**：说明缺什么专用方法、V1 通用方法为何易偏，并明示**不能作为买卖依据**（保险/军工与持仓 code 同标准）
  2. **主评估改写**：`assessment = "方法暂不适用"`，`methodology_applicable = false`；公允区间/MOS 可保留但仅对照用
  3. **双轨**：`value_rating` 强制 `UNKNOWN`，不得因假「价值低估」推买入
- **And** 人工 override 为已实现原型（bank / high_dividend / value_growth）时豁免压制
- **Note**：精确警告文案与三层压制由 `add-prototype-fallback-message`（T-15 半诚实）升级为 `add-v2-honesty-degrade`（第 0 刀诚实层）；专用模型（EV/NBV、情景 DCF、Cyclical）仍属后续 V2 任务

### 场景 6：输出反锚定

- **Given** 任一股票的价值面结果
- **When** 展示给用户
- **Then** 以估值区间 + 分位呈现，不直接暴露历史最高/最低价等易锚定数字

---

## 11. 开放问题 / TODO 清单

| 编号 | 项 | 阶段 | 状态 |
|------|----|------|------|
| T-1 | 安全边际阈值按原型差异化（§6.2 VA-OUT-3） | V1.x | 待设计（V1 用统一阈值） |
| T-2 | value_trap High → 独立专项提示 + 降低 confidence | V1.x | ✅ `add-value-trap-high-alert`：独立 `value_trap_alert` + confidence 一级降级；摘要仍保留 warnings |
| T-3 | 银行专用指标（净息差/不良率等）数据完整度 E2E 验证 | V1.x | 🔧 路由+聚合 ✅；Tushare 专项字段常 missing |
| T-4 | 保险内含价值（EV/NBV）模型 | V2 | 未开始 |
| T-5 | 军工·订单驱动估值模型 | V2 | 未开始 |
| T-6 | 历史 PE/PB fetcher（Tushare `daily_basic`，§13.1 D-E） | P1 | ✅ `add-historical-multiples-5yr`（5 年季末采样 20 点） |
| T-7 | 行业→原型映射路由（PrototypeRouter V2；Tushare 简化行业） | P1 | ✅ `add-industry-prototype-router`；复用 `stock_basic.industry`，非 SW/CS 官方多级代码 |
| T-8 | 人工覆盖原型持久化（VA-CLS-2，落 dao） | P1 | 未开始 |
| T-9 | ValueAnalyzer Facade | P0 | ✅ `src/service/value/analyzer.py` |
| T-10 | 区间聚合 Aggregator | P0 | ✅ `src/service/value/aggregator.py` |
| T-11 | ValueScore 综合评分（估值40+质量30+护城河20+风险10） | P1 | 字段预留，算法未实现 |
| T-12 | Cyclical 4 种方法 + `CyclicalStock` 数据模型 | V2 | 未开始 |
| T-13 | controller API + CLI 入口（§14.2-E/F） | P2 | 未开始 |
| T-14 | 与技术面双轨集成 + LLM ContextPack 扩展 | P2 | 未开始 |
| T-15 | V2 原型显式降级提示（§10 场景 5） | V1.x→诚实层 | ✅ `add-prototype-fallback-message` 精确警告；✅ `add-v2-honesty-degrade` 补完三层压制（主评估 + 双轨 UNKNOWN；code：002594/002027） |

---

## 12. 与现有资产映射

| MRD 需求 | stock_copilot 现状 | 缺口 |
|----------|---------------------|------|
| 方法论计算库（23 method_key） | ✅ `src/service/value/valuation/`（Phase 0–8） | Cyclical 4 种（V2 待 port） |
| 数据模型 | ✅ `src/common/models/stock_data.py` | 历史 PE/PB 填充（Tushare D-E）；CyclicalStock（V2） |
| 数据获取 | ✅ `src/data_provider/`（AKShare/Baostock/Tushare） | 部分字段覆盖率待 E2E 确认（prior_*、银行专项指标） |
| 价值面编排 Facade | ✅ `src/service/value/analyzer.py` | value_trap High 专项 ✅（T-2）；V2 原型降级（T-15） |
| 区间聚合 | ✅ `src/service/value/aggregator.py` | MOS 按原型差异化（T-1） |
| 原型路由 | ✅ `src/service/value/router.py`（硬编码 + 行业映射 + 财务启发） | 人工覆盖持久化（T-8） |
| 分析结果模型 | ✅ `src/service/value/models/analysis_result.py` | — |
| 综合评分 | ❌ 字段预留（`value_score=None`） | `ValueScore` 算法（T-11） |
| API / CLI | ❌ `controller/`、`apps/` 为空壳 | REST 端点、CLI 入口（T-13） |
| 双轨 LLM 集成 | ❌ 未建 | ContextPack 价值面 block（T-14） |
| 价值陷阱 / SBC | ✅ `value_trap.py`、`sbc.py`；value_trap 摘要进 warnings，High 有独立警示 + confidence 降级 | — |
| 保险 / 军工模型 | ❌ | V2 新增（T-4/T-5） |

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

`pe_relative` / `pb_relative` 两种相对估值方法依赖历史倍数序列（`historical_pe: List[float]`、`historical_pb: List[float]`）。

**方法论层（已完成）：**

- `StockData` 已扩展 `historical_pe` / `historical_pb` 字段（可空列表）
- 字段为空时，`pe_relative` / `pb_relative` 返回 `applicability="Not Applicable"`（不阻断其他方法）
- 单元测试以 fixture 注入历史序列，验证与 ref ±0.1%

**数据层（待 implement，数据源见 D-E）：**

- data_provider 负责填充上述字段；实现独立于方法论库（change：`add-historical-multiples-provider`）

#### D-E：历史 PE/PB 数据源 — Tushare Pro（已确定，2026-06-21）

| 项 | 决策 |
|----|------|
| **数据源** | **Tushare Pro** 作为历史 PE/PB 序列的主源（AKShare/Baostock 不作为该字段的主实现路径） |
| **实现路径** | 在现有 `src/data_provider/tushare/` 扩展：拉取历史行情/估值指标（如 `daily_basic` 的 `pe_ttm`、`pb` 等，或等价接口），按报告期/交易日对齐后写入 `StockData.historical_pe` / `historical_pb` |
| **付费与积分** | Tushare 部分历史/高频接口需更高积分或付费权限；**由产品运营方自行开通/充值**，不纳入代码仓库 |
| **配置** | 沿用 §9 `TUSHARE_TOKEN` / `config/app.yaml`；无 Token 或权限不足时：`historical_pe`/`historical_pb` 保持 `None`，相对估值方法降级为 Not Applicable，**不阻断**其余 21 种方法 |
| **验收** | 网络 E2E：样本股（工行/长江电力/茅台）`historical_*` 非空且长度 ≥ 3；离线 CI 无 Token 时 skip |

> **分工**：数据权限与费用 — 运营方；fetcher 实现与字段映射 — 开发（`add-historical-multiples-provider` change）。

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

> **状态（2026-06-21）**：Phase 0–8 方法论库已全部交付（23 method_key）；编排层 P0（ValueAnalyzer / Aggregator / Router）已在 `add-value-analyzer-core` 交付。上层集成（§14.2 E/F/G）待建。

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

实现 Phase 0–8 后，可用以下 method_key 组合手动验证三原型覆盖（完整路由见 §5）：

| 原型 | 应跑通的 method_key |
|------|---------------------|
| 银行（工行 601398） | `pb`, `residual_income`, `ddm`, `graham_number`, `altman_z`, `pb_relative`, `value_trap` |
| 高股息（长江电力 600900） | `ddm`, `two_stage_ddm`, `epv`, `owner_earnings`, `graham_number`, `value_trap` |
| 价值成长（茅台 600519） | `dcf`, `epv`, `owner_earnings`, `graham_formula`, `ev_ebitda`, `piotroski_f`, `beneish_m`, `value_trap` |

---

## 14. 实现现状与待完善 Feature

> 本节整合 2026-06-21 探索结论，对照 [product-overview.md](../product-overview.md) §5.1.1 与当前代码库，
> 明确**已交付**与**待建**边界。方法论库（§13 Phase 0–8）+ 编排层 P0 均已完成；价值面**可对外交付**尚缺 API/CLI 入口与 LLM 集成。

### 14.1 已交付能力总览

| 层级 | 模块 | 路径 | 状态 |
|------|------|------|------|
| 数据模型 | `StockData` | `src/common/models/stock_data.py` | ✅ 含 historical_pe/pb、sbc 等预留字段 |
| 数据获取 | 多源 Provider | `src/data_provider/` | ✅ AKShare / Baostock / Tushare |
| 持久化 | DAO + SQLite | `src/dao/` | ✅ |
| 方法论库 | 23 种估值方法 | `src/service/value/valuation/` | ✅ `default_engine()` 全量注册 |
| 编排 Facade | `ValueAnalyzer` | `src/service/value/analyzer.py` | ✅ `analyze(code) → ValueAnalysisResult` |
| 区间聚合 | `ValuationAggregator` | `src/service/value/aggregator.py` | ✅ 中位数 + IQR 过滤 |
| 原型路由 | `PrototypeRouter` | `src/service/value/router.py` | ✅ 硬编码覆盖 + 财务特征启发 |
| V2 原型降级提示 | `describe_unimplemented_industry()` + `ValueAnalyzer` | `src/service/value/router.py`、`analyzer.py` | ✅ 复用行业识别字典，保险/军工提示具体暂缺方法论；其他 unknown 原型保留通用提示 |
| 分析结果模型 | `ValueAnalysisResult` | `src/service/value/models/analysis_result.py` | ✅ |
| 单元测试 | 91 用例 | `test/service/value/` | ✅ 离线可跑 |

**23 个 method_key 分组：**

| 分组 | method_key |
|------|------------|
| Graham | `graham_number`, `graham_formula`, `ncav` |
| 银行 | `pb`, `residual_income` |
| 股息 | `ddm`, `two_stage_ddm` |
| 盈利力 | `epv`, `owner_earnings` |
| DCF | `dcf`, `reverse_dcf` |
| 质量/风险 | `altman_z`, `piotroski_f`, `beneish_m`, `value_trap`, `sbc` |
| 成长/相对 | `peg`, `garp`, `rule_of_40`, `ev_ebitda`, `magic_formula`, `pe_relative`, `pb_relative` |

### 14.2 分层缺口地图

```text
用户 ──▶ apps/ ──▶ controller/ ──▶ service/value/
         ❌           ❌              ✅ valuation/（23 方法）
         CLI/Web      API 端点        ✅ analyzer / aggregator / router
         看板         请求路由        ✅ data_provider（via 外部调用）
```

#### A. ValueAnalyzer Facade（P0，✅ 已交付）

**职责**：把数据获取、原型路由、方法运行、区间聚合串成一次分析调用。

```text
输入: stock_code
  │
  ├─1→ data_provider.fetch(code) → StockData
  ├─2→ router.route(StockData) → [method_keys]            ← ✅
  ├─3→ engine.run_selected(method_keys, StockData) → {results}
  ├─4→ aggregator.aggregate(results) → FairValueRange     ← ✅
  └─5→ build ValueAnalysisResult（§6.1 输出字段）          ← ✅
```

**建议落点**：`src/service/value/analyzer.py`  
**输出契约**：见 [value-analysis-integration.md](../design/value-analysis-integration.md) §3.2 `ValueAnalysisResult`

#### B. 区间聚合 Aggregator（P0，✅ 已交付）

**职责**：将多方法 `ValuationResult` 转为 §6.1 规定的 `fair_value_range` + `margin_of_safety` + `price_percentile`。

```text
多方法输出示例（茅台）:
  DCF:           709
  EPV:           680
  Owner Earnings: 1249   ← 可能为异常值，需过滤
  Graham Formula: 580

  过滤 Not Applicable / Limited / score 类方法
  → 可靠公允价集合 → 中位/分布 → [low, base, high]
  → MOS = (base - current_price) / base
  → 分位 = 当前价在区间中的位置
```

**需求对齐**：§6.2 VA-OUT-1 ~ VA-OUT-4  
**建议落点**：`src/service/value/aggregator.py`

**已定稿（add-value-analyzer-core）：**

- 聚合算法：中位数 + IQR 异常值过滤（V1 不加权）
- 评分类方法（`output_type = "score"`）明确排除，摘要进入 `warnings`
- 离散度大（cv ≥ 0.3）或方法数不足时降低 `confidence`

#### C. 原型路由 Router（P0，✅ 已交付）

**职责**：实现 §3/§5 的"先分类、再选方法"；银行排除 DCF，高股息优先 DDM 等。

**建议落点**：`src/service/value/router.py`  
**参考**：`ref/valueinvest` 的 `get_recommended_methods()`（银行/分红/成长/价值粗路由）  
**V1 已实现**：硬编码覆盖表（工行/长电/茅台等）+ 行业→原型映射 + 财务特征启发（杠杆率/股息/成长率）；`src/service/value/router.py`。行业映射复用 Tushare `stock_basic.industry` 的简化分类名称，不是 SW/CS 官方多级代码：已支持银行及电力/水务/燃气/高速公路/港口，保险与军工显式降级为 `unknown`，避免高杠杆误用银行方法。

**人工覆盖持久化（VA-CLS-2，T-8）**：✅ `PrototypeOverrideRepo` 持久化当前有效覆盖；`value override` CLI 写入或更新记录。分析时人工覆盖优先于固定样本、行业映射与财务特征启发式，并在 warnings 中输出覆盖原因。

**Open Question**：若需要银行细分或更精确的行业归属，SW/CS 官方多级行业代码接入（如 Tushare `index_classify` / `index_member`）应作为未来独立 change 实施；当前变更不新增 fetcher、字段或持久化结构。

#### D. 历史 PE/PB data_provider（P1）— 数据源已确定

**决策（2026-06-21，D-E）**：历史 PE/PB 序列由 **Tushare Pro** 提供；付费/积分由运营方承担，开发实现 fetcher + 降级逻辑。

**现状**：`StockData.historical_pe` / `historical_pb` 字段已预留，Tushare fetcher 尚未写入该序列 → `pe_relative` / `pb_relative` 多数返回 Not Applicable。

**实现要点**：

- 扩展 `src/data_provider/tushare/`（或专用 multiples 子模块）
- 拉取历史估值指标并对齐为 `List[float]`（降序，与 relative 方法约定一致）
- 无 Token / 权限不足：`historical_* = None`，E2E skip，离线 CI 不受影响

**建议 change**：`add-historical-multiples-provider`

#### E. controller API 层（P2，依赖 P0）

| 端点 | 说明 |
|------|------|
| `POST /api/v1/analysis/value` | 触发单票价值面分析 |
| `GET /api/v1/stocks/{code}/valuation` | 查询估值结果 |

**建议落点**：`src/controller/value_controller.py`

#### F. CLI / 看板入口（P2）

| 入口 | 说明 |
|------|------|
| CLI | `python -m apps.cli analyze 600519`（或等价命令） |
| 看板 | 单票一页：价值区间 + MOS + 分位 + method_breakdown（MRD §6 + product-overview §5.3） |

#### G. 与技术面双轨集成 + LLM（P2）

**职责**：价值面结果注入 LLM ContextPack，与技术面并行输出综合建议。

```text
技术面: signal_score=72, 多头排列
价值面: value_score=65, MOS=16.7%, fair_value_range=[620,680,750]
         ↓
LLM 综合报告（数值来自确定性模块，LLM 仅叙述）
```

**参考**：[value-analysis-integration.md](../design/value-analysis-integration.md) §4.2 `ValueAnalysisBlock`  
**双轨决策矩阵**：integration 文档 §5 Phase 2 表格（技术×价值 → 综合建议）

#### H. Cyclical 4 种方法（V2，非 V1 阻塞）

来自 `ref/valueinvest` 的 `cyclical/` 模块，依赖独立 `CyclicalStock` 数据模型（周期位置、均值化财务数据）：

| method_key | 类 | 说明 |
|------------|-----|------|
| `cyclical_pb` | `CyclicalPBValuation` | 周期调整 P/B |
| `cyclical_pe` | `CyclicalPEValuation` | 周期调整 P/E（均值化盈利） |
| `cyclical_fcf` | `CyclicalFCFValuation` | 周期调整 FCF |
| `cyclical_dividend` | `CyclicalDividendValuation` | 周期调整股息 |

**适用原型**：§2.2 周期+资产（北大荒）、现金流+广告周期（分众传媒）等 V2 样本。

#### I. 决策护航 / 情绪 / 复盘（V2+，归属 product-overview，非价值面子模块）

| 能力 | 归属 | 与价值面关系 |
|------|------|-------------|
| 红蓝对抗、Checklist、假设首开仓 | product-overview §5.2 | 消费价值面输出作为 Checklist 输入 |
| 情绪量化 | product-overview §5.1.3 P1 | 三维联合解读 |
| 复盘归因 | product-overview §6 Phase 4 | 独立模块 |

### 14.3 优先级路线图

```text
P0（价值面内部可独立交付）✅ 已完成
├── A. ValueAnalyzer Facade        ✅
├── B. 区间聚合 Aggregator          ✅
└── C. 原型路由 Router              ✅（硬编码 + 财务启发；行业映射 T-7 后置）

P1（数据完整性 + 评分增强）
├── D. 历史 PE/PB provider（T-6）
├── 行业代码映射 Router V2（T-7）
├── 人工覆盖持久化（T-8）
└── 综合 ValueScore（T-11）

P2（上层集成，依赖 P0）
├── E. controller API
├── F. CLI / 看板
└── G. 技术面双轨 + LLM ContextPack

V2（后置）
├── H. Cyclical 4 种 + CyclicalStock
├── 保险 EV/NBV、军工订单模型
└── I. 决策护航 / 情绪 / 复盘（跨模块）
```

### 14.4 建议 OpenSpec Change 顺序

| 顺序 | Change 名称 | 范围 | 状态 |
|------|-------------|------|------|
| 1 | `add-value-analyzer-core` | Facade + Aggregator + Router + ValueAnalysisResult | ✅ 已归档（2026-06-21） |
| 2 | `add-historical-multiples-provider` | Tushare `daily_basic` → historical_pe/pb（T-6） | 待开始 |
| 3 | `add-value-api-cli` | controller REST + CLI 最小入口（T-13） | 待开始（依赖 #1） |
| 4 | `add-dual-track-llm-integration` | ContextPack 价值面 block + 双轨决策矩阵（T-14） | 待开始（依赖 #1 + 技术面） |
| 5 | `add-cyclical-valuation`（V2） | CyclicalStock + 4 方法（T-12） | V2，待开始 |

### 14.5 设计决策记录

| 问题 | 决策 | 状态 |
|------|------|------|
| 区间聚合算法 | 中位数 + IQR 过滤（V1 不加权）| ✅ 已定稿（design.md add-value-analyzer-core） |
| 原型路由 V1 策略 | 硬编码覆盖表优先 + 财务特征启发兜底 | ✅ 已实现（`router.py`）；行业代码映射 P1 后置 |
| ValueAnalyzer 边界 | 直接持有 `StockDataProvider`，由 `from_config()` 封装生产构造路径 | ✅ 已定稿 |
| ValueScore 权重 | V1 预留字段（`value_score=None`），算法后置 | 待 T-11 决策 |
| 安全边际阈值 | V1 统一阈值（>20%低估 / >5%合理偏低 / >-5%合理 / >-20%合理偏高 / ≤-20%高估） | ✅ 已实现；原型差异化 T-1 后置 |

---

## 15. 下一步

1. ~~方法论库 Phase 0–8~~ ✅ 已完成（23 method_key）
2. ~~编排层 P0~~ ✅ 已完成（`add-value-analyzer-core` 归档）
3. **当前优先**：`add-historical-multiples-provider` — 解锁 pe_relative / pb_relative（T-6）
4. **V1 三原型端到端验收**：工行 / 长电 / 茅台，对照 §10 场景 1–3 + §13.3 冒烟清单（需真实 data_provider，非 mock）
5. **上层集成**：`add-value-api-cli`（T-13）→ `add-dual-track-llm-integration`（T-14）
6. **P1 编排细化**：行业代码映射（T-7）、人工覆盖（T-8）
7. **文档同步**：将 §14 摘要合并回 [product-overview.md](../product-overview.md) §5.1.1
