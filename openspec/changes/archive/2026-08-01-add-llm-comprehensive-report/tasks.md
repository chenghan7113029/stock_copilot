## 1. ContextPack 打包

- [x] 1.1 新建 `src/service/report/context_pack.py`：`build_dual_track_evidence(report: DualTrackReport) -> dict`
- [x] 1.2 实现价值面字段打包（`fair_value_range`/`margin_of_safety`/`price_percentile`/`assessment`/`confidence`/`prototype`），`value_result is None` 时跳过该分区
- [x] 1.3 实现技术面字段打包（`trend_status`/`signal_score`/`buy_signal`/`signal_reasons`/`risk_factors`），`tech_result is None` 时跳过该分区
- [x] 1.4 实现融合字段打包（`combined_signal`/`value_rating`）
- [x] 1.5 单测 `test/service/report/test_context_pack.py`：覆盖双维度均存在、单维度缺失、`Enum` 值序列化为 `.value` 三种场景

## 2. 综合报告叙事封装

- [x] 2.1 新建 `src/service/report/comprehensive_narrator.py`：定义 `COMPREHENSIVE_REPORT_SCHEMA`（`summary`/`key_points`/`risks`/`confidence`）
- [x] 2.2 定义 instruction 文本：显式声明「不得引入 evidence 之外的新数字/新结论」
- [x] 2.3 实现 `narrate_comprehensive_report(report, config=None, client=None, cache=None) -> NarrateResult`：调用 `build_dual_track_evidence()` + `common.llm.narrate()`
- [x] 2.4 单测 `test/service/report/test_comprehensive_narrator.py`（mock `narrate()`）：覆盖成功、LLM 未配置、grounded 校验失败三种场景

## 3. CLI `report summary`

- [x] 3.1 `src/apps/cli.py` 新增 `run_report_summary(code, as_json=False, output=None, narrate=False, config=None)`：默认离线路径复用 `build_analysis_summary()` + `EvidenceBucketer` 证据条数；`narrate=True` 时额外调用 `narrate_comprehensive_report()`
- [x] 3.2 `build_parser()` 新增 `report summary` 子命令：`code` 位置参数、`--json`/`--output`/`--quiet`/`--narrate`
- [x] 3.3 `main()` 分发逻辑新增 `report_type == "summary"` 分支
- [x] 3.4 `src/apps/formatters.py` 新增 `format_summary_report(...)`：`--narrate` 失败时降级为「确定性摘要 + 失败原因」提示，不阻断输出
- [x] 3.5 单测 `test/apps/test_cli_report_summary.py`：覆盖默认离线、`--narrate` 成功（mock narrate）、`--narrate` 失败降级、无本地数据报错四种场景

## 4. 端到端验证

- [x] 4.1 `sync 600519` 后运行 `report summary 600519`（不传 `--narrate`），确认输出确定性摘要，且不发起网络请求
- [x] 4.2 配置测试用 LLM（或 mock）后运行 `report summary 600519 --narrate`，人工检查叙事内容是否引用了确定性摘要中的数字，无编造新数字
- [x] 4.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 5. add-llm-narrative-core 状态同步

- [x] 5.1 更新 `openspec/changes/add-llm-narrative-core/proposal.md` 顶部状态说明：移除「已冻结」标注，注明消费方为 `add-llm-comprehensive-report`
- [x] 5.2 更新 `openspec/changes/add-llm-narrative-core/tasks.md` 第 10.3 项：视情况执行 `/opsx-archive add-llm-narrative-core`

## 6. 文档更新

- [x] 6.1 更新 `docs/mrd/product-overview.md` §5.3：PO-02「LLM 综合报告」状态更新为「已实现」
- [x] 6.2 更新 `docs/mrd/roadmap-todo.md`：PO-02 状态更新、价值面待办 G 状态更新、新增变更记录

## 7. 归档

- [x] 7.1 确认 `tasks.md` 全部任务完成
- [x] 7.2 运行 `/opsx-archive add-llm-comprehensive-report` 归档，同步 specs 到 `openspec/specs/`
