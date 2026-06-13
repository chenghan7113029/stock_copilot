## Context

价值面分析 V1 需要可信的 A 股数据。`src/data_provider/`、`src/dao/` 当前为空骨架。两个参考项目已实现 A 股取数与存储：

- `ref/valueinvest`：`data/fetcher/akshare.py` 通过 AKShare 取行情 + 三大财报 + 分红 + 财务指标，产出统一 `Stock` 字段集（`FetchResult`，含 `missing_fields`），**全程无 token**。
- `ref/daily_stock_analysis`：`data_provider/` 内含多源 fetcher，由 `DataFetcherManager` 统一管理：每个 fetcher 带 `priority`，`sorted(key=priority)` + 自动 failover，有 token 时动态提优。`src/storage.py` 用 **SQLAlchemy + SQLite**（WAL、busy_timeout、upsert、repositories 模式）持久化。

工程约束（engineering-conventions §5）：**禁止 import `ref/`**；需要的算法/映射须**拷贝**进 `src/` 并标注来源。本变更据此从零搭建 `src/data_provider/` + `src/dao/`，并以两项硬验收（完备性、与参考一致性 0.1%）作为交付门槛。

## Goals / Non-Goals

**Goals:**

- `src/data_provider/`：统一 A 股股票估值数据模型 + 多源（AKShare + Baostock）独立管理，字段覆盖 MRD §7 V1 三原型需求。
- 配置驱动选源 + 优先级（无 token > 有 token 免费 > 有 token 收费）+ 自动 failover，对齐 daily_stock_analysis `DataFetcherManager`。
- `src/dao/`：SQLAlchemy + SQLite 持久化，backend 经 engine URL 可配（预留 MySQL）；来源维度保留原始快照；**禁止本地 csv**。
- 缺失字段显式标注（None + `missing_fields`）+ 来源/时效元数据。
- 两项可复跑校验：完备性校验 + 与参考一致性校验（0.1%）。
- 生产代码零 `ref/` 依赖。

**Non-Goals:**

- 估值方法计算、原型自动分类、区间聚合（后续变更）。
- 技术面 / 情绪面数据；保险/军工等 V2 原型；非 A 股市场。
- 历史 PE/PB 序列（V1.x）。
- 实时高频行情、盘口数据。

## Decisions

### D1：V1 接入 AKShare + Baostock，均免 token

- **选择**：两个数据源都在 V1 接入，均无需 token。AKShare 为主（字段最全，覆盖行情+三大财报+分红+指标）；Baostock 作为第二源（行情/财务交叉补充）。Tushare 仅留适配位、默认关闭（有 token）。
- **理由**：满足"无 token 优先 + A 股 + 完备性"，并落实用户"本期接入 Baostock"。
- **备选**：仅 AKShare 单源（弃，用户要求多源）；上 Tushare（需 token，违反优先级）。

### D2：多源独立管理 + 配置驱动选源/优先级（对齐 DataFetcherManager）

- **选择**：每个数据源是独立 fetcher 类（`AKShareFetcher`/`BaostockFetcher`），实现统一 `BaseFetcher` 接口；`SourceManager` 持有 fetcher 列表，按 `priority` 排序，取数时按优先级尝试 + 自动 failover。
- **配置**：`config/app.yaml` 的 `data_sources` 指定启用哪些源及其优先级；`get_stock_data(code)` 按优先级逐字段填充，记录每字段命中源。
- **理由**：与 daily_stock_analysis 一致，用户已确认。
- **备选**：硬编码单源（弃，缺乏可配置性）。

### D3：从 ref 拷贝字段映射，生产零 import

- **选择**：将 `ref/valueinvest` 的 AKShare 列名→字段映射逻辑拷贝进 `src/data_provider/akshare/`；Baostock 字段映射参考 `ref/daily_stock_analysis` 实现拷贝。文件头标注来源仓库、原路径、commit/日期、许可证（§5 拷贝规范），并补本仓库测试。
- **理由**：禁止 import `ref/`；拷贝后视为本仓库代码维护。

### D4：缺失降级用 None + missing_fields（优于参考的 0 填充）

- **选择**：字段无法获取时置 `None` 并加入 `missing_fields`；**不**用 `0` 静默填充。
- **理由**：`ref/valueinvest` 的 `0` 填充无法区分"真实为 0"与"缺失"，下游估值易误判（违反 MRD VA-DATA-1）。
- **影响**：一致性对比时把参考侧 `0` 与本侧 `None` 归一化（见 D7）。

### D5：分层与模块落点

