## Context

报告内容由 `src/apps/formatters.py` 生成，经 `src/apps/cli.py` 的 `_emit_report` / `_batch_output_path` 落盘。批量模式当前默认 `{code}_{kind}.txt`；stdout 与文件内容均为 `===` / `---` 风格纯文本。用户验收时在 IDE 中打开 `.txt` 缺少标题层级，希望默认改为 Markdown。

约束：依赖方向仍为 apps → service；不改分析结果模型与 `--json` 契约；讲解（explainers）已嵌入文本模式，Markdown 化时须保留其信息，仅改结构标记。

## Goals / Non-Goals

**Goals:**

- 默认批量落盘扩展名为 `.md`；显式后缀仍尊重用户路径。
- 所有默认人类可读 `format_*` 输出为可渲染 Markdown（`#`/`##`、列表、粗体/引用等轻量标记）。
- 文档与单测与新约定对齐。

**Non-Goals:**

- 不引入新依赖（如 markdown 库）做 AST 渲染。
- 不改 `--json` 字段、Skill 对 dual JSON 的消费。
- 不批量转换 `reports/` 历史 `.txt`。
- 不做 HTML/PDF 导出或 Web 预览页。
- 本期不强制统一 emoji 去留策略（保持现有信号文案）。

## Decisions

1. **扩展名默认 `.md`，路径显式优先**  
   `_batch_output_path` 在目录模式下写 `{code}_{kind}.md`；若 `-o` 已带 `.txt`/`.json`/`.md` 则按文件路径处理（现有逻辑已支持后缀集合，只需改默认）。  
   *备选：保留 `.txt` 仅改内容* → 拒绝，扩展名与预览器关联是用户诉求的一部分。

2. **在 formatters 内直接拼 Markdown，不加中间层模板引擎**  
   将 `=== 标题 ===` → `# 标题`，`--- 小节 ---` → `## 小节`，条目改为 `-` 列表；方法卡片等用 `###`。改动集中在 `formatters.py`，CLI 只改后缀与 help。  
   *备选：新建 `MarkdownReportBuilder`* → 过度设计，本期字段稳定、单文件可维护。

3. **stdout 与落盘同一套 Markdown 字符串**  
   避免「屏幕纯文本 / 文件 Markdown」两套逻辑；终端里 Markdown 标记仍可读。  
   *备选：TTY 检测降级* → 增加复杂度，收益低。

4. **测试策略**  
   断言关键 Markdown 标记（如以 `# ` 开头的标题、含 `## ` 小节）与既有业务关键词；更新 `_batch_output_path` 对 `.md` 的断言。不要求完美 CommonMark 校验。

5. **文档**  
   `docs/user-guide.md` 示例一律改为 `.md`；归档后可落 `docs/design/report-markdown-output.md`（从本 design 精简）。

## Risks / Trade-offs

- [依赖硬编码 `*.txt` 的本地脚本失效] → Mitigation：BREAKING 写入 proposal/user-guide；显式 `-o foo.txt` 仍可用。  
- [单测大量断言 `===` 首行失败] → Mitigation：集中改 `test/apps/test_formatters.py` 等；先改一处样板再批量。  
- [Markdown 特殊字符（如 `|`、`*`）破坏表格/强调] → Mitigation：本期继续用简单行文与列表，避免自动表格；数值行保持明文。  
- [dual 讲解变长后 `.md` 更大] → Mitigation：可接受；JSON 模式仍不附讲解正文。

## Migration Plan

1. 改 `_batch_output_path` 默认后缀 → 跑 watchlist 单测。  
2. 逐个升级 formatters + 对应断言。  
3. 更新 user-guide 示例。  
4. 本地用一只票目视预览 `.md`。  
5. 回滚：恢复后缀与 formatters 即可；无 DB 迁移。

## Open Questions

- 无阻塞项。若后续需要「兼容输出 `.txt` flag」，可另开 change；本期不做。
