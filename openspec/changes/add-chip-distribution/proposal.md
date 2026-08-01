## Why

`docs/mrd/roadmap-todo.md` §3 F-17（P2）与 `docs/mrd/features/tech-analysis.md` §2.2 均已列出「筹码分布」为技术面待办：当前 `TechAnalyzer` 的六维评分（趋势/乖离率/量能/支撑/MACD/动量）全部基于价格与均线动量，缺一个反映「持仓成本结构」的维度——同样是放量突破或回踩买点，若套牢盘极重，反弹阻力和解套抛压会显著不同，但现有指标体系无法区分这两种情况。AKShare `stock_cyq_em` 已提供东方财富口径的获利比例、平均成本、90%/70% 成本集中度，数据源明确、无需自建计算，是低成本补齐这一信息维度的机会。

## What Changes

- 新增 `AKShareFetcher.fetch_chip_distribution(code)`：封装 `ak.stock_cyq_em(symbol=code, adjust="qfq")`（复权口径与现有 `fetch_kline` 对齐），返回标准化列名的历史序列（`trade_date`/`winner_ratio`/`avg_cost`/`concentration_90`/`concentration_70`/`cost_90_low`/`cost_90_high`/`cost_70_low`/`cost_70_high`）
- 新增独立的 `ChipDistributionProvider`（`src/data_provider/chip_distribution_provider.py`）+ `ChipDistributionRepo`（`src/dao/chip_distribution_repo.py`）+ `ChipDistribution` ORM（`src/dao/models.py`），复用 `KlineProvider`/`KlineRepo` 的缓存范式（按 `code + trade_date` 主键 upsert），但**不复用、不扩展** `KlineProvider` 的 `kline_days` 窗口——`stock_cyq_em` 是 AKShare 服务端基于全历史独立计算的日度序列，与我们自己抓取的 K 线窗口无耦合关系（详见 design.md 决策 1）
- `TechAnalysisResult` 新增结构化字段：`winner_ratio`（获利比例）、`trap_ratio`（套牢比例，代码派生 `100 - winner_ratio`，无需额外数据）、`avg_cost`、`concentration_90`、`concentration_70`、`chip_status`（新枚举 `ChipStatus`，基于集中度分档）；新增纯规则分类函数（`src/service/tech/chip_classifier.py`），阈值放入 `IndicatorParams`
- `TechAnalyzer.analyze()` 编排新增一步：调用 `ChipDistributionProvider` 获取最新一行筹码数据，合并进 `TechAnalysisResult` 并追加 `signal_reasons`/`risk_factors` 文案（如「筹码高度集中，主力控盘明显」/「套牢盘沉重，反弹阻力较大」）；获取失败或无缓存时相关字段保持 `None` 并追加 `warnings`，**不影响**其余技术面字段与 `buy_signal`
- `sync` 命令新增筹码分布拉取与持久化步骤（遵循既有 `add-cli-core` D-1 原则：`report` 永不联网，新数据必须先 `sync`）
- **V1 不纳入 `signal_score` 打分**：筹码字段仅作展示与文案增强，不改变 `BullTrendScorer` 现有 100 分权重体系（见 design.md 决策 2）

**不包含**：
- 不做筹码分布的可视化（分布曲线图等），V1 仅消费 AKShare 已聚合好的标量字段
- 不新增 Baostock 备用数据源（`stock_cyq_em` 为 AKShare 专属接口，无 Baostock 等价物）
- 不在 V1 将筹码指标纳入 `ScoringParams` 打分权重

## Capabilities

### New Capabilities
- `tech-chip-distribution`：筹码分布数据获取（AKShare `stock_cyq_em`）、SQLite 缓存、`ChipStatus` 分类规则

### Modified Capabilities
- `tech-analyzer`：`TechAnalysisResult` 新增筹码字段；`TechAnalyzer.analyze()` 编排新增筹码分布步骤（失败降级、不影响既有字段）

## Impact

- **新增文件**：
  - `src/data_provider/chip_distribution_provider.py`
  - `src/dao/chip_distribution_repo.py`
  - `src/service/tech/chip_classifier.py`
  - `test/data_provider/test_chip_distribution_provider.py`
  - `test/service/tech/test_chip_classifier.py`
- **修改文件**：
  - `src/data_provider/akshare/fetcher.py`：新增 `fetch_chip_distribution()`
  - `src/dao/models.py`：新增 `ChipDistribution` ORM（`chip_distribution` 表）
  - `src/service/tech/models/tech_result.py`：新增 `ChipStatus` 枚举与 `TechAnalysisResult` 筹码字段
  - `src/service/tech/config.py`：`IndicatorParams` 新增筹码集中度分档阈值
  - `src/service/tech/analyzer.py`：`analyze()` 新增筹码分布步骤；`from_config()` 新增依赖构造
  - `src/apps/cli.py`：`run_sync()` 新增筹码分布拉取与持久化
  - `src/apps/formatters.py`：`format_tech_report()` 新增筹码分布展示区块
  - `test/service/tech/test_analyzer.py`：新增筹码字段相关场景
- **依赖**：无新增第三方依赖（复用既有 `akshare`）
- **文档**：`docs/mrd/features/tech-analysis.md` §2.2（F-17 状态由「待建」更新为已实现，补充 §4.2 输出契约字段）、`docs/mrd/roadmap-todo.md` §3（F-17 状态更新 + 变更记录）