```text
src/
├── common/models/stock_data.py        # StockData 数据模型（共享类型）
├── common/exceptions.py               # UnsupportedMarketError / DataProviderError
├── data_provider/
│   ├── base.py                        # BaseFetcher 抽象 + FetchResult/HistoryResult
│   ├── manager.py                     # SourceManager：选源/优先级/failover
│   ├── akshare/{fetcher.py,field_mapping.py}   # 拷贝自 ref + 适配
│   ├── baostock/{fetcher.py,field_mapping.py}  # 第二源
│   ├── provider.py                    # Facade: get_stock_data(code) -> StockData
│   └── validation/{completeness.py,field_requirements.py}
└── dao/
    ├── engine.py                      # SQLAlchemy engine/session（backend 由 config 决定）
    ├── models.py                      # ORM：原始快照表（含 source 维度）
    └── stock_snapshot_repo.py         # Repository：写入/按源查询
```

- **理由**：数据模型为跨层共享类型放 `common/models/`；取数与选源放 `data_provider/`；持久化放 `dao/`；符合依赖方向 `service → data_provider/dao → common`。

### D6：持久化 —— SQLAlchemy + SQLite，backend 可配，来源维度存储

- **选择**：用 SQLAlchemy ORM；engine URL 来自 `config/app.yaml` 的 `db.url`，V1 默认 `sqlite:///<path>`，后续切 `mysql+...` 仅改配置。原始快照表主键/唯一键为 `(code, source, report_period 或 fetch_date)`，**每个数据源的数据独立成行**，可按源查询与对比；**不写 csv**。
- **理由**：用户选定"单库 + 来源维度"，并将后续迁 MySQL；SQLAlchemy 屏蔽 backend 差异，与 daily_stock_analysis 一致。
- **SQLite 细节**：启用 WAL + busy_timeout（参考 daily_stock_analysis），写入用 upsert（on conflict 按唯一键更新）。

### D7：两项交付门槛的实现

- **完备性校验**（`validation/completeness.py`）：以 `field_requirements.py` 中"原型→必需字段"表，对样本股票（工行/招行=银行、长江电力=高股息、贵州茅台=价值成长）输出字段覆盖报告；必需字段缺失即判不通过。
- **一致性校验**（`test/data_provider/test_consistency_with_ref.py`，标 `@pytest.mark.network`）：本层 AKShare 取数 vs `ref/valueinvest` 同源结果，关键字段（当前价、EPS、BVPS、营收、净利润、股息率等）**相对误差 ≤ 0.1%** 否则失败，财报口径**不放宽**；参考侧 `0`/本侧 `None` 归一化为"参考缺失"不计差异但报告标注。参考项目仅在测试内以独立方式调用（临时 sys.path 或子进程跑 ref CLI），生产代码不 import `ref/`。
- **注意**：0.1% 容差针对"本层 vs 参考（同为 AKShare）"；**跨源差异（AKShare vs Baostock）属正常**，由选源优先级处理，不纳入该一致性门槛。

## Risks / Trade-offs

- [AKShare/Baostock 接口不稳定 / 限频] → fetcher 层指数退避重试 + 上限；测试用本地 fixture 缓存样本响应离线跑。
- [0.1% 容差偏紧] → 因对比为同源（AKShare）逐字段，差异主要来自解析/取数口径，0.1% 可达；若个别字段因参考侧派生算法（如 FCF=经营现金流−capex）有差，需在测试中对齐口径或单列豁免并记录。
- [Baostock 字段口径与 AKShare 不同] → 仅作交叉/补充源，不参与一致性门槛；选源时高优先级（AKShare）已有字段不被覆盖。
- [SQLite→MySQL 迁移] → 仅用 SQLAlchemy 通用特性，避免 SQLite 专有 SQL；upsert 用 SQLAlchemy 方言适配；迁移时仅改 `db.url` + 跑建表。
- [参考侧 0 填充 vs 本侧 None] → 一致性对比归一化处理并在报告标注。
- [一致性测试需安装 akshare 等] → 标 `@pytest.mark.network`，CI 可选；交付前必跑一次留报告到 `reports/`。

## Migration Plan

- 纯新增，无既有行为变更，无需回滚。
- 新增依赖 akshare、baostock、SQLAlchemy 写入 `requirements.txt` / `pyproject.toml`。
- `config/app.example.yaml` 增加 `data_sources` 与 `db.url` 示例；`config/app.yaml` 不入库。
- 交付即跑：完备性 + 一致性校验，报告存 `reports/`。
- 归档后将"数据获取方式"合并回 [docs/mrd/features/value-analysis.md](../../../docs/mrd/features/value-analysis.md) §9，消除 §11 T-6。

## Open Questions（已解决）

- ~~历史 PE/PB 序列~~ → **推迟到 V1.x**（不在本变更）。
- ~~一致性容差~~ → **相对误差 0.1%，财报口径不放宽**。
- ~~Baostock 是否纳入 / 存储粒度~~ → **Baostock 本期接入；单库 + 来源维度存储；SQLAlchemy（后续迁 MySQL）**。
