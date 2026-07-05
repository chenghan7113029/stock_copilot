## Context

当前价值评估管线存在三个估值假设层 Bug，导致以茅台为代表的消费成长股估值严重失真（聚合中位 521 元 vs LLM 参考 1340-1474 元）：

1. **EPS 季报污染**：`fina_indicator.eps` 为当期（含季报）EPS，pe_relative 直接使用导致结果为 TTM 的 1/3。
2. **WACC 全局固定 10%**：`AssumptionProvider.get_discount_rate()` 忽略股票风险特征，对低 β 消费龙头过度折现。
3. **growth_rate 无下限**：`get_growth_rate_1_5()` 直接返回 `stock.growth_rate`（2yr CAGR），在行业下行年可能只有 3%，严重低估长期增速。

相关模块：`src/common/models/stock_data.py`、`src/service/value/router.py`、`src/service/value/valuation/assumptions.py`、`src/service/value/valuation/adapter.py`、`src/data_provider/provider.py`。

## Goals / Non-Goals

**Goals:**
- 修复 EPS 污染：provider merge 层推导 TTM EPS
- 引入 β-CAPM 折现率：按原型从 app.yaml 读取 β，替代全局 10%
- growth_rate 设置下限：防止周期低谷拉低 DCF 增速假设
- `StockData.proto` 字段传递原型信息，供假设层查表
- EBITDA 推导补全：adapter 层由 `ebit + depreciation` 兜底

**Non-Goals:**
- 不接入实时 β 数据（保留方案 A 给未来 change）
- 不修改 FCF 计算逻辑（FY2025 263亿数据待独立核验）
- 不改动估值聚合权重策略
- 不改动报告格式

## Decisions

### 决策 1：proto 写入 StockData（方式 I）

**选择**：`PrototypeRouter.route()` 将 proto 写入 `stock.proto` 字段。

**理由**：
- 最干净的依赖路径：`AssumptionProvider` 通过 `StockData` 接收 proto，无需感知 `PrototypeRouter`
- `StockDataAdapter` 无需改动，`stock.proto` 通过 `__getattr__` 透传
- 与现有 `set_field` 风格一致

**备选方案 II（在 analyzer 层构造专属 assumptions）**：需要在每次 run_selected 前重建 engine，侵入 `ValueAnalyzer._analyze_stock()`，且 engine 与 assumptions 解耦被破坏，放弃。

**备选方案 III（app.yaml 直接配置 discount_rate_by_proto）**：跳过 CAPM 语义，失去 β 教育价值与未来方案 A 兼容性，放弃。

### 决策 2：TTM EPS 推导位置在 provider merge 层

**选择**：在 `StockDataProvider._merge_result()` 完成所有源合并后，若 `net_income` 和 `shares_outstanding` 均可用，则用 `net_income / shares_outstanding` 覆写 `eps`，来源标注为 `"derived:ttm"`。

**理由**：
- 推导逻辑属于数据质量层，而非估值逻辑层
- 与现有 `_derive_fcf_from_cashflow` 等推导模式一致
- 修复对所有下游方法（pe_relative、ddm、payout_ratio）透明

**备选（在 adapter 层推导）**：需在多个方法内分别处理，且无法修正 `stock.eps` 字段本身，放弃。

### 决策 3：growth_rate_floor 按原型配置

**选择**：`AssumptionProvider` 新增 `growth_rate_floor_by_proto: dict[str, float]`，`get_growth_rate_1_5(stock)` 取 `max(stock.growth_rate or 0, floor_for_proto)`。

**理由**：
- 行业下行年 2yr CAGR 不代表长期增速，消费龙头需兜底
- 按原型配置比全局 floor 更精准
- 兜底值不影响增速确实更高的股票

**默认配置**：
```yaml
value_analysis:
  beta_by_proto:
    value_growth: 0.6
    high_dividend: 0.5
    bank: 0.9
  growth_rate_floor_by_proto:
    value_growth: 8.0
    high_dividend: 3.0
    bank: 5.0
```

### 决策 4：EBITDA 推导在 adapter 层

**选择**：`StockDataAdapter.ebitda` 属性：若 `stock.ebitda` 存在则直接返回；否则尝试 `ebit + depreciation`；均无则返回 None。

**理由**：推导属于 adapter 职责（补齐 duck-type 属性），不污染 `StockData` 本身。

## Risks / Trade-offs

- **[风险] proto 写入 StockData 引入副作用**：`route()` 现在修改 stock 对象（非纯函数）。→ 缓解：`proto` 是元数据字段（与 `field_sources`、`missing_fields` 同类），文档明确此字段由 router 写入。

- **[风险] growth_rate_floor 掩盖真实衰退**：对真正处于长期衰退轨道的股票，floor 会高估 DCF。→ 缓解：floor 只适用于 1-5 年段（g1），6-10 年段和终端增长率不设 floor；未来可扩展为「衰退原型」。

- **[权衡] TTM EPS 覆写可能误导季报密集型分析**：若用户希望看当季单季 EPS，覆写后无法获取。→ 缓解：保留原始 `fina_indicator.eps` 在 `field_sources` 记录，未来可新增 `eps_quarterly` 字段。

- **[风险] β 按原型配置是静态假设**：不同股票同原型但 β 不同。→ 缓解：这是方案 B 的明确权衡；方案 A（接入历史日收益率计算 β）作为未来增强。

## Migration Plan

1. 所有修改向后兼容——`StockData.proto` 默认 `""`，旧快照不受影响
2. `app.yaml` 新增配置项均有默认值，现有配置文件无需变更即可工作
3. 无数据库 schema 变更
4. TTM EPS 推导在内存中进行，不影响已存储的快照数据
