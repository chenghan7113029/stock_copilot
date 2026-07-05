## 1. 数据模型：StockData 新增 proto 字段

- [x] 1.1 修改 `src/common/models/stock_data.py`：在元数据区块新增 `proto: str = ""` 字段，注释说明由 PrototypeRouter 写入

## 2. 路由层：PrototypeRouter 写入 proto

- [x] 2.1 修改 `src/service/value/router.py`：`route()` 返回前执行 `stock.proto = prototype`
- [x] 2.2 修改 `test/service/value/test_router.py`（或新建）：验证 route() 后 stock.proto 被正确写入（覆盖工行=bank、茅台=value_growth、unknown 三个场景）

## 3. 假设层：beta_by_proto + growth_rate_floor

- [x] 3.1 修改 `src/service/value/valuation/assumptions.py`：
  - `AssumptionDefaults` 新增 `beta_by_proto: dict[str, float]`（默认 `{"value_growth": 0.6, "high_dividend": 0.5, "bank": 0.9}`）和 `growth_rate_floor_by_proto: dict[str, float]`（默认 `{"value_growth": 8.0, "high_dividend": 3.0, "bank": 5.0}`）
  - `AssumptionProvider.__init__` 从 config 读取这两个字段
  - `get_discount_rate(stock)` 逻辑：若 `stock.proto` 在 `beta_by_proto` 中，返回 `china_10y_yield + beta × equity_risk_premium`；否则返回 `self.discount_rate`
  - `get_growth_rate_1_5(stock)` 逻辑：取 `max(stock.growth_rate or 0, floor_by_proto.get(stock.proto, 0))` 与 config 默认值的 max，若 stock.growth_rate 为 None 则直接用 max(config_default, floor)
- [x] 3.2 修改 `config/app.yaml`：在 `value_analysis` 下新增 `beta_by_proto` 与 `growth_rate_floor_by_proto` 配置块（与 3.1 默认值一致）
- [x] 3.3 新建/修改 `test/service/value/test_assumptions.py`：
  - 测试 value_growth proto 使用 CAPM（5.4%）
  - 测试未知 proto fallback 到 10%
  - 测试 growth_rate=3.14 + floor=8.0 → 返回 8.0
  - 测试 growth_rate=15.0 + floor=8.0 → 返回 15.0
  - 测试 growth_rate=None → 返回 max(config_default, floor)

## 4. 数据提供层：TTM EPS 推导

- [x] 4.1 修改 `src/data_provider/provider.py`：在 `get_stock_data`（在线合并后）和 `get_stock_data_offline`（离线合并后）末尾添加 TTM EPS 推导逻辑：
  ```python
  if stock.net_income and stock.net_income > 0 and stock.shares_outstanding and stock.shares_outstanding > 0:
      stock.eps = stock.net_income / stock.shares_outstanding
      stock.field_sources["eps"] = "derived:ttm"
  ```
- [x] 4.2 修改 `test/data_provider/test_provider.py`：新增测试 `test_ttm_eps_derived_from_net_income`，验证 net_income=823亿、shares=12.5亿时 eps=65.84，来源=derived:ttm；验证 net_income=None 时 eps 保持原值

## 5. Adapter 层：EBITDA 推导

- [x] 5.1 修改 `src/service/value/valuation/adapter.py`：新增 `ebitda` 属性，逻辑：若 `stock.ebitda` 不为 None 则返回；否则若 `stock.ebit` 和 `stock.depreciation` 均不为 None 则返回 `stock.ebit + stock.depreciation`；否则返回 None

## 6. 集成验证：茅台估值回归

- [x] 6.1 运行 `py -m apps.cli report value 600519`（离线），验证：
  - pe_relative 公允价 ≥ 1200 元
  - DCF 公允价 ≥ 700 元
  - 聚合中位 ≥ 1000 元
  - ValuationResult.details["discount_rate"] ≈ 5.4（value_growth CAPM）
- [x] 6.2 验证 stock.eps 输出为 TTM 值（~65 元）而非季报单季值（~21 元）

## 7. 文档归档

- [x] 7.1 更新 `docs/mrd/features/value-analysis.md`：变更记录新增 `fix-valuation-assumptions` 条目，描述 EPS TTM、β-CAPM、growth floor 三项修复
- [x] 7.2 更新 `docs/mrd/roadmap-todo.md`：将 task 7.5（聚合中位对齐 Gemini 参考区间）标记为 ✅ 已解决
