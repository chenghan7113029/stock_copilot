## Why

`fix-baostock-data-quality`（层 A）通过 Baostock 数据内部推导，可将估值误差从 -188% 收窄到约 ±10-15%，PE Relative 单项可达 ±5%。但 Owner Earnings、DCF、EV/EBITDA 仍依赖估算值（capex 估算过高、net_debt 未纳入、revenue 用代理值），无法让所有估值方法均达到 ±5% 精度。本变更通过升级 Tushare token（或切换至兼容接口），接入利润表、现金流量表、资产负债表三张财务报表，补全 `capex`、`revenue`、`net_debt` 等关键字段，使全量估值方法均可用真实数据运行，目标是全方法 ±5% 对齐参考 LLM（Gemini）的估值结果。

**前置条件**：本 change 依赖 Tushare `income` / `cashflow` / `balancesheet` / `fina_indicator` 接口可用（需积分 120+ 或等效权限）。在决定实施前，建议先确认 token 权限。

## What Changes

- **Tushare `income` 接口接入**：获取年度/季度营业收入（`revenue`）、归母净利润（`net_income`）、营业利润（`ebit`）、利息费用（`interest_expense`），补全 EPV、EV/EBITDA、Beneish M-Score 所需数据。
- **Tushare `cashflow` 接口接入**：获取经营活动现金流（`n_cashflow_act`）、资本支出（`c_pay_acq_const_fiolta`）、折旧摊销（`depr_fa_cog_dp`），推导真实 FCF（`fcf = ocf - abs(capex)`），修复 Owner Earnings 和 DCF 过高的估算 capex 问题。
- **Tushare `balancesheet` 接口接入**：获取总资产（`total_assets`）、总负债（`total_liabilities`）、货币资金（`money_cap`）、各类流动/非流动资产负债，计算 `net_debt = total_debt - cash`（茅台等净现金股票直接纳入 EV/EBITDA 和 DCF 计算）。
- **Tushare `fina_indicator` 接口接入**：获取 `eps`、`bvps`（每股净资产）、`roe`、`roic`，补全 Piotroski F-Score、Beneish M-Score、PB Relative 所需字段。
- **SourceManager 数据源优先级调整**：Tushare 财报数据作为「补充源」，Baostock 作为「主源」，合并时 Tushare 的财报字段（revenue、capex、net_debt）覆盖 Baostock 的估算值。
- **FCF 计算统一**：`TushareFetcher._derive_fcf` 已实现（`ocf - abs(capex)`），确保其优先于 Baostock 的 operCashTTM 和 CFOToOR 推导链。

## Capabilities

### New Capabilities

- `tushare-income-data`: 接入 Tushare `income` 接口，获取年度 revenue、net_income、ebit、interest_expense。
- `tushare-cashflow-data`: 接入 Tushare `cashflow` 接口，获取 OCF、capex、depreciation，推导真实 FCF。
- `tushare-balance-data`: 接入 Tushare `balancesheet` 接口，获取 total_assets、total_liabilities、cash，计算 net_debt。
- `tushare-fina-indicator-data`: 接入 Tushare `fina_indicator` 接口，获取 bvps、roic 等高质量财务指标。
- `net-debt-calculation`: 从 total_debt（short_term_debt + long_term_debt）- cash_and_equivalents 计算 `net_debt`，补充 EV/EBITDA 和 DCF 企业价值桥梁。

### Modified Capabilities

（无现有 spec 级别的需求变更）

## Impact

**受影响模块**：
- `src/data_provider/tushare/fetcher.py` — 核心：激活 income / cashflow / balancesheet 查询（当前已实现但因权限失败而无数据）
- `src/data_provider/tushare/field_mapping.py` — 可能需要补充 `money_cap`（货币资金）→ `cash` 映射
- `src/data_provider/source_manager.py` — 确保合并优先级：Tushare 财报 > Baostock 估算
- `src/common/models/stock_data.py` — 确认 `net_debt`、`cash` 字段已定义
- `src/service/value/valuation/growth.py`（EVEBITDA）— net_debt 参与 EV = market_cap + net_debt 计算

**依赖**：
- 本 change 依赖 Tushare 积分升级（`income` 接口需 120 积分，`balancesheet` 需 120 积分，`cashflow` 需 120 积分）
- 或接入兼容的替代财报数据源（如 AKShare 财报接口，如恢复可用）

**预期效果**（在层 A 基础上，以茅台 600519 为基准）：
- Owner Earnings: ~1,300-1,500 元 → ~1,400-1,600 元（真实 capex ~30 亿，而非估算的 118 亿）
- EV/EBITDA: ~1,000-1,200 元 → ~1,200-1,400 元（含净现金 ~1,800 亿）
- DCF: ~1,100-1,300 元 → ~1,200-1,500 元（真实 FCF = OCF - real_capex）
- Piotroski F-Score: N/A → 可运行（需 total_assets、revenue）
- Beneish M-Score: N/A → 可运行（需 revenue、total_assets）
- 全方法聚合: ~1,150-1,450 元 → ~1,300-1,500 元，中位数 ~1,380 元
- vs Gemini 参考 1,340-1,474 元 → 全方法误差 ±5%
