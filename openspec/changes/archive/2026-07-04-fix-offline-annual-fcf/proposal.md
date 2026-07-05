## Why

茅台 600519 离线估值中 FCF 被误用为 **263 亿**（2026 Q1 单季现金流），而 FY2025 年报正确值为 **584 亿**。根因是 `get_stock_data_offline()` 在同 source 多快照时仅按 `fetched_at` 取最新一条，较新的 Q1 sync 覆盖了较早但含正确年报 FCF 的快照。在线 `TushareFetcher` 已优先取 `1231` 年报，离线合并策略与之不一致，导致 DCF/EPV/owner_earnings 严重偏低。

## What Changes

- **离线合并分层选快照**：同 source 多 `report_period` 时，行情字段（`current_price` 等）仍取 `fetched_at` 最新；财报字段（`FINANCIAL_STATEMENT_FIELDS` 含 `fcf`）优先取 `report_period` 以 `1231` 结尾的最新年报快照。
- **字段级合并**：若同 source 存在多条快照，先合并最新行情快照，再合并最优年报快照的财报字段（允许 override）。
- **回归验证**：600519 离线 FCF ≈ 584 亿，DCF 公允价显著高于修复前 899 元。
- **测试**：新增/更新 `test_provider.py` 覆盖「Q1 快照 fetched_at 更新但年报 FCF 更大」场景。

## Capabilities

### New Capabilities

（无新增 capability，为现有 data provider 行为修正）

### Modified Capabilities

- `value-data-provider`：修订「离线快照按来源取最新 fetched_at」需求，明确财报字段优先年报、行情字段优先最新 fetched_at 的分层策略。

## Impact

- `src/data_provider/provider.py`：`get_stock_data_offline()` 离线合并逻辑
- `test/data_provider/test_provider.py`：新增年报优先合并测试
- `docs/mrd/features/value-analysis.md`：变更记录
- `scripts/verify_moutai_fcf.py`：可作为验收脚本引用
