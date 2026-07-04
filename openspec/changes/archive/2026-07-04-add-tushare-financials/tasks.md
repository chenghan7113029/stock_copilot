## 0. 前置：验证 Tushare 权限

- [x] 0.1 确认 Tushare token 升级至支持 `income` / `cashflow` / `balancesheet` / `fina_indicator` 接口（积分 ≥ 120）
- [x] 0.2 运行验证脚本确认四个接口均可调用并返回 600519 数据

> **权限**：需 Tushare 积分 ≥2000（`income`/`cashflow`/`balancesheet`/`fina_indicator`）。验证脚本：`scripts/verify_tushare_financials.py`

## 1. StockData 模型补充

- [x] 1.1 检查 `src/common/models/stock_data.py`：确认 `net_debt`、`cash` 字段是否已定义；若无 `cash` 字段，新增 `cash: Optional[float] = None`

## 2. Tushare field_mapping 补充

- [x] 2.1 修改 `src/data_provider/tushare/field_mapping.py`：在 `BALANCE_SHEET_FIELD_MAP` 中新增 `"money_cap": "cash"` 映射

## 3. Tushare fetcher 补充 _derive_net_debt

- [x] 3.1 在 `src/data_provider/tushare/fetcher.py` 中新增静态方法 `_derive_net_debt(data)`：计算 `net_debt = short_term_debt + long_term_debt - cash`（支持 None 处理）
- [x] 3.2 在 `fetch_fundamentals` 末尾调用 `_derive_net_debt(data)`
- [x] 3.3 新增测试 `test/data_provider/test_tushare_fetcher.py`：`test_derive_net_debt_positive`（有债）和 `test_derive_net_debt_negative`（净现金如茅台）

## 4. Tushare income 年报优先逻辑

- [x] 4.1 修改 `TushareFetcher._fetch_latest` 方法：对 `income` 接口增加「优先取年报（end_date 以 1231 结尾）」逻辑
- [x] 4.2 新增测试：`test_income_prefers_annual_report`，验证有年报时不取季报

## 5. SourceManager 财报字段覆盖策略

- [x] 5.1 检查 `src/data_provider/source_manager.py`（或 provider.py）的多源合并逻辑
- [x] 5.2 确保执行顺序：Baostock 先运行（写入行情 + 基础财务），Tushare 后运行（写入财报字段）
- [x] 5.3 对 `FINANCIAL_STATEMENT_FIELDS = {"revenue", "fcf", "capex", "net_debt", "ebit", "depreciation", "total_assets", "total_liabilities", "bvps", "roic"}` 这些字段，Tushare 的非 None 值覆盖 Baostock 的估算值
- [x] 5.4 新增测试：`test_tushare_financials_override_baostock_estimates`，验证 Tushare revenue 覆盖 Baostock 估算的 revenue

## 6. EV/EBITDA 验证 net_debt 参与计算

- [x] 6.1 检查 `src/service/value/valuation/growth.py` 的 `EVEBITDA.calculate()`：确认 `net_debt` 从 `stock.net_debt` 读取，且负值（净现金）使 equity_value 增大
- [x] 6.2 手工验算：茅台 EBITDA ≈ 1,237 亿，fair_ev = 1,237 × 12 = 14,844 亿，net_debt = -1,800 亿（净现金），equity = 16,644 亿，per_share ≈ 1,330 元

## 7. 端到端验证

- [x] 7.1 重新同步茅台数据（`py -m apps.cli sync 600519`）
- [x] 7.2 生成价值报告，验证以下字段有真实数据：`revenue`（~1,688 亿）、`fcf`（~590 亿）、`net_debt`（< 0，净现金）、`total_assets`（~3,038 亿）
- [x] 7.3 验证 Piotroski F-Score 可运行（之前因 total_assets 为 None 而 N/A）
- [x] 7.4 验证 EV/EBITDA 公允价 ≥ 1,200 元（含净现金调整）
- [ ] 7.5 验证全方法聚合中位数 ≥ 1,300 元，与 Gemini 参考值 1,340-1,474 误差 ≤ ±5%

> **7.5 实测（2026-07-04，Tushare 2000 积分 + 离线快照修复后）**
>
> | 指标 | 实测 | 目标 | 结果 |
> |------|------|------|------|
> | revenue | 1,688 亿 | ~1,688 亿 | ✅ |
> | fcf | 584 亿 | ~590 亿 | ✅ |
> | net_debt | -517 亿 | < 0 | ✅ |
> | total_assets | 3,038 亿 | ~3,038 亿 | ✅ |
> | pe_relative | 1,440 | 1,340–1,474 | ✅ |
> | ev_ebitda | 1,628 | ≥ 1,200 | ✅ |
> | 聚合中位 | 838 | ≥ 1,300 | ❌（DCF/EPV/Graham 仍偏低，属估值假设层，非数据缺口） |

## 8. 归档文档

- [x] 8.1 更新 `docs/mrd/roadmap-todo.md`：将「Tushare 财报接入」标记为已完成
- [x] 8.2 合并本 change 的 proposal/design 到相关 mrd 和 design 文档
