## 1. Fetcher 接口与 Baostock 修复

- [x] 1.1 修改 `src/data_provider/base.py`：将 `fetch_all(self, code, exchange)` 设为统一签名；内部 normalize 与合并 quote/fundamentals
- [x] 1.2 修改 `src/data_provider/manager.py`：移除 `fetch_all` 特殊分支，统一 `(code, exchange)` 调用
- [x] 1.3 确认 `src/data_provider/provider.py` 与 manager 调用一致；补充/更新 `test/data_provider/test_manager.py` 回归
- [x] 1.4 修改 `src/data_provider/baostock/fetcher.py`：实现有效 `(year, quarter)` 计算与最多 4 季回溯；合并单次 `_session` 减少 login 次数（可选优化）
- [x] 1.5 更新 `test/data_provider/test_baostock_fetcher.py`：mock 验证季频参数与 eps/roe 解析

## 2. Provider 持久化会话边界

- [x] 2.1 重构 `src/data_provider/provider.py`：先收集全部 `FetchResult`，再短 Session 批量 upsert（fetch 阶段不持有 Session）
- [x] 2.2 可选：在 `StockSnapshotRepo` 增加 `upsert_many(results)` 便于批量写
- [x] 2.3 编写 `test/data_provider/test_provider_persistence.py`：mock fetcher + 内存 SQLite，验证无 locked 且多源落库

## 3. 配置 bootstrap 与采集脚本

- [x] 3.0 新增 `config/value_data_validation_stocks.yaml`（V1 样本清单真源：4 银行 + 长江电力 + 茅台）；E2E/脚本从该文件读取
- [x] 3.1 新增 `src/common/config_loader.py`（或等价）：加载 YAML；缺 `app.yaml` 时从 example 复制并创建 `data/`；提供 `load_validation_stocks()` 读取清单
- [x] 3.2 新增 `scripts/fetch_value_data.py`：默认读验证清单；fetch → upsert → 打印读回摘要；支持 `--code` 覆盖
- [x] 3.3 更新 `scripts/setup-dev-env.sh` 或 `scripts/README.md`：说明首次运行与 `config/app.yaml` 复制

## 4. DAO 读回增强

- [x] 4.1 在 `src/dao/stock_snapshot_repo.py` 增加 `list_recent(limit)` 或 `list_by_code(code)` 便捷读回（若已有则补文档/测试）
- [x] 4.2 编写 `test/dao/test_read_back.py`：写入后读回字段一致

## 5. E2E 验收

- [x] 5.1 新增 `src/data_provider/validation/field_coverage.py`：计算 V1 必需字段并集；跨样本聚合 covered/blocked；生成 JSON 报告
- [x] 5.2 新增 `test/e2e/test_value_data_pipeline.py`：标 `@pytest.mark.network`；读 `config/value_data_validation_stocks.yaml` 全清单；fetch→upsert→read；断言并集逐字段 covered 或 blocked 进缺口报告
- [x] 5.3 本地运行 `pytest -m network test/e2e/`，产出 `reports/value-data-field-coverage-*.json` 与 `reports/value-data-field-gaps-*.json`；blocked 字段汇总供产品决策
- [x] 5.4 运行全量离线 pytest + ruff 通过

## 6. 文档与收尾

- [x] 6.1 归档前更新 `docs/mrd/features/value-analysis.md` §9：补充 E2E 验收与 `scripts/fetch_value_data.py` 用法
- [x] 6.2 若新增 config_loader / scripts 约定，同步 `docs/dev/engineering-conventions.md`
