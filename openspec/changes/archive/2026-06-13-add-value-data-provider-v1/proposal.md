## Why

价值面分析模块（MRD §V1：银行 / 高股息·类债 / 高质量价值成长三原型）依赖一套可信、字段完备的 A 股数据。当前 `src/data_provider/` 为空骨架，所有估值方法（PB、剩余收益、DDM、DCF、EPV、Owner Earnings、Graham、相对估值、Altman-Z、Piotroski-F、Beneish-M）都无数据来源，价值面无法落地。

本变更先把 **V1 数据接入层 + 持久化** 建起来：多源（免 token 优先）接入 A 股数据、按配置选源与优先级、落 SQLite 存储（来源维度保留原始快照），并以两项硬性验收（数据完备性、与参考项目结果一致）作为交付门槛，为后续估值引擎提供可信输入。

## What Changes

- 新增 `src/data_provider/` A 股价值面数据接入层：
  - 统一股票估值数据模型（`StockData`），覆盖 MRD §7 V1 三原型所需字段（行情、每股、盈利、现金流、资产负债、分红、质量/风险明细；历史 PE/PB 序列推迟到 V1.x）。
  - **多数据源、单独管理**：V1 接入 **AKShare** 与 **Baostock**（均免 token）；每个数据源为独立 fetcher，对齐 `ref/daily_stock_analysis` 的 `DataFetcherManager` 模式。
  - **配置驱动选源 + 优先级**：通过 `config/app.yaml` 指定启用哪些源；使用数据时按优先级选源（"无 token > 有 token 免费 > 有 token 收费"），高优先级优先 + 自动 failover。
  - 字段缺失降级：缺失显式标注（None + `missing_fields`），附数据来源 + 时效元数据（MRD VA-DATA-1/2）。
- 新增 `src/dao/` 持久化（**本期不写本地 csv**）：
  - 用 **SQLAlchemy + SQLite** 落库；**DB backend 经 engine URL 可配置**（为后续切换 MySQL 预留，切换零改业务代码）。
  - **来源维度存储**：每条原始快照按 `(股票代码, 数据源, 报告期/采集时间)` 留行，可按源查询与逐源对比。
- 算法/字段映射从 `ref/valueinvest/`、`ref/daily_stock_analysis/` **拷贝**进 `src/`（禁止 import ref/，遵循工程约定 §5）。
- 交付门槛（两项必过验收）：
  1. **数据完备性**：接入字段满足 V1 三原型全部估值方法输入需要；
  2. **数据一致性**：本层取数结果与参考项目（`ref/valueinvest` 的 `Stock.from_api`）在**相对误差 0.1%**内一致（同源 AKShare 对比，财报口径不放宽）。
- 提供可复跑验证脚本/测试，对样本股票（工行/招行、长江电力、贵州茅台）执行上述两项校验。

**非目标（本变更不做）：** 估值方法计算、原型自动分类、区间聚合、技术面/情绪面数据、保险/军工等 V2 原型、非 A 股市场、历史 PE/PB 序列（V1.x）。

## Capabilities

### New Capabilities

- `value-data-provider`: A 股价值面数据接入能力 —— 统一股票估值数据模型、多源（AKShare + Baostock，免 token 优先）独立管理、配置驱动选源与优先级 + failover、字段缺失降级与来源/时效元数据，以及"数据完备性 + 与参考项目一致性（0.1%）"两项交付级校验。
- `value-data-store`: 价值面数据持久化能力 —— 基于 SQLAlchemy + SQLite（backend 可配，预留 MySQL）的来源维度原始快照存储，禁止本地 csv，支持按数据源查询与对比。

### Modified Capabilities

<!-- 无既有 spec 变更（openspec/specs/ 当前为空） -->

## Impact

- **代码**：`src/data_provider/`（数据模型引用、多源 fetcher、Manager、选源/优先级、校验工具）、`src/dao/`（SQLAlchemy 模型、Repository、引擎/会话）、`src/common/`（共享类型/异常）、`test/{data_provider,dao}/`（含一致性测试）。
- **依赖**：新增 akshare、baostock、SQLAlchemy；写入 `requirements.txt` / `pyproject.toml`。
- **配置**：`config/app.yaml` 增加 `data_sources`（启用项 + 优先级）与 `db.url`（默认 SQLite 文件，预留 MySQL）；密钥/连接串不入库。
- **参考仓库**：只读引用 `ref/valueinvest`、`ref/daily_stock_analysis` 做算法拷贝与一致性对比，不修改、不 import。
- **文档**：归档后合并回 [docs/mrd/features/value-analysis.md](../../../docs/mrd/features/value-analysis.md) §9（数据获取方式已定：AKShare+Baostock）、消除 §11 T-6；如分层/依赖有架构级影响，更新 [docs/dev/engineering-conventions.md](../../../docs/dev/engineering-conventions.md)。
