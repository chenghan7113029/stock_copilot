## 1. 数据获取层：AKShare 筹码分布

- [x] 1.1 `src/data_provider/akshare/fetcher.py` 新增 `fetch_chip_distribution(self, code: str) -> pd.DataFrame`：调用 `ak.stock_cyq_em(symbol=code, adjust="qfq")`，重命名列为 `trade_date`/`winner_ratio`/`avg_cost`/`concentration_90`/`concentration_70`/`cost_90_low`/`cost_90_high`/`cost_70_low`/`cost_70_high`，数值列 `pd.to_numeric(errors="coerce")`
- [x] 1.2 空数据或异常时抛出 `DataProviderError`（对齐 `fetch_kline` 现有异常处理风格）
- [x] 1.3 单测 `test/data_provider/test_akshare_fetcher.py`（或对应现有文件）新增：正常返回场景（mock `ak.stock_cyq_em`）、空数据抛异常场景

## 2. 持久化层：ChipDistribution 表 + Repo

- [x] 2.1 `src/dao/models.py` 新增 `ChipDistribution` ORM：`__tablename__ = "chip_distribution"`，字段 `code`/`trade_date`（复合主键）+ `winner_ratio`/`avg_cost`/`concentration_90`/`concentration_70`/`cost_90_low`/`cost_90_high`/`cost_70_low`/`cost_70_high`（均 `Float | None`）
- [x] 2.2 新建 `src/dao/chip_distribution_repo.py`：`ChipDistributionRepo`，方法 `query_latest(code) -> dict | None`、`query_range(code, start_date, end_date) -> list[dict]`、`upsert_batch(records)`（镜像 `KlineRepo` 的 `sqlite_insert(...).on_conflict_do_update(...)` 模式）
- [x] 2.3 单测 `test/dao/test_chip_distribution_repo.py`：upsert 后 `query_latest` 返回最新日期行；`upsert_batch` 对已存在 `(code, trade_date)` 覆盖更新而非重复插入

## 3. Provider 层：ChipDistributionProvider

- [x] 3.1 新建 `src/data_provider/chip_distribution_provider.py`：`ChipDistributionProvider.__init__(repo, akshare_fetcher=None)`
- [x] 3.2 实现 `get_latest(code, offline=False, on_progress=None) -> tuple[dict | None, list[str]]`：
  - `offline=True`：只调用 `repo.query_latest(code)`，无缓存返回 `(None, ["无缓存数据"])`
  - `offline=False`：调用 `fetch_chip_distribution()`，成功则 `upsert_batch` 未缓存历史行并返回最新一行；`DataProviderError` 时回退到本地缓存（若有）并在 `warnings` 追加失败原因；两者皆无则返回 `(None, warnings)`
- [x] 3.3 单测 `test/data_provider/test_chip_distribution_provider.py`：覆盖 §设计 中「离线只读缓存」「联网首次拉取」「获取失败回退缓存」「无缓存且获取失败」四个场景（mock repo + mock fetcher，断言 offline 模式下 fetcher 未被调用）

## 4. 分类规则：ChipStatus

- [x] 4.1 `src/service/tech/config.py` 的 `IndicatorParams` 新增 `chip_concentration_strong: float = 10.0`、`chip_concentration_weak: float = 30.0`
- [x] 4.2 `src/service/tech/models/tech_result.py` 新增 `ChipStatus` 枚举：`HIGHLY_CONCENTRATED = "高度控盘"`、`CONCENTRATED = "较为集中"`、`NORMAL = "正常分布"`、`DISPERSED = "筹码分散"`
- [x] 4.3 新建 `src/service/tech/chip_classifier.py`：`classify_chip_status(concentration_90: float | None, params: IndicatorParams) -> ChipStatus | None`（纯函数，`concentration_90 is None` 时返回 `None`）
- [x] 4.4 单测 `test/service/tech/test_chip_classifier.py`：覆盖四档分类边界值 + `None` 输入场景

## 5. TechAnalysisResult 字段与 TechAnalyzer 编排

