## Context

`src/service/value/valuation/` 已实现 23 种估值方法（Phase 0–8），通过 `default_engine()` 注册。`src/data_provider/provider.py` 的 `StockDataProvider` 已可将 A 股代码解析为 `StockData`。但两者之间缺少编排层——调用方须手动调 provider、手动筛选方法、手动处理结果，无法用一次调用获得结构化的价值面分析输出。

本次 change 在 `src/service/value/` 内新增三个模块（Analyzer / Aggregator / Router）和一个输出数据类，完成编排层建设。

## Goals / Non-Goals

**Goals:**

- 提供 `ValueAnalyzer.analyze(code) -> ValueAnalysisResult` 单一入口，隐藏编排细节
- 实现 `ValuationAggregator`：多方法公允价 → 区间聚合（过滤 / 中位 / MOS / 分位）
- 实现 `PrototypeRouter` V1：银行 / 高股息 / 价值成长三原型路由；未知原型降级
- 定义 `ValueAnalysisResult`：MRD §6.1 全部字段，供后续 API/CLI/LLM 直接消费
- 单元测试覆盖主路径（mock provider，离线）

**Non-Goals:**

- 历史 PE/PB 数据获取（`add-historical-multiples-provider` 独立 change）
- controller API 层、CLI 入口（P2，独立 change）
- LLM ContextPack 集成（P2）
- Cyclical / 保险 / 军工原型（V2）
- 综合 ValueScore 评分（本期输出字段预留，算法后置）

## Decisions

### D-1：模块结构

```
src/service/value/
  models/
    analysis_result.py   ← ValueAnalysisResult dataclass
  router.py              ← PrototypeRouter
  aggregator.py          ← ValuationAggregator
  analyzer.py            ← ValueAnalyzer Facade
  __init__.py            ← 导出上述类
```

依赖方向：`analyzer` → `router` + `aggregator` + `valuation/engine` + `data_provider`，符合工程约定（service 层不依赖 controller/apps）。

### D-2：PrototypeRouter V1 — 行业代码 + 财务特征启发 + 硬编码覆盖

V1 按以下优先级判断原型：

1. **硬编码样本覆盖表**（code → prototype）：工行/交行/建行/招行 → `bank`；长江电力 → `high_dividend`；贵州茅台 → `value_growth`。确保 V1 三原型冒烟必过。
2. **行业代码启发**：AKShare `sw_industry`/`cs_industry` 代码前缀映射（银行→`bank`，电力/公用事业→`high_dividend`）
3. **财务特征启发**：
   - `total_liabilities / total_assets > 0.85` → `bank`（高杠杆）
   - `dividend_yield > 4.0` 且 `growth_rate < 10` → `high_dividend`
   - 其余 → `value_growth`（兜底）
4. **unknown**：数据不足（total_assets / dividend_yield / growth_rate 均 None）→ `unknown`，降级为 5 种通用方法

**方法路由表**（对齐 MRD §5）：

| 原型 | 主方法 | 辅助方法 | 风险校验 | 明确排除 |
|------|--------|---------|---------|---------|
| bank | pb, residual_income | ddm, two_stage_ddm, graham_number | altman_z, pb_relative, value_trap | dcf, reverse_dcf, magic_formula, rule_of_40, ncav, peg, garp |
| high_dividend | ddm, two_stage_ddm | epv, owner_earnings, graham_number | altman_z, value_trap | rule_of_40, peg, garp |
| value_growth | dcf, epv, owner_earnings | graham_formula, ev_ebitda, pe_relative | piotroski_f, beneish_m, value_trap | ncav |
| unknown | graham_number, graham_formula, epv, altman_z, value_trap | — | — | dcf, ddm（高度依赖假设） |

### D-3：ValuationAggregator — 中位数 + IQR 过滤

```
输入: Dict[method_key, ValuationResult]

步骤:
1. 过滤不参与聚合的结果:
   - error 非 None
   - applicability 为 "Not Applicable"
   - details.output_type == "score"（评分类）
2. 提取有效公允价集合 values
3. 若 len(values) == 0 → fair_value_range = None, assessment = "数据不足"
4. IQR 异常值过滤（Q1 - 1.5*IQR, Q3 + 1.5*IQR）剔除极端值
5. 聚合:
   - base = median(values)
   - low = percentile(values, 25)
   - high = percentile(values, 75)
6. MOS = (base - current_price) / base
7. price_percentile = 当前价在 [low, high] 中的分位（线性插值）
8. assessment 基于 MOS:
   - MOS > 20% → 低估
   - MOS > 5%  → 合理偏低
   - MOS > -5% → 合理
   - MOS > -20% → 合理偏高
   - MOS ≤ -20% → 高估
9. confidence:
   - 有效方法数 ≥ 3 且 cv(values) < 0.3 → High
   - 有效方法数 ≥ 2 → Medium
   - 否则 → Low
```

**选中位数而非加权均值**：估值方法之间无绝对优劣权重，中位数对异常值鲁棒、可解释性强，V1 先行。

### D-4：ValueAnalysisResult — 精简契约

基于 MRD §6.1，V1 输出字段：

```python
@dataclass
class ValueAnalysisResult:
    code: str
    name: str
    current_price: float | None
    prototype: str                          # bank / high_dividend / value_growth / unknown
    method_keys_used: list[str]             # 本次运行的 method_keys
    fair_value_range: ValuationRange | None # low / base / high（聚合后）
    margin_of_safety: float | None          # %，正=低估
    price_percentile: float | None          # 0–100
    assessment: str                         # 低估/合理/高估等
    confidence: str                         # High/Medium/Low
    method_results: dict[str, ValuationResult]   # 原始各方法结果，供明细追溯
    warnings: list[str]                     # 评分类输出、数据缺失、原型降级等
    data_timestamp: datetime | None
    fundamental_report_date: date | None
    # 预留（V2 填充）
    value_score: int | None = None          # 综合评分 0–100
```

**不包含** `moat_rating`、`roic_vs_wacc` 等需要额外分析引擎的字段（V2 扩展）。

### D-5：ValueAnalyzer 构造 — 依赖注入

```python
class ValueAnalyzer:
    def __init__(
        self,
        provider: StockDataProvider,
        engine: ValuationEngine | None = None,
        router: PrototypeRouter | None = None,
        aggregator: ValuationAggregator | None = None,
    ): ...

    @classmethod
    def from_config(cls, config: dict) -> "ValueAnalyzer":
        """从 app.yaml config 构造，供生产使用。"""
        ...
```

依赖注入便于单测 mock；`from_config` 封装生产构造路径。

## Risks / Trade-offs

- **[Risk] IQR 过滤在方法数少（≤ 2）时失效** → Mitigation：≤ 2 个有效值时跳过 IQR，直接用均值；`confidence = "Low"`
- **[Risk] 原型路由误判（如招行被归为 value_growth）** → Mitigation：硬编码样本覆盖表兜底；未来接入人工覆盖层（§3.2 VA-CLS-2）
- **[Risk] 某方法运行异常导致整体失败** → Mitigation：`engine.run_all` 已内置异常捕获，返回带 `error` 的 `ValuationResult`；aggregator 过滤后继续
- **[Risk] V1 `unknown` 原型降级对复杂股票估值失准** → Mitigation：在 `warnings` 明确标注"原型未识别，使用通用方法集，置信度低"
