## Why

`product-overview.md` §6 将「红蓝军对抗」列为 P0 决策护航机制，用于对抗确认偏差：「多空角色基于同一公开信息各出报告并互相攻击；用户须声明拒绝哪方及理由」。当前 `DualTrackAnalyzer` 已产出丰富的确定性证据（价值面各方法 assessment/warnings、技术面 signal_reasons/risk_factors），但没有任何机制把这些证据组织成对立的多空论述，也没有对外 CLI 入口。本 change 基于 `add-llm-narrative-core` 的基建，实现红蓝对抗的 V1（Level 1：规则证据分桶 + LLM 互相反驳叙事）。

## What Changes

- 新增 `EvidenceBucketer`（纯规则，零 LLM）：从 `DualTrackReport` 中按既有规则将 method assessment/warnings/value_trap/signal_reasons/risk_factors 分类为 `bull_evidence[]` / `bear_evidence[]`
- 新增兜底规则：某一方证据条数过少（< 2 条）时，追加「对方核心假设脆弱性」条目（如 growth_rate 假设、原型方法适用局限、行业周期位置），保证对抗双方始终有内容
- 新增 `DualTrackAnalyzer.analyze_offline(code)`：修复现有 `analyze()` 内部调用联网版 `ValueAnalyzer.analyze()` 的问题，新增离线版本（内部转调 `ValueAnalyzer.analyze_offline()` + `TechAnalyzer.analyze(offline=True)`），供 CLI 严格离线场景使用
- 新增 `ConfrontationGenerator`：调用 `add-llm-narrative-core` 的 `narrate()`，输入双方证据桶，输出结构化 `{bull_report, bear_report, bull_rebuts_bear[], bear_rebuts_bull[]}`；反驳内容锚定已给证据，不引入新事实
- 新增 `ConfrontationRecord` DAO 表：`code / generated_at / bull_report / bear_report / rebuttals(json) / accepted_side(nullable) / reason_text(nullable)`；V1 仅落库生成结果，`accepted_side`/`reason_text` 字段预留但不要求填写（用户声明拒绝哪方及理由依赖未来 Web 界面，本 change 不实现该交互）
- 新增 CLI 入口 `python -m apps.cli report dual <code> [--narrate] [--json] [--output]`：
  - 默认（不加 `--narrate`）：严格离线，仅输出证据分桶 + 兜底脆弱性提示（Level 0），内部复用 `run_report_tech`/`run_report_value` 的 analyzer 装配逻辑
  - `--narrate`：显式联网调用 LLM 生成 Level 1 互相反驳叙事；LLM 调用失败或 grounded 校验不过时降级为 Level 0 输出并打印 warning，不中断命令

## Capabilities

### New Capabilities
- `red-blue-confrontation`：证据分桶规则、兜底脆弱性规则、Level 1 反驳叙事生成、`ConfrontationRecord` 持久化
- `cli-report-dual`：`report dual` 子命令（Level 0 离线 + `--narrate` 显式联网增强）

### Modified Capabilities
- `dual-track-analyzer`：新增 `analyze_offline()` 方法（不改变现有 `analyze()` 行为，向后兼容追加）

## Impact

- **新增文件**：
  - `src/service/dual_track/evidence_bucketer.py`
  - `src/service/dual_track/confrontation.py`（`ConfrontationGenerator` + prompt/schema）
  - `src/dao/models.py`：新增 `ConfrontationRecord` ORM
  - `src/dao/confrontation_repo.py`
  - `src/apps/cli.py`：新增 `report dual` 子命令与 `run_report_dual()`
  - `src/apps/formatters.py`：新增 `format_dual_report()`
  - `test/service/dual_track/test_evidence_bucketer.py`、`test_confrontation.py`
  - `test/apps/test_cli_report_dual.py`
- **修改文件**：
  - `src/service/dual_track/analyzer.py`：新增 `analyze_offline()`
- **依赖**：`add-llm-narrative-core` 必须先归档
- **文档**：`docs/mrd/product-overview.md` §6/§7（PO-03 状态更新）、`docs/mrd/roadmap-todo.md`（新增变更记录）
