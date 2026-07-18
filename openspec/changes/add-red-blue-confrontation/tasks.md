## 1. 前置依赖确认

- [ ] 1.1 确认 `add-llm-narrative-core` 已归档，`narrate()` 可用（`from common.llm.narrator import narrate`）

## 2. DualTrackAnalyzer.analyze_offline()

- [ ] 2.1 `src/service/dual_track/analyzer.py` 新增 `analyze_offline(code: str) -> DualTrackReport`，内部调用 `ValueAnalyzer.analyze_offline()` + `TechAnalyzer.analyze(code, offline=True)`
- [ ] 2.2 复用既有 `SignalFusion.fuse()` 与 `build_analysis_summary()` 逻辑，不重复实现
- [ ] 2.3 单测 `test/service/dual_track/test_analyzer.py`：新增 `analyze_offline` 成功场景、无本地缓存降级场景、验证不发起网络请求（mock provider 断言未调用联网方法）
- [ ] 2.4 回归测试确认既有 `analyze()`（联网版）行为不变

## 3. EvidenceBucketer

- [ ] 3.1 新建 `src/service/dual_track/evidence_bucketer.py`：`EvidenceBucketer.bucket(report: DualTrackReport) -> tuple[list[str], list[str]]`
- [ ] 3.2 实现价值面分类：优先读取 `value_trap` 等结构化 `details` 字段判断正负极性，fallback 到 assessment 关键词匹配
- [ ] 3.3 实现技术面分类：`signal_reasons` → bull，`risk_factors` → bear（直接映射，无需额外判断）
- [ ] 3.4 单测 `test/service/dual_track/test_evidence_bucketer.py`：覆盖低估+多头归 bull、value_trap High 归 bear、risk_factors 归 bear 等 spec 场景

## 4. 兜底假设脆弱性规则

- [ ] 4.1 在 `EvidenceBucketer` 内实现按 `prototype`（bank/high_dividend/value_growth/unknown）的方法论局限性文案库（硬编码字典）
- [ ] 4.2 实现触发条件：`bull_evidence` 或 `bear_evidence` 条数 `< 2` 时追加对应兜底条目
- [ ] 4.3 单测覆盖：强多头个股（bear_evidence 为空）触发兜底、验证兜底文案不含具体数值断言

## 5. ConfrontationGenerator

- [ ] 5.1 新建 `src/service/dual_track/confrontation.py`：定义 Level 1 输出 JSON Schema（`bull_report`/`bear_report`/`bull_rebuts_bear`/`bear_rebuts_bull`/`confidence`）
- [ ] 5.2 编写 prompt instruction：要求反驳锚定证据条目、禁止引入新论点/新数字
- [ ] 5.3 实现 `ConfrontationGenerator.generate(bull_evidence, bear_evidence) -> ConfrontationResult`，内部调用 `narrate()`
- [ ] 5.4 实现 `narrate()` 失败时的降级：返回 `narrative_failed=True` + 原始证据分桶内容
- [ ] 5.5 单测 `test/service/dual_track/test_confrontation.py`：mock `narrate()` 成功/失败两种路径

## 6. ConfrontationRecord 持久化

- [ ] 6.1 `src/dao/models.py` 新增 `ConfrontationRecord` ORM：`code`, `generated_at`, `bull_report`, `bear_report`, `rebuttals`(Text/JSON), `accepted_side`(nullable), `reason_text`(nullable)
- [ ] 6.2 `src/dao/engine.py` 的 `ensure_sqlite_schema()` 补充建表逻辑
- [ ] 6.3 新建 `src/dao/confrontation_repo.py`：`save(record)` / `find_by_code(code)`
- [ ] 6.4 单测覆盖：写入成功、`accepted_side`/`reason_text` 缺省时不报错

## 7. CLI `report dual`

- [ ] 7.1 `src/apps/cli.py` 新增 `run_report_dual(code, narrate=False, as_json=False, output=None, config=None)`：
  - 内部调用 `DualTrackAnalyzer.analyze_offline()`、`EvidenceBucketer`
  - `narrate=True` 时额外调用 `ConfrontationGenerator`，失败时打印 warning 并降级
- [ ] 7.2 `build_parser()` 新增 `report dual` 子命令：`code` 位置参数、`--narrate`/`--json`/`--output`/`--quiet` flag，`--narrate` 帮助文本注明"将联网调用 LLM"
- [ ] 7.3 `src/apps/formatters.py` 新增 `format_dual_report(evidence_bull, evidence_bear, confrontation_result | None, as_json) -> str`
- [ ] 7.4 本地无快照时复用现有错误提示模式（`[error] 未找到 <code> 的本地数据，请先运行 sync`）
- [ ] 7.5 单测 `test/apps/test_cli_report_dual.py`：覆盖默认离线成功、`--narrate` 成功、`--narrate` 失败降级、无缓存报错四种场景

## 8. 端到端验证

- [ ] 8.1 `sync 600519` 后运行 `report dual 600519`，确认 Level 0 输出证据分桶且不联网（可通过 mock/日志确认无 HTTP 调用）
- [ ] 8.2 配置真实/mock LLM 后运行 `report dual 600519 --narrate`，确认 Level 1 报告生成且含免责声明
- [ ] 8.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 9. 文档

- [ ] 9.1 更新 `docs/mrd/product-overview.md` §6/§7：PO-03 状态从「待建」更新为「V1 Level 1 已实现」，注明用户声明环节留待 Web 层
- [ ] 9.2 更新 `docs/mrd/roadmap-todo.md`：新增变更记录，PO-03 状态更新

## 10. 归档

- [ ] 10.1 确认 `tasks.md` 全部任务完成
- [ ] 10.2 运行 `/opsx-archive add-red-blue-confrontation` 归档，同步 specs 到 `openspec/specs/`
