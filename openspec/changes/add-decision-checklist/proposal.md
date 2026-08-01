## Why

`product-overview.md` §5.2 将「结构化 Checklist」列为 P0 决策护航机制（PO-04），用于对抗「路径依赖 / 可得性启发」偏差：强制填写价值理由 ≥2 条、技术面配合情况、情绪位置、止损止盈点；仅填一条且明显是「昨晚看新闻」式单一来源理由时须**拦截**提交。§8.1 验收准则明确「买入/卖出意图触发 Checklist，缺字段或仅可得性原因时系统拒绝提交」是 Phase 2 的产品级验收项之一，但当前仓库完全没有 Checklist 的数据模型、校验逻辑与交互入口。

## What Changes

- 新增 DAO 表 `ChecklistRecord`（`src/dao/models.py`）：覆盖 MRD §5.2「Checklist 最低字段」——长期价值理由（≥2 条）、短期技术面配合情况、情绪位置及解读、止损点、止盈点，附加系统校验产出的 `passed`/`rejection_reasons` 字段
- 新增 `src/service/guard/checklist_validator.py`：纯规则校验（零 LLM），实现 MRD 要求的「非可得性单一原因」启发式判定（字数阈值 + 关键词表，V1 粗糙规则，接受局限）
- 新增 CLI 交互式命令 `python -m apps.cli checklist submit <code> [--action buy|sell]`：通过一系列 prompt 收集字段并跑校验；校验通过（`passed=True`）才视为「合规提交」，向用户明确提示；校验失败（`passed=False`）时打印拒绝原因并明确告知「本次提交不构成合规 Checklist」（硬拦截语义），但仍会将本次尝试写入 `ChecklistRecord`（留痕，供未来复盘 PO-09 使用），不做静默丢弃
- 新增 CLI 查询命令 `python -m apps.cli checklist show <code>`：列出该代码的历史 Checklist 提交记录（含通过/拒绝状态）

**不包含（明确推迟）：**
- 不依赖情绪面模块（`add-sentiment-module`）：情绪位置字段 V1 由用户手动文本输入，不校验是否与真实情绪指标一致
- 不做 Web 表单交互（等待 REST API 就绪后的 Web 层，本 change 只做 CLI 交互式命令）
- 不做复盘归因（PO-09，读取 Checklist 历史做胜率统计等，属于 Phase 4 范畴）
- 不做「价值理由须引用价值面输出」的自动化核对（V1 只要求用户在理由文本中包含引用，不做程序化比对用户输入的理由是否确实命中 `ValueAnalysisResult` 的具体字段值，属已知局限）

## Capabilities

### New Capabilities
- `decision-checklist`：`ChecklistRecord` 数据模型 + 纯规则校验逻辑（字段完整性、条数、非可得性单一原因启发式）
- `cli-checklist-submit`：`checklist submit`/`checklist show` 交互式 CLI 命令

### Modified Capabilities
（无——不修改任何既有 capability 的既定需求）

## Impact

- **新增文件**：
  - `src/service/guard/__init__.py`
  - `src/service/guard/models/__init__.py`
  - `src/service/guard/models/checklist.py`（`ChecklistSubmission`/`ChecklistValidationResult` dataclass）
  - `src/service/guard/checklist_validator.py`（`ChecklistValidator.validate(submission) -> ChecklistValidationResult`）
  - `src/dao/checklist_repo.py`（`ChecklistRepo.save()`/`list_by_code()`）
  - `src/apps/cli.py`：新增 `checklist submit`/`checklist show` 子命令
  - `test/service/guard/test_checklist_validator.py`
  - `test/apps/test_cli_checklist.py`
- **修改文件**：
  - `src/dao/models.py`：新增 `ChecklistRecord` ORM
  - `src/dao/engine.py`：`ensure_sqlite_schema()` 补充建表逻辑
- **依赖**：无新增第三方依赖
- **文档**：`docs/mrd/product-overview.md` §5.2/§8.1（PO-04 状态更新为「已实现」、验收准则勾选）、`docs/mrd/roadmap-todo.md`（PO-04 状态更新 + 变更记录）
