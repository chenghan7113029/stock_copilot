## 1. 离线合并：分层选快照

- [x] 1.1 修改 `src/data_provider/provider.py` 的 `get_stock_data_offline()`：
  - 按 source 分组全部快照（不再只保留 fetched_at 最新一条）
  - 行情快照 = `max(snaps, key=fetched_at)`，合并非 `FINANCIAL_STATEMENT_FIELDS` 字段
  - 财报快照 = 在 `report_period.endswith("1231")` 中取 `max(report_period)`；无年报则 fallback 到行情快照
  - 财报快照的 `FINANCIAL_STATEMENT_FIELDS` 通过 `override_field` 合并
- [x] 1.2 抽取私有辅助方法（如 `_pick_quote_snapshot`、`_pick_financial_snapshot`）保持 `get_stock_data_offline` 可读

## 2. 测试

- [x] 2.1 修改 `test/data_provider/test_provider.py`：
  - 新增 `test_offline_financials_prefer_annual_over_newer_quarterly`：同 source 下 Q1 快照 fetched_at 更新但年报 FCF 更大，合并后 fcf 应为年报值
  - 更新 `test_get_stock_data_offline_picks_latest_fetched_per_source` 若行为变化，确保行情仍取最新 fetched_at
- [x] 2.2 运行 `py -m pytest test/data_provider/test_provider.py -q`

## 3. 集成验证

- [x] 3.1 运行 `py scripts/verify_moutai_fcf.py`，确认离线合并后 FCF ≈ 584 亿
- [x] 3.2 运行 `py -m apps.cli report value 600519`，确认：
  - `fcf` 对应 DCF 输入基数提升（DCF 公允价 > 1200 元，粗估）
  - 聚合中位向 LLM 参考区间进一步靠拢

## 4. 文档

- [x] 4.1 更新 `docs/mrd/features/value-analysis.md` 变更记录新增 `fix-offline-annual-fcf`
- [x] 4.2 更新 `docs/mrd/roadmap-todo.md` 补充 FCF 263→584 根因与修复说明
