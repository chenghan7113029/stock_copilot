## 1. 依赖与配置

- [x] 1.1 在 `pyproject.toml` / `requirements.txt` 增加 `tushare>=1.4.0`
- [x] 1.2 更新 `config/app.example.yaml`：补充 tushare 启用示例、Token 填写说明、优先级建议
- [x] 1.3 更新 `src/common/config_loader.py`（若需）：支持从 `TUSHARE_TOKEN` 环境变量合并 token；文档注释说明 Token 勿提交

## 2. Tushare Fetcher 实现

- [x] 2.1 新增 `src/data_provider/tushare/field_mapping.py`：Tushare 列名 → StockData 字段映射
- [x] 2.2 新增 `src/data_provider/tushare/fetcher.py`：`TushareFetcher` 实现 `fetch_quote` / `fetch_fundamentals` / `fetch_all`
- [x] 2.3 修改 `src/data_provider/manager.py`：`_build_fetcher("tushare")` 传入 token；无 token 时返回 None 并 warning
- [x] 2.4 编写 `test/data_provider/test_tushare_fetcher.py`：mock pro_api，验证映射、None 语义、错误路径

## 3. 落库与读回验收

- [x] 3.1 新增 `test/e2e/test_tushare_pipeline.py`：`@pytest.mark.network`；读 `value_data_validation_stocks.yaml`；无 Token skip
- [x] 3.2 测试断言：6 只样本均有 `source=tushare` 快照；至少 `current_price` 或 `eps` 非空
- [x] 3.3 本地配置 Token 后运行 `pytest -m network test/e2e/test_tushare_pipeline.py -v` 通过（Token 无接口权限时 skip，需 tushare.pro 积分）
- [x] 3.4 可选：运行 `python scripts/fetch_value_data.py` 确认 DB 中 tushare 快照可读

## 4. 回归与文档

- [x] 4.1 运行 `pytest -m "not network"` 与 `ruff check src/ test/` 通过
- [x] 4.2 更新 `docs/mrd/features/value-analysis.md` §9：补充 Tushare 数据源与 Token 配置说明
- [x] 4.3 更新 `docs/dev/engineering-conventions.md` 技术栈：增加 tushare 依赖

## 5. Token 配置指引（交付给用户）

实施完成后，用户在本地执行：

1. 复制 `config/app.example.yaml` → `config/app.yaml`（若尚未存在）
2. 在 `data_sources.enabled` 取消注释 tushare 并填入 Token
3. 或设置环境变量 `TUSHARE_TOKEN`
4. 运行 `pytest -m network test/e2e/test_tushare_pipeline.py -v`

**切勿**将 Token 提交到 Git 或粘贴到公开渠道。
