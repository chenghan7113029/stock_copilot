## 1. Tushare fetcher：prior 年度数据拉取

- [x] 1.1 修改 `src/data_provider/tushare/fetcher.py`：新增 `_fetch_prior_year_financials(ts_code, current_annual_period)` 方法
  - 入参：当期年报 report_period（`20251231`），计算 prior_period = (year - 1) 同月日
  - 调用 `pro.fina_indicator(ts_code, period=prior_period, fields='roa')`
  - 调用 `pro.balancesheet(ts_code, period=prior_period, fields='total_assets,total_liab,total_cur_assets,total_cur_liab,total_share')`
  - 调用 `pro.income(ts_code, period=prior_period, fields='revenue,operate_cost,total_share')`
  - 推导 6 个 prior_* 字段（见 spec），写入 data；API 返回空则加入 missing_fields
- [x] 1.2 在 `fetch_all()` 中，确认年报 `report_period` 后调用 `_fetch_prior_year_financials()`（仅年报触发）

## 2. StockData 字段确认

- [x] 2.1 确认 `src/common/models/stock_data.py` 中已定义 `prior_roa`、`prior_debt_ratio`、`prior_current_ratio`、`prior_shares_outstanding`、`prior_gross_margin`、`prior_asset_turnover`（已有则跳过）

## 3. 测试

- [x] 3.1 新建 `test/data_provider/tushare/test_prior_period.py`（或加入现有文件）：
  - mock `fina_indicator`/`balancesheet`/`income` 返回 prior 年度数据，验证 6 个 prior_* 字段正确计算
  - mock prior API 返回空，验证 missing_fields 含 prior_roa 等，无异常
  - mock 当期为季报（非 1231），验证 prior 年度查询不触发
- [x] 3.2 运行 `py -m pytest test/ -q` 确认无回归

## 4. 集成验证

- [x] 4.1 重新 sync 600519，运行 `py -m apps.cli report value 600519`，确认：
  - `piotroski_f_score` 分项中 `delta_roa > 0` 等同比指标有值（不再为 None）
  - `beneish_m_score` 的 `gmi`（Gross Margin Index）和 `sgai` 有值

## 5. 文档

- [x] 5.1 更新 `docs/mrd/features/value-analysis.md`：变更记录新增 `add-prior-period-financials`；已知缺口移除 prior_* 相关说明
