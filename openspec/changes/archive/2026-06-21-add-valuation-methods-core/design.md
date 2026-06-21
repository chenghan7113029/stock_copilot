## Context

stock_copilot 已具备完整的数据管道（`src/data_provider/`）和数据落库能力（`src/dao/`），
但缺少估值计算层。`ref/valueinvest/` 提供了经过验证的 20+ 种估值算法参考实现，
本次 Phase 0–3 移植其中 8 种核心方法，建立可独立运行、可测试的方法论计算库。

目前 `src/service/value/` 目录为空占位。所有估值方法使用的唯一输入是 `StockData`（`src/common/models.py`）。

## Goals / Non-Goals

**Goals:**
- 建立 `src/service/value/valuation/` 计算层骨架（BaseValuation、AssumptionProvider、StockDataAdapter、ValuationEngine）
- Port 8 种方法：GrahamNumber、GrahamFormula、NCAV、PBValuation、ResidualIncome、DDM、TwoStageDDM、EPV
- 实现 WACC 计算模块，从 StockData 推导，支持参数覆盖
- 单元测试覆盖全部方法，与 ref/valueinvest 同输入偏差 ≤ ±0.1%
- StockData 扩展两个可空字段（historical_pe、historical_pb），向后兼容

**Non-Goals:**
- 原型路由层（ValuationEngine.get_recommended_methods 按行业选方法，后续独立 change）
- Phase 5–8 方法（DCF、AltmanZ、PEG、MagicFormula 等）
- Controller/API 暴露（本期为纯 service 内部库）
- 历史 PE/PB 数据的 data_provider 侧获取（字段预留，数据层独立 change）

## Decisions

### D1：目录结构

```
src/service/value/
├── __init__.py
└── valuation/
    ├── __init__.py       # 导出 ValuationEngine + 全部方法类
    ├── base.py           # BaseValuation, ValuationResult, ValuationRange, FieldRequirement
    ├── assumptions.py    # AssumptionProvider（配置化参数，含 WACC 推导）
    ├── adapter.py        # StockDataAdapter（StockData → 估值方法 duck-type 接口）
    ├── engine.py         # ValuationEngine（注册表 + run_single/run_all）
    ├── wacc.py           # WACC 计算（port 自 ref/valueinvest/roic/wacc.py）
    ├── graham.py         # GrahamNumber, GrahamFormula, NCAV
    ├── bank.py           # PBValuation, ResidualIncome
    ├── ddm.py            # DDM, TwoStageDDM
    └── epv.py            # EPV
```

**理由**：与 `ref/valueinvest` 保持文件粒度对齐，方便后续追加方法不改结构；
扁平于 `service/value/valuation/`，符合项目"扁平 src" 约定。

### D2：None vs 0 语义（关键差异）

`ref/valueinvest` 的 `DataValidator` 将 `value == 0` 视为缺失（`is_critical` 字段检测 0）。
`StockData` 用 `None` 表示缺失，`0.0` 表示真实零值。

**方案**：`StockDataAdapter` 在转换时：
- `StockData.xxx = None` → 标记为缺失，计入 `missing_fields`
- `StockData.xxx = 0.0` → 透传为 0.0，由方法自行处理（如利息费用确实为零）

FieldRequirement 中 `min_value` 检查保留（BVPS、EPS > 0 等业务约束），不与 None 检查混淆。

### D3：AssumptionProvider 配置化参数

所有方法的假设参数集中在 `AssumptionProvider`，初始化顺序：
1. `StockData` 字段（最优先）
2. 方法实例化时的 `__init__` 参数覆盖
3. `config/app.yaml` 中的 `value_analysis:` 块
4. 硬编码默认值（最后兜底）

A 股默认值：
- 无风险利率：`china_10y_yield = 1.80%`
- 股权风险溢价：`equity_risk_premium = 6.0%`
- AAA 债券收益率：`aaa_corporate_yield = 5.30%`
- 默认折现率：`discount_rate = 10.0%`
- 税率：`tax_rate = 25.0%`
- DDM 股息增长率（默认）：`dividend_growth_rate = 3.0%`

**理由**：比 ref/valueinvest 更系统，避免散落在各方法类的 `DEFAULT_*` 常量。

### D4：ValuationEngine 注册表模式

```python
engine = ValuationEngine()
engine.register("graham_number", GrahamNumber())
engine.register("graham_formula", GrahamFormula())
# ...
result = engine.run_single("graham_number", stock_data)
results = engine.run_all(stock_data)  # 返回 dict[str, ValuationResult]
```

`run_all` 遇到异常不中断，把错误包装进 `ValuationResult(error=...)` 返回。

**理由**：注册表模式便于后续原型路由层按名称调用；`run_all` 容错与 ref/valueinvest 的 `ValuationEngine.run_all` 一致。

### D5：WACC 模块复用策略

`wacc.py` port 自 `ref/valueinvest/valueinvest/roic/wacc.py`，接收 `StockDataAdapter` 输出，
返回 `WACCResult`（dataclass）。DCF 等后续方法复用此模块；Phase 0–3 方法（Graham/DDM/EPV）
直接用 `AssumptionProvider.discount_rate`（即 `cost_of_capital`），不强制走 WACC 路径。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| ref/valueinvest 的 `Stock.cost_of_capital` 默认 10%，但 A 股合理值约 8–12%，不统一 | AssumptionProvider 显式配置化，测试用 fixture 锁定值 |
| EPV 的维护性 CapEx 估算（收入 7% fallback）对轻资产公司偏高 | 方法返回 `warnings` 字段说明，后续可配置化 |
| 历史 PE/PB 字段在 StockData 为 None 时相关方法不可用 | 返回 `applicability="Not Applicable"` 而非错误，不阻断其他方法 |
| Port 精度：浮点累积误差可能超 ±0.1% | fixture 用小数点后 4 位截断；若超界则调查是否公式差异而非精度问题 |

## Migration Plan

1. 新增目录 `src/service/value/valuation/`，与现有 `src/service/value/` 并存，不影响已有代码
2. 扩展 `StockData`：追加两个 `Optional[list[float]]` 字段，默认 `None`，不破坏现有序列化/反序列化
3. 无数据库迁移，无 API 变更，无配置文件格式改动
4. 单元测试独立于网络，全部使用 fixture，可在 CI 中无条件运行
