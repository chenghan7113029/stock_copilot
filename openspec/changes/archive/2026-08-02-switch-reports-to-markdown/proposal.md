## Why

当前 CLI 落盘报告默认使用 `.txt`，内容多为 `===` / `---` 分隔的纯文本，在编辑器中几乎没有标题层级、列表与强调，阅读体验差。改用 Markdown 扩展名并让默认文本输出符合 Markdown 结构后，本地预览与 GitHub/IDE 渲染都能更易扫读；验收与分享也更顺手。

## What Changes

- **BREAKING（文件名）**：`--watchlist -o <dir>` 及文档示例中的默认落盘扩展名由 `{code}_{kind}.txt` 改为 `{code}_{kind}.md`；用户显式传入 `.txt` / `.json` / `.md` 路径时仍按其后缀写入。
- 所有人类可读报告 formatters（tech / value / dual / summary / dashboard / sentiment / entry-check / trade-review / portfolio / checklist 文本模式）默认输出改为合法、可渲染的 Markdown（标题、列表、粗体等），**不改变** `--json` 契约与字段。
- 更新 `docs/user-guide.md` 及测试中对 `.txt` 默认后缀的断言与示例。
- 本期**不**批量迁移 `reports/` 下已有历史 `.txt`（本地产物、gitignore）；新生成一律 `.md`。

## Capabilities

### New Capabilities

- `report-markdown-output`：报告默认落盘扩展名与人类可读 Markdown 渲染约定（含批量 `-o` 目录规则、与 JSON 模式边界）。

### Modified Capabilities

- `cli-report-tech`：默认文本输出为 Markdown；落盘示例/约定指向 `.md`。
- `cli-report-value`：同上。
- `cli-report-dual`：同上；证据分桶与讲解分区用 Markdown 标题，JSON 仍证据优先。
- `cli-report-summary`：同上。
- `cli-formatter`：若存在统一 formatter 要求，补充「默认人类可读输出为 Markdown」。

## Impact

- **代码**：`src/apps/cli.py`（`_batch_output_path`、help 文案）、`src/apps/formatters.py`（各 `format_*_report`）、相关 CLI/formatter 单测。
- **文档**：`docs/user-guide.md`；归档后可补一行 `docs/design/report-markdown-output.md`（可选，design 阶段定）。
- **工程约定**：一般无需改目录树；若约定写死 `.txt` 示例则同步 `docs/dev/engineering-conventions.md`。
- **兼容**：依赖硬编码 `*_tech.txt` 等路径的本地脚本需改为 `.md`；`--json` 与 Skill 消费 JSON 不受影响。
