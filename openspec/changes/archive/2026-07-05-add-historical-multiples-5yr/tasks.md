## 1. Tushare fetcher：新增历史 PE/PB 采样

- [x] 1.1 修改 `src/data_provider/tushare/fetcher.py`：新增 `_fetch_historical_multiples(ts_code)` 方法
  - 调用 `pro.daily_basic(ts_code, start_date=5年前, end_date=today, fields='trade_date,pe_ttm,pb')`
  - 按季末（3/6/9/12 月末最后交易日）采样，最多取 20 点
  - 过滤 PE ≤ 0 或 > 200；PB ≤ 0 或 > 50
  - 有效点 ≥ 3 时写入 data["historical_pe"] 和 data["historical_pb"]（降序排列）
  - 否则加入 missing_fields
- [x] 1.2 在 `fetch_all()` 流程中调用 `_fetch_historical_multiples()`（在 daily_basic 之后）

## 2. Baostock fallback 验证

- [x] 2.1 确认 `_merge_fields()` 中 `historical_pe` 使用 `set_field`（不被覆盖），保证 Tushare 先写后 Baostock 不覆盖
- [x] 2.2 确认 Baostock historical_pe fallback 路径仍正常（Tushare 不可用时）

## 3. 格式层：DCF/EPV 语义注释

- [x] 3.1 修改 `src/apps/formatters.py`：在方法行渲染时对 `dcf` 追加增长假设摘要，对 `epv` 追加"零增长地板价"提示
  - 从 `ValuationResult.details` 读取 `growth_1_5` 和 `discount_rate`（已存在）

## 4. 快照存储支持

- [x] 4.1 确认 `StockSnapshot` ORM 中已有 `historical_pe`/`historical_pb` 序列字段（现有 JSON 列或逗号分隔字符串），`historical_pb` 路径是否完整

## 5. 测试

- [x] 5.1 新建 `test/data_provider/tushare/test_historical_multiples.py`（或添加到现有 tushare 测试）：mock `daily_basic` 返回，验证季末采样逻辑、过滤逻辑、不足 3 点时 missing
- [x] 5.2 新建集成回归：sync 600519 后 `get_stock_data_offline('600519').historical_pb` 不为 None，长度 ≥ 10
- [x] 5.3 运行 `py -m pytest test/ -q` 确认无回归

## 6. 集成验证

- [x] 6.1 运行 `py -m apps.cli report value 600519`，确认：
  - `pb_relative` 从 "Not Applicable" 变为 "Applicable" 并有公允价
  - DCF 方法行含 "(含增长假设)"，EPV 行含 "(零增长地板价)"
  - `pe_relative` 历史 PE 均值基于 ≥ 15 点

## 7. 文档

- [x] 7.1 更新 `docs/mrd/features/value-analysis.md`：变更记录新增 `add-historical-multiples-5yr`；已知缺口中移除 `historical_pb 为空`
- [x] 7.2 更新 `docs/mrd/roadmap-todo.md`：T-6 标为 ✅ 已实现
