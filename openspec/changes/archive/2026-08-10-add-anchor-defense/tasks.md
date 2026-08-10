## 1. 分位定性分档映射

- [x] 1.1 新建 `src/service/value/anchor.py`：`percentile_band(price_percentile: float) -> str`，5 档映射（低位/中低位/中性/中高位/高位），固定边界归属规则
- [x] 1.2 单测 `test/service/value/test_anchor.py`：覆盖 5 个分档区间的代表值与边界值（20/40/60/80）

## 2. 历史最高价计算（默认隐藏）

- [x] 2.1 `src/service/value/anchor.py` 新增 `historical_high(code: str, kline_repo: KlineRepo) -> tuple[float, int] | None`：从本地 `Kline` 表读取全部可得记录，计算最大 `close`/`high` 与记录条数（数据窗口天数）
- [x] 2.2 单测 `test/service/value/test_anchor.py`：覆盖有缓存/无缓存两种场景，验证纯离线（不触发任何网络调用）

## 3. CLI 呈现层改造

- [x] 3.1 `src/apps/cli.py`：`report value` 子命令新增 `--show-anchor-price` flag（默认 `False`）
- [x] 3.2 `src/apps/formatters.py`：`format_value_report()` 调整价格分位呈现逻辑——文本模式改为"定性分档（数值）"格式；`--json` 模式 `price_percentile` 原始数值字段保持不变
- [x] 3.3 `src/apps/formatters.py`：新增历史最高价展示分支，仅当 `show_anchor_price=True` 时输出，附带数据窗口说明与固定警示文案
- [x] 3.4 `src/apps/cli.py`：`run_report_value()` 透传 `--show-anchor-price` 到 formatter，需要时调用 `historical_high()`（离线，从已注入的 `KlineRepo` 读取）

## 4. 测试更新

- [x] 4.1 更新 `test/apps/test_formatters.py`：调整 `format_value_report` 既有断言以匹配新文本格式；新增 `--show-anchor-price` 相关测试用例
- [x] 4.2 更新 `test/apps/test_cli_report.py`：新增 `--show-anchor-price` flag 的 CLI 集成测试（默认关闭时不展示、显式开启时展示）
- [x] 4.3 检索仓库内是否存在对 `report value` 文本输出做正则解析的下游脚本；若存在则同步更新，若不存在则在 PR 描述中记录已确认无影响

## 5. 端到端验证

- [x] 5.1 运行 `python -m apps.cli report value 600519`，人工核对默认输出不含历史最高价、价格分位以定性分档为主呈现
- [x] 5.2 运行 `python -m apps.cli report value 600519 --show-anchor-price`，核对历史最高价数值、数据窗口说明、警示文案均正确展示
- [x] 5.3 运行 `python -m apps.cli report value 600519 --json`，核对 `price_percentile` 原始数值字段未被本 change 影响
- [x] 5.4 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 6. 文档

- [x] 6.1 更新 `docs/mrd/product-overview.md` §5.2/§7：PO-07 状态更新为「V1 已实现：分位定性分档呈现 + 历史最高价默认隐藏（opt-in 展示）；成本价隐藏留给 add-fresh-entry-check 复用本 change 护栏惯例」
- [x] 6.2 更新 `docs/mrd/roadmap-todo.md`：新增变更记录，PO-07 状态更新
- [x] 6.3 若判断内容量级足够，新建 `docs/design/anchor-defense-presentation.md` 沉淀"默认隐藏 + opt-in + 固定警示文案"呈现护栏模式，供未来 `add-fresh-entry-check` 等 change 参考复用；否则在本任务中说明为何判断不需要独立文档

## 7. 归档

- [x] 7.1 确认 `tasks.md` 全部任务完成（归档任务 7.2 按用户要求跳过）
- [ ] 7.2 运行 `openspec archive add-anchor-defense`（或 `/opsx-archive`），同步 specs 到 `openspec/specs/`
