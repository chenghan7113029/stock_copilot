## 1. PrototypeRouter 银行分类验证与修正

- [ ] 1.1 阅读 `src/service/value/router.py`，确认 `_classify(stock)` 中银行原型的判断逻辑
- [ ] 1.2 若未匹配行业字段，修改 `_classify`：`if stock.industry and "银行" in stock.industry: return "bank"`
- [ ] 1.3 更新 `test/service/value/test_router.py`：新增 `test_bank_classification_by_industry`，验证 601398 归类为 bank

## 2. Tushare fetcher：银行专项指标映射

- [ ] 2.1 阅读 `src/data_provider/tushare/fetcher.py` 的 `_fetch_fina_indicator()`，确认 `fina_indicator` 返回字段中是否含 `netint_margin`、`prov_cov`、`npl_ratio`
- [ ] 2.2 修改 `_fetch_fina_indicator()` 的 `fields` 参数：加入 `netint_margin,prov_cov,npl_ratio`（如字段名需确认可调试 Tushare 返回）
- [ ] 2.3 在字段映射中添加：`netint_margin → net_interest_margin`，`prov_cov → provision_coverage`，`npl_ratio → npl_ratio`
- [ ] 2.4 确认 fetch 仅银行时才发起银行专项查询（通过 `industry` 字段判断），或兼容所有股票（非银行返回空则 missing）

## 3. StockData 字段确认

- [ ] 3.1 确认 `src/common/models/stock_data.py` 含 `net_interest_margin`、`npl_ratio`、`provision_coverage` 三字段（若缺失则添加）

## 4. 测试

- [ ] 4.1 新建 `test/service/value/test_bank_e2e.py`：
  - 构造含完整银行字段的 `StockData(code="601398", industry="银行", net_interest_margin=2.05, provision_coverage=215.0, pe_ratio=5.5, ...)` 
  - 调用 `ValueAnalyzer.analyze_offline("601398")` 并 mock StockDataProvider
  - 验证 `result.prototype = "bank"`，`result.method_results` 不为空，聚合中位有值
  - 验证 NIM/NPL 为 None 时聚合不崩溃（优雅降级）
- [ ] 4.2 在 `test/data_provider/tushare/` 新增 `test_bank_metrics_fetch.py`：mock `fina_indicator` 含 `netint_margin`，验证映射到 `net_interest_margin`

## 5. 集成验证（有 Tushare 2000 积分环境）

- [ ] 5.1 运行 `py -m apps.cli sync 601398`
- [ ] 5.2 运行 `py -m apps.cli report value 601398`，确认：
  - `prototype = bank`
  - `net_interest_margin` 不为 None（或 missing 并有说明）
  - 聚合中位有值，主要方法无崩溃
  - 银行相关的价值陷阱提示合理

## 6. 文档

- [ ] 6.1 更新 `docs/mrd/features/value-analysis.md`：变更记录新增 `value-bank-e2e`；已知缺口更新银行 E2E 状态
- [ ] 6.2 更新 `docs/mrd/roadmap-todo.md`：银行 E2E 验证标为 ✅（或 🔧 部分实现，说明 NPL ratio 限制）
