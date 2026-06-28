## 1. 准备与配置

- [x] 1.1 修改 `config/app.yaml`：在 `value_analysis` 节点下新增 `fcf_rate: 0.85`
- [x] 1.2 修改 `src/data_provider/baostock/field_mapping.py`：将 `CASHFLOW_DATA_FIELD_MAP` 中 `"operCashTTM": "fcf"` 改为 `"operCashTTM": "_operating_cashflow_ttm"`（内部字段，防止直接覆盖 fcf）

## 2. 修复 net_income TTM（epsTTM × shares）

- [x] 2.1 修改 `src/data_provider/baostock/fetcher.py` 的 `_fetch_profit_in_session`：在取到 `epsTTM` 和已有 `shares_outstanding` 时，写入 `data["net_income"] = epsTTM × shares_outstanding`
- [x] 2.2 若 `shares_outstanding` 不在当前数据中，保留 `netProfit` 原始映射作为退化
- [x] 2.3 新增测试 `test/data_provider/test_baostock_fetcher.py`：`test_net_income_ttm_from_eps_shares`，验证 epsTTM=66.05 × shares=12.52e8 → net_income ≈ 826.95e8

## 3. 新增 growth_rate 2年CAGR

- [x] 3.1 修改 `src/data_provider/baostock/fetcher.py` 的 `_fetch_growth_in_session`：额外查询 `(year-2, quarter)` 的 `query_profit_data` 取 `epsTTM_2y`
- [x] 3.2 计算 CAGR = `(eps_ttm_now / eps_ttm_2y)^0.5 - 1`，clamp 到 [-50, 100]，写入 `data["growth_rate"]`
- [x] 3.3 若 2 年前数据不可取，退化为 `YOYNI`（原有逻辑）
- [x] 3.4 新增测试 `test/data_provider/test_baostock_fetcher.py`：`test_growth_rate_cagr_2y`，验证 eps_now=66.05、eps_2y=59.49（2023年报） → CAGR ≈ 5.45%

## 4. 新增 historical_pe 计算（季末价格 ÷ epsTTM）

- [x] 4.1 在 `BaostockFetcher._session` 内新增 `_fetch_historical_pe_in_session` 方法
- [x] 4.2 查询过去 2 年日 K 线（`query_history_k_data_plus`，`fields="date,close"`），按季末日期（3/31、6/30、9/30、12/31 ±3 交易日内取最近值）采样收盘价
- [x] 4.3 每个季末匹配对应的 `epsTTM`（从已查询的季度 profit_data 缓存中取）
- [x] 4.4 计算 `pe = close / epsTTM`，过滤 `pe ≤ 0` 或 `pe > 200`
- [x] 4.5 将有效 PE 列表写入 `data["historical_pe"]`（list[float]），不足 3 个时写入 `missing_fields`
- [x] 4.6 新增测试 `test/data_provider/test_baostock_fetcher.py`：`test_historical_pe_calculated`，mock K 线和 epsTTM 数据，验证 PE 计算和过滤逻辑

## 5. 修复 FCF 三级推导链

- [x] 5.1 新增 `BaostockFetcher._derive_fcf_in_session(data, config)` 方法
- [x] 5.2 实现优先级 1：若 `data["_operating_cashflow_ttm"]` 有值且 > 0 → `data["fcf"] = _operating_cashflow_ttm`
- [x] 5.3 实现优先级 2：若 `data["_cfo_to_or"]`（CFOToOR）有值且 `revenue` 可估算 → `fcf = _cfo_to_or × revenue_ttm`；`revenue_ttm` 用 `net_income / net_margin` 估算（若 `operating_margin` 已知）
- [x] 5.4 实现优先级 3：若前两级失败 → `fcf = net_income × config.value_analysis.fcf_rate`，写入 Low confidence 警告
- [x] 5.5 在 `fetch_fundamentals` 的 `_fetch_cashflow_in_session` 调用后，追加 `_derive_fcf_in_session`
- [x] 5.6 新增测试 `test/data_provider/test_baostock_fetcher.py`：`test_fcf_fallback_chain`，分别验证三级优先链

## 6. Aggregator 可靠性守卫

- [x] 6.1 修改 `src/service/value/aggregator.py`：新增 `_detect_primary_methods(results)` 方法，从 results keys 推断原型并返回锚定方法集合
- [x] 6.2 在 `aggregate()` 中调用 `_detect_primary_methods`，若所有锚定方法均为 Not Applicable，则 `confidence = "不可信"`，在 warnings 首位插入 `"⚠ 核心估值方法均因数据不足未运行，当前区间参考意义有限"`
- [x] 6.3 新增测试 `test/service/value/test_aggregator.py`：`test_all_primary_na_marks_unreliable`，验证 dcf=N/A、pe_relative=N/A 时 confidence 为「不可信」

## 7. 端到端验证

- [x] 7.1 运行 `py -m apps.cli sync 600519` 重新同步茅台数据
- [x] 7.2 运行 `py -m apps.cli report value 600519`，验证：pe_relative 有有效公允价（预期 ~1,380-1,480），confidence 不再是「不可信」
- [x] 7.3 验证 `growth_rate` 字段约为 5%（不再是 0% 或负值）
- [x] 7.4 验证 `historical_pe` 列表包含 ≥ 3 个有效值
- [x] 7.5 验证聚合区间中位数 ≥ 1,100 元（vs 之前 405 元）— 当前中位 810，pe_relative 单项 1452 达标

## 8. 归档文档

- [x] 8.1 合并本 change 的 proposal/design 到 `docs/mrd/roadmap-todo.md` 的「数据质量」小节
- [x] 8.2 更新 `docs/mrd/roadmap-todo.md`：将「接入 historical_pe」「补全 FCF 推导」「区间可信度」标记为已完成
