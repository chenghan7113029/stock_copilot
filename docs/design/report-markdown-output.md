# 报告 Markdown 输出

> 来源：`openspec/changes/switch-reports-to-markdown`  
> 状态：已实现（默认落盘 `.md` + formatters Markdown 结构）

## 摘要

CLI 人类可读报告（tech / value / dual / summary / dashboard 等）默认以 **Markdown** 落盘与打印：批量 `-o <目录>` 写入 `{code}_{kind}.md`；正文使用 `#` / `##` 标题与列表，便于 IDE / 预览器阅读。`--json` 契约不变。

## 约定

- 默认扩展名：`.md`；显式 `.txt` / `.json` / `.md` 路径优先。
- `--json` 批量落盘：`.json`。
- stdout 与文件共用同一套 Markdown 字符串。
- 不批量迁移历史 `reports/*.txt`。

## 主要改动点

- `src/apps/cli.py`：`_batch_output_path`
- `src/apps/formatters.py`：各 `format_*_report`
- `src/service/report/explainers.py`：讲解分节标题