- [x] 5.1 `src/service/tech/models/tech_result.py` 的 `TechAnalysisResult` 新增字段：`winner_ratio: float | None = None`、`trap_ratio: float | None = None`、`avg_cost: float | None = None`、`concentration_90: float | None = None`、`concentration_70: float | None = None`、`chip_status: ChipStatus | None = None`
- [x] 5.2 `src/service/tech/analyzer.py` 的 `TechAnalyzer.__init__` 新增可选依赖 `chip_provider: ChipDistributionProvider | None = None`；`from_config()` 自动构造 `ChipDistributionRepo` + `ChipDistributionProvider`
- [x] 5.3 `analyze()` 在周线分析后新增步骤：调用 `self._chip_provider.get_latest(code, offline=offline)`，成功时设置 `winner_ratio`/`trap_ratio`（= `100 - winner_ratio`）/`avg_cost`/`concentration_90`/`concentration_70`/`chip_status`（调用 `classify_chip_status`），失败时保持 `None` 并 `result.warnings.extend(chip_warnings)`
- [x] 5.4 `analyze()` 在 `chip_status` 非 None 时追加 `signal_reasons`/`risk_factors` 文案：`HIGHLY_CONCENTRATED`/`CONCENTRATED` → `signal_reasons` 追加「筹码集中度较高（90%集中度 {x:.1f}%），主力控盘特征明显」；`trap_ratio` 较高（如 > 60）时 → `risk_factors` 追加「套牢比例较高（{trap_ratio:.1f}%），反弹阻力可能较大」
- [x] 5.5 单测 `test/service/tech/test_analyzer.py` 新增场景：筹码分布数据可用时字段正确合并；`chip_provider` 返回 `(None, [...])` 时筹码字段为 None 且不影响 `buy_signal`/`signal_score`；`offline=True` 时 `chip_provider.get_latest` 以 `offline=True` 被调用（mock 断言）

## 6. CLI 集成

- [x] 6.1 `src/apps/cli.py` 的 `run_sync()` 新增：构造 `ChipDistributionRepo` + `ChipDistributionProvider`，调用 `get_latest(code, offline=False, on_progress=progress_cb)`，纳入现有 `session.commit()` 事务；失败时打印 `[warn]`（不中断 sync 流程，与 K 线失败的强中断行为区分，因为筹码分布非分析前提）
- [x] 6.2 `src/apps/formatters.py` 的 `format_tech_report()` 新增「--- 筹码分布 ---」展示区块：`获利比例 {winner_ratio}% | 套牢比例 {trap_ratio}% | 平均成本 {avg_cost} | 集中度(90%/70%) {concentration_90}/{concentration_70} | {chip_status}`；字段为 `None` 时整个区块跳过（不显示占位符）
- [x] 6.3 单测 `test/apps/test_cli_*.py` 或 `test/apps/test_formatters.py` 新增：筹码字段存在/不存在两种场景下 `format_tech_report()` 输出断言；`--json` 模式下筹码字段可被 `json.loads` 解析

## 7. 端到端验证

- [x] 7.1 `sync 600519` 后运行 `report tech 600519`，人工核对输出中「筹码分布」区块与 AKShare `stock_cyq_em(symbol="600519")` 返回的最新一行数值一致
- [ ] 7.2 断网/mock AKShare 抛异常场景下运行 `report tech <code>`（已有历史缓存），确认技术面报告正常输出，仅筹码分布区块缺失或标注警告
- [x] 7.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 8. 文档更新

- [x] 8.1 更新 `docs/mrd/features/tech-analysis.md` §2.2：F-17 状态由「待建」更新为「✅」，补充说明；§4.2 输出契约补充筹码分布字段分组；§7.1 已交付文件清单新增本 change 相关文件
- [x] 8.2 更新 `docs/mrd/roadmap-todo.md` §3：F-17 状态勾选为已实现，追加变更记录条目

## 9. 归档

- [ ] 9.1 确认 `tasks.md` 全部任务完成，`openspec validate add-chip-distribution --strict` 通过
- [ ] 9.2 运行归档流程（`/opsx-archive add-chip-distribution` 或等效命令），同步 delta specs 到 `openspec/specs/`
