## Why

以茅台（600519）为验证基准，当前价值评估聚合中位（521元）与大模型参考区间（1340-1474元）存在约 2.5 倍差距，根因是三个估值假设层 Bug——EPS 使用季报单季值而非 TTM 年化值、WACC 使用全局默认 10%（无法反映低风险消费龙头真实折现率）、DCF 增长率直接取 2025 行业下行年的 2年 CAGR（3.14%）而非长期中枢——导致 DCF / EPV / pe_relative 全部严重失真。这些 Bug 属于估值假设层（非数据缺口），必须修复才能让系统估值可信。

## What Changes

- **EPS TTM 推导**：Tushare `fina_indicator.eps` 为当期（含季报）EPS，在 provider merge 层改为用年报净利润 ÷ 总股本推导 TTM EPS，修正 pe_relative 从 477 元 → ~1449 元。
- **proto 字段写入 StockData**：`PrototypeRouter.route()` 执行后将 proto 写入 `StockData.proto`，供下游假设层按原型查表。
- **β 按原型配置（方案 B 方式 I）**：`app.yaml` 新增 `beta_by_proto` 配置，`AssumptionProvider.get_discount_rate()` 读取 proto 对应 β 后用 CAPM 推算折现率，value_growth 原型折现率从 10% 降至 5.4%，DCF 结果从 329 元 → ~900-1100 元。
- **growth_rate 设置下限**：`AssumptionProvider.get_growth_rate_1_5()` 增加 `growth_rate_floor` 配置，防止 2yr CAGR 在行业下行年拉低 DCF 增速假设；value_growth 默认下限 8%。
- **EBITDA 推导补齐**：若 `ebitda` 缺失，在 adapter 层由 `ebit + depreciation` 推导，使 `ev_ebitda` 方法在更多场景可用。

## Capabilities

### New Capabilities

- `stock-proto-field`：StockData 携带 proto 字段，由 PrototypeRouter 在路由时写入，供估值假设层下游访问。
- `valuation-beta-by-proto`：按股票原型（value_growth / high_dividend / bank）配置默认 β，AssumptionProvider 用 CAPM 推算折现率，替代全局 10% 固定值。
- `valuation-growth-rate-floor`：growth_rate_1_5 设置按原型可配的下限（floor），避免周期性低谷年份拉低长期增速假设。

### Modified Capabilities

- `value-prototype-router`：route() 方法新增副作用——将 proto 字符串写入 stock.proto 字段。
- `value-data-provider`：merge 阶段补充 TTM EPS 推导逻辑（年报 net_income ÷ shares_outstanding）。
- `valuation-dcf`：折现率来源从固定 10% 改为 AssumptionProvider.get_discount_rate(stock)（已接入 β-CAPM）。
- `valuation-relative`：pe_relative 使用 TTM EPS 而非 fina_indicator 单季 EPS。

## Impact

- `src/common/models/stock_data.py`：新增 `proto: str = ""` 字段
- `src/service/value/router.py`：`route()` 写入 `stock.proto`
- `src/service/value/valuation/assumptions.py`：新增 `beta_by_proto`、`growth_rate_floor_by_proto` 读取；`get_discount_rate()`、`get_growth_rate_1_5()` 逻辑更新
- `src/service/value/valuation/adapter.py`：`ebitda` 推导属性补充
- `src/data_provider/provider.py`：TTM EPS 推导逻辑（merge 层）
- `config/app.yaml`（及 `config/app.example.yaml`）：新增 `value_analysis.beta_by_proto`、`value_analysis.growth_rate_floor_by_proto`
- `test/service/value/` 相关测试：assumptions、router、adapter 单测更新
- `docs/mrd/features/value-analysis.md`：更新变更记录与已知缺口
