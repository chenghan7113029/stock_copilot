## Why

`product-overview.md` §5.3 将「LLM 综合报告」列为 P0 能力（PO-02）：把确定性计算结果打包为 Context，用 LLM 生成可读叙述，且「数值以确定性模块为准」。`docs/mrd/roadmap-todo.md` §4.2 的价值面待办 G 明确「LLM ContextPack：价值面块注入双轨 + LLM 叙述，与 PO-02 合并」。当前用户只能看到 `report tech`/`report value`/`report dual` 输出的结构化数值与关键词式 `assessment`/`signal_reasons`，缺少一段自然语言总结来降低阅读负担。

仓库已具备可复用的 LLM 叙事基建 `common.llm.narrate()`（`add-llm-narrative-core`，已实现并合入主干，但状态为「已冻结，无消费方」）：三层防御（Input Guard 截断 → LLM 核仅做叙事包装 → Output Guard schema 校验 + grounded 数值锚定 + 置信度分级 + 幂等缓存）均已就位。本 change 是它的**首个消费方**，直接调用而不重新造轮子。

## What Changes

- 新增 `src/service/report/context_pack.py::build_dual_track_evidence(report: DualTrackReport) -> dict`：从 `DualTrackReport`（`value_result` + `tech_result`）打包为 `narrate()` 所需的 evidence dict，只包含确定性字段（估值区间、安全边际、评级、趋势状态、信号分、signal_reasons/risk_factors 等），不做任何数值再加工
- 新增 `src/service/report/comprehensive_narrator.py::narrate_comprehensive_report(report, config=None) -> NarrateResult`：定义综合报告的 JSON Schema（`summary`/`key_points[]`/`risks[]`/`confidence`）与 instruction，调用 `common.llm.narrate(evidence, schema, instruction)`；instruction 中显式要求「严禁引入 evidence 之外的新数字/新结论」（`narrate()` 的 grounded 校验已在代码层拦截，此处 prompt 层重复强调作为第二道防线）
- 新增 CLI 入口 `python -m apps.cli report summary <code> [--json] [--output] [--narrate]`：默认严格离线，仅输出确定性摘要（复用 `build_analysis_summary()` 与红蓝证据条数）；显式传入 `--narrate` 时才联网调用 LLM 生成叙事段落，遵循既有「report 默认离线，联网需显式 flag」原则（`add-cli-core` D-1、`add-red-blue-confrontation` 决策 3）
- 新增 `src/apps/formatters.py::format_summary_report()`：text/JSON 双格式，`--narrate` 结果失败时（`ok=False`）降级为仅展示确定性摘要 + 失败原因，不阻断命令输出

**状态变化说明**：本 change 落地后，`add-llm-narrative-core` 从「已冻结、无消费方」变为「已解冻」（有真实消费方）。该状态变化只在本 change 的 design.md 中说明，**不在本次 propose 阶段修改 `add-llm-narrative-core` 自身的 `proposal.md`/`tasks.md`**——那是本 change 实施（apply）阶段才需要同步更新的事。

**不包含（明确推迟）：**
- 不新增独立的红蓝对抗叙事或情绪面叙事（`comprehensive_narrator` 只消费价值面 + 技术面，未来红蓝对抗证据/情绪面数据就绪后可扩展 evidence，不在本 change 范围）
- 不修改 `common/llm/` 下任何文件（`narrate()`/`LLMClient`/grounded 校验均直接复用，零改动）
- 不修改 `report dual` 的既有契约（新增独立的 `report summary` 命令，不在 `report dual` 上追加 `--narrate`）

## Capabilities

### New Capabilities
- `llm-comprehensive-report`：ContextPack 打包（`build_dual_track_evidence`）+ 综合报告 schema/instruction 定义 + `narrate_comprehensive_report()` 调用封装
- `cli-report-summary`：`report summary` 子命令（默认离线摘要，`--narrate` 显式联网叙事）

### Modified Capabilities
（无——不修改 `dual-track-analyzer`、`llm-narrative-core`、`cli-report-dual` 等既有 capability 的既定需求）

## Impact

- **新增文件**：
  - `src/service/report/context_pack.py`
  - `src/service/report/comprehensive_narrator.py`
  - `src/apps/cli.py`：新增 `report summary` 子命令与 `run_report_summary()`
  - `src/apps/formatters.py`：新增 `format_summary_report()`
  - `test/service/report/test_context_pack.py`
  - `test/service/report/test_comprehensive_narrator.py`（mock `narrate()`）
  - `test/apps/test_cli_report_summary.py`
- **修改文件**：无（`src/common/llm/`、`src/service/dual_track/` 均零改动，纯消费）
- **依赖**：依赖已实现但冻结的 `add-llm-narrative-core`（`common.llm.narrate()`）；复用现有 `llm:` 配置段与 `llm_narrate_cache` 表，无新增依赖/新增表
- **文档**：`docs/mrd/product-overview.md` §5.3（PO-02 状态更新为「已实现」）、`docs/mrd/roadmap-todo.md`（PO-02、价值面待办 G 状态更新 + 变更记录）
