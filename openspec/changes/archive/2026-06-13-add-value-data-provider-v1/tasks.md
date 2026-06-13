## 1. 脚手架与依赖

- [x] 1.1 在 `pyproject.toml` / `requirements.txt` 增加运行时依赖 akshare、baostock、SQLAlchemy，固定可用版本
- [x] 1.2 创建模块骨架：`src/data_provider/{base.py,manager.py,provider.py}`、`src/data_provider/{akshare,baostock,validation}/`、`src/dao/{engine.py,models.py,stock_snapshot_repo.py}`、`src/common/models/`
- [x] 1.3 在 `config/app.example.yaml` 增加 `data_sources`（启用项 + 优先级）与 `db.url`（默认 SQLite，注释 MySQL 示例）；`config/app.yaml` 不入库

## 2. 数据模型与基类（src/common, src/data_provider/base.py）

- [x] 2.1 在 `src/common/models/stock_data.py` 定义 `StockData` dataclass，字段覆盖 MRD §7 V1 三原型需求（行情/每股/盈利/现金流/资产负债/分红/质量风险明细；不含历史 PE/PB 序列），含 `field_sources`、`data_timestamp`、`fundamental_report_date`、`missing_fields` 元数据
- [x] 2.2 在 `src/common/exceptions.py` 增加 `UnsupportedMarketError`、`DataProviderError`
- [x] 2.3 在 `src/data_provider/base.py` 定义 `BaseFetcher` 抽象（含 `priority`、source_name、fetch_quote/fetch_fundamentals/fetch_all）与 `FetchResult`（None+missing_fields 语义，见 design D4）
- [x] 2.4 编写 `test/common/test_stock_data.py`：模型字段、默认值、缺失语义

## 3. AKShare 接入（主源，免 token）

- [x] 3.1 拷贝 `ref/valueinvest` 的 AKShare 列名→字段映射到 `src/data_provider/akshare/field_mapping.py`，文件头标注来源/原路径/commit/许可证（工程约定 §5）
- [x] 3.2 实现 `src/data_provider/akshare/fetcher.py`：A 股代码标准化与交易所识别、行情（`stock_individual_info_em`）、三大财报（`stock_financial_report_sina`）、分红（`stock_dividend_cn`）、财务指标（`stock_financial_analysis_indicator`）
- [x] 3.3 实现缺失降级（None + `missing_fields`）与来源/时效元数据填充；指数退避重试 + 上限
- [x] 3.4 编写 `test/data_provider/test_akshare_fetcher.py`：本地 fixture 离线单测，覆盖字段解析与缺失标注

## 4. Baostock 接入（第二源，免 token）

- [x] 4.1 参考 `ref/daily_stock_analysis` 的 Baostock 实现，拷贝字段映射到 `src/data_provider/baostock/field_mapping.py`（标注来源）
- [x] 4.2 实现 `src/data_provider/baostock/fetcher.py`：登录/登出管理、行情与可得财务字段，统一为 `FetchResult`
- [x] 4.3 编写 `test/data_provider/test_baostock_fetcher.py`：本地 fixture 离线单测

## 5. 多源管理与 Provider Facade

- [x] 5.1 实现 `src/data_provider/manager.py` 的 `SourceManager`：持有 fetcher 列表、按 `priority` 排序、自动 failover（对齐 daily_stock_analysis `DataFetcherManager`）
- [x] 5.2 实现配置驱动：从 `config/app.yaml` 的 `data_sources` 读取启用源与优先级；未启用源不实例化/不调用
- [x] 5.3 实现 `src/data_provider/provider.py` 的 `get_stock_data(code) -> StockData`：按优先级逐字段填充、记录每字段命中源、合并元数据；非 A 股抛 `UnsupportedMarketError`
- [x] 5.4 编写 `test/data_provider/test_manager.py` / `test_provider.py`：优先级选源、配置启停、failover、非 A 股拒绝、字段合并与元数据

## 6. 持久化（src/dao，SQLite via SQLAlchemy）

- [x] 6.1 实现 `src/dao/engine.py`：从 `config` 读 `db.url`（默认 SQLite），创建 engine/session；SQLite 启用 WAL + busy_timeout；仅用通用 SQLAlchemy 能力（预留 MySQL）
- [x] 6.2 实现 `src/dao/models.py`：原始快照 ORM 表，唯一键 `(code, source, report_period/fetch_date)`，含来源/时效列
- [x] 6.3 实现 `src/dao/stock_snapshot_repo.py`：按唯一键 upsert 写入、按 (code, source) 查询；**不写 csv**
- [x] 6.4 打通 provider → dao：采集结果按源独立落库（多源不互相覆盖）
- [x] 6.5 编写 `test/dao/test_stock_snapshot_repo.py`：内存/临时 SQLite，验证多源独立留存、upsert 去重、按源查询

## 7. 交付门槛一 — 数据完备性校验

- [x] 7.1 在 `src/data_provider/validation/field_requirements.py` 落 MRD §7 "原型 → 必需字段"表（银行 / 高股息 / 价值成长）
- [x] 7.2 实现 `src/data_provider/validation/completeness.py`：按原型校验字段覆盖，输出覆盖/缺失报告
- [x] 7.3 编写 `test/data_provider/test_completeness.py`：对样本股票（工行/招行、长江电力、贵州茅台）断言必需字段满足或明确列出缺失（标 `@pytest.mark.network`，并提供 fixture 离线版）

## 8. 交付门槛二 — 与参考项目一致性校验（0.1%）

- [x] 8.1 实现 `test/data_provider/test_consistency_with_ref.py`：测试内以独立方式调用 `ref/valueinvest`（临时 sys.path 仅限测试或子进程跑 ref CLI），生产代码不 import ref
- [x] 8.2 对样本股票对比关键字段（当前价、EPS、BVPS、营收、净利润、股息率等），**相对误差 ≤ 0.1%** 否则失败；财报口径不放宽
- [x] 8.3 处理参考侧 0 填充 vs 本侧 None 的归一化（design D7），输出差异报告到 `reports/`
- [x] 8.4 标 `@pytest.mark.network`；记录一次交付前完整运行结果

## 9. 收尾与文档

- [x] 9.1 运行 `pytest`（含 network 标记的交付校验）确认两项门槛通过，留存报告到 `reports/`
- [x] 9.2 `ruff` 通过，修复 lint
- [x] 9.3 归档时将"数据获取方式"合并回 `docs/mrd/features/value-analysis.md` §9（AKShare 主源 + Baostock 已定），消除 §11 T-6
- [x] 9.4 目录/依赖有架构级影响（新增 dao 持久化、data_sources/db 配置）时，同步更新 `docs/dev/engineering-conventions.md` 与 `openspec/config.yaml`
