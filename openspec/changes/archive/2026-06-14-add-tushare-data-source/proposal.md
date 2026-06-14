## Why

E2E 验收显示 AKShare 不稳定时，Baostock  alone 无法覆盖 V1 价值面所需的资产负债表、分红、股本等字段。Tushare Pro 是 A 股财报数据的成熟备选源（valueinvest、daily_stock_analysis 均已采用），用户已申请 Token，需将其接入多源管道并验证「取数 → 落库 → 读回」全链路可用。

## What Changes

- 新增 `TushareFetcher`（`src/data_provider/tushare/`），实现 `BaseFetcher` 接口（`fetch_quote` / `fetch_fundamentals` / `fetch_all`）
- 扩展 `SourceManager._build_fetcher` 支持 `tushare`，从配置或环境变量读取 Token
- 更新 `config/app.example.yaml` 与 `config_loader` 文档：Token 写入本地 `config/app.yaml`（不入库）或 `TUSHARE_TOKEN` 环境变量
- 新增离线 mock 测试 + `@pytest.mark.network` 验收：对 `config/value_data_validation_stocks.yaml` 样本股验证 Tushare 数据写入 SQLite 且 `source=tushare` 可读回
- 更新 `requirements.txt` / `pyproject.toml` 增加 `tushare` 依赖
- 默认优先级：Tushare **priority 3**（在 AKShare/Baostock 之后 failover；用户可在配置中调高）

## Capabilities

### New Capabilities

（无独立新 capability；Tushare 作为 value-data-provider 的第三数据源扩展）

### Modified Capabilities

- `value-data-provider`：新增 Tushare 数据源接入、Token 配置与缺失 Token 时的优雅跳过/报错行为
- `value-data-pipeline-e2e`：新增 Tushare 启用时的落库读回验收（基于验证样本清单）

## Impact

| 区域 | 影响 |
|------|------|
| `src/data_provider/tushare/` | 新增 fetcher + field_mapping |
| `src/data_provider/manager.py` | 注册 tushare 构建逻辑，传入 token |
| `src/common/config_loader.py` | 可选：合并 `TUSHARE_TOKEN` 环境变量 |
| `config/app.example.yaml` | 补充 tushare 启用示例与 Token 说明 |
| `test/data_provider/test_tushare_fetcher.py` | 新增离线测试 |
| `test/e2e/test_tushare_pipeline.py` | 新增网络验收（无 Token 时 skip） |
| `docs/mrd/features/value-analysis.md` §9 | 归档前补充 Tushare 数据源说明 |
| `docs/dev/engineering-conventions.md` | 技术栈增加 tushare 依赖 |
| `pyproject.toml` / `requirements.txt` | 新增 `tushare>=1.4.0` |

**安全**：Token MUST NOT 提交到 Git；仅存在于 `config/app.yaml`（已 gitignore）或环境变量。
