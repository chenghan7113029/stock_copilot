## 1. 落盘扩展名

- [x] 1.1 Modify `src/apps/cli.py`：`_batch_output_path` 默认 `{code}_{kind}.md`；更新相关 argparse help
- [x] 1.2 Modify `test/apps/test_cli_watchlist.py`（及同类断言）：期望后缀 `.md`

## 2. Formatters Markdown 化

- [x] 2.1 Modify `src/apps/formatters.py`：`format_tech_report` / `format_value_report` 标题与分节改为 Markdown
- [x] 2.2 Modify 同文件：`format_dual_report` / `format_summary_report` / `format_dashboard_report`
- [x] 2.3 Modify 同文件：`format_sentiment_report` / `format_entry_check_report` / `format_trade_review_report` / `format_portfolio_report` / `format_checklist_records`
- [x] 2.4 确认 `as_json=True` 路径零改动；讲解区块仍仅文本模式

## 3. 测试

- [x] 3.1 Modify `test/apps/test_formatters.py`：断言 `# ` / `## ` 与既有业务关键词；去掉对 `===` 首行的硬依赖
- [x] 3.2 修正其他因标题格式变更失败的 CLI/formatter 单测
- [x] 3.3 跑 `pytest test/apps/test_formatters.py test/apps/test_cli_watchlist.py -q` 及相关失败用例直至通过

## 4. 文档

- [x] 4.1 Modify `docs/user-guide.md`：示例路径与说明由 `.txt` 改为 `.md`（保留显式 `.txt` 仍可用的一句说明）
- [x] 4.2 Create `docs/design/report-markdown-output.md`（可由本 change design 精简）

## 5. 验收与归档

- [x] 5.1 对 watchlist 至少 1 只票生成 tech/value/dual/summary/dashboard 到临时目录，目视 `.md` 渲染
- [x] 5.2 `pytest test/ -q -m "not network"` 全量通过
- [x] 5.3 Archive：同步 specs 到 `openspec/specs/`，合并文档到 `docs/`
