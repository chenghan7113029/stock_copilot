## 1. DualTrackAnalyzer.analyze_offline()

- [x] 1.1 `src/service/dual_track/analyzer.py` 新增 `analyze_offline(code: str) -> DualTrackReport`，内部调用 `ValueAnalyzer.analyze_offline()` + `TechAnalyzer.analyze(code, offline=True)`
- [x] 1.2 复用既有 `SignalFusion.fuse()` 与 `build_analysis_summary()` 逻辑，不重复实现
- [x] 1.3 单测 `test/service/dual_track/test_analyzer.py`：新增 `analyze_offline` 成功场景、无本地缓存降级场景、验证不发起网络请求（mock provider 断言未调用联网方法）
- [x] 1.4 回归测试确认既有 `analyze()`（联网版）行为不变

## 2. EvidenceBucketer

- [x] 2.1 新建 `src/service/dual_track/evidence_bucketer.py`：`EvidenceBucketer.bucket(report: DualTrackReport) -> tuple[list[str], list[str]]`
- [x] 2.2 实现价值面分类：优先读取 `value_trap` 等结构化 `details` 字段判断正负极性，fallback 到 assessment 关键词匹配
- [x] 2.3 实现技术面分类：`signal_reasons` → bull，`risk_factors` → bear（直接映射，无需额外判断）
- [x] 2.4 单测 `test/service/dual_track/test_evidence_bucketer.py`：覆盖低估+多头归 bull、value_trap High 归 bear、risk_factors 归 bear 等 spec 场景

## 3. 兜底假设脆弱性规则

- [x] 3.1 在 `EvidenceBucketer` 内实现按 `prototype`（bank/high_dividend/value_growth/unknown）的方法论局限性文案库（硬编码字典）
- [x] 3.2 实现触发条件：`bull_evidence` 或 `bear_evidence` 条数 `< 2` 时追加对应兜底条目
- [x] 3.3 单测覆盖：强多头个股（bear_evidence 为空）触发兜底、验证兜底文案不含具体数值断言

## 4. CLI `report dual`（严格离线，无联网 flag）

- [x] 4.1 `src/apps/cli.py` 新增 `run_report_dual(code, as_json=False, output=None, config=None)`：内部调用 `DualTrackAnalyzer.analyze_offline()`、`EvidenceBucketer`，输出证据分桶结果，全程不联网
- [x] 4.2 `build_parser()` 新增 `report dual` 子命令：`code` 位置参数、`--json`/`--output`/`--quiet` flag（与 `report tech`/`report value` 对齐，不新增任何联网相关 flag）
- [x] 4.3 `src/apps/formatters.py` 新增 `format_dual_report(bull_evidence, bear_evidence, as_json) -> str`
- [x] 4.4 本地无快照时复用现有错误提示模式（`[error] 未找到 <code> 的本地数据，请先运行 sync`）
- [x] 4.5 单测 `test/apps/test_cli_report_dual.py`：覆盖成功输出、`--json`/`--output` 行为、无缓存报错三种场景

## 5. Cursor Skill：红蓝对抗互驳叙事

- [x] 5.1 新建 `.cursor/skills/red-blue-confrontation/SKILL.md`（参照 `.cursor/skills/openspec-*` 的 frontmatter 格式：`name`/`description`/`compatibility`）
- [x] 5.2 SKILL.md 内写明输入契约：执行 `python -m apps.cli report dual <code> --json` 获取 `bull_evidence[]`/`bear_evidence[]`；代码未提供时先询问用户
- [x] 5.3 SKILL.md 内写明生成约束：多空论述与互驳均须锚定证据条目、禁止编造证据外数字、输出末尾固定免责声明
- [x] 5.4 SKILL.md 内写明输出呈现：对话内直接呈现完整结构；可选落盘 `reports/<code>_confrontation.md`，不写数据库
- [x] 5.5 人工验证：对 1-2 个真实代码（如强多头 `600519`、证据均衡的其他代码）手动触发 Skill，检查输出是否满足契约（引用具体证据条目、含免责声明、无编造数字）

## 6. 端到端验证

- [x] 6.1 `sync 600519` 后运行 `report dual 600519`，确认输出证据分桶（含兜底条目，若触发）且不联网（可通过 mock/日志确认无 HTTP 调用）
- [x] 6.2 触发红蓝对抗 Skill 处理 `report dual 600519 --json` 的输出，人工检查生成叙事是否符合 §5.5 契约
- [x] 6.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 7. 文档

- [x] 7.1 更新 `docs/mrd/product-overview.md` §6/§7：PO-03 状态更新为「V1（Skill 版）已实现：证据分桶 + Cursor Skill 互驳叙事；Web + 独立 LLM API 版待建（依赖已冻结的 `add-llm-narrative-core`）」
- [x] 7.2 更新 `docs/mrd/roadmap-todo.md`：新增变更记录，PO-03 状态更新
- [x] 7.3 更新 `docs/dev/engineering-conventions.md`（如涉及新目录/模块职责变化，如 `.cursor/skills/` 的项目级 Skill 说明）

## 8. 归档

- [x] 8.1 确认 `tasks.md` 全部任务完成
- [x] 8.2 运行 `/opsx-archive add-red-blue-confrontation` 归档，同步 specs 到 `openspec/specs/`
