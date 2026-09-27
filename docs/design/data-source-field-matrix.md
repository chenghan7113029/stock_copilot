# 数据源字段能力矩阵

> 阶段 B（`align-tushare-coverage`）真源文档。实现行为须与本表一致；变更请与代码同 PR。  
> 支持级别：`native`（接口直接产出）/ `derived`（由同源字段推导）/ `unsupported`（不写入对外结果）。

样本验收股：`600519`（茅台）— 价值面在 `tushare(1)+baostock(2)` 下，`industry` 与财报特例字段预期来自 **tushare native**。

## 价值面 / 财报（`FINANCIAL_STATEMENT_FIELDS`）

| 字段 | tushare | baostock | akshare |
|------|---------|----------|---------|
| revenue | native | **unsupported** | native |
| fcf | derived | **unsupported** | derived |
| capex | native | **unsupported** | native |
| net_debt | derived | **unsupported** | derived |
| ebit | native / derived | **unsupported** | native |
| depreciation | native | **unsupported** | native |
| total_assets | native | **unsupported** | native |
| total_liabilities | native | **unsupported** | native |
| bvps | native | **unsupported** | native |
| roic | derived | **unsupported** | derived |
| net_income | native | **unsupported** | native |

说明：Baostock 仍可读取季频接口做内部推导（如 growth_rate、historical_pe），但 **不得** 将上表字段写入 `FetchResult.data`。

## 其他价值面常用字段

| 字段 | tushare | baostock | akshare |
|------|---------|----------|---------|
| industry | native | unsupported | native |
| current_price | native | native | native |
| eps / roe | native | native | native |
| growth_rate | native / derived | derived | native |
| pe_ratio / pb_ratio | native | derived (historical_pe) | native |
| shares_outstanding | native | unsupported* | native |

\* Baostock 行情路径不保证流通股本；若配置注入则仅作内部辅助。

## K 线 / 实时

| 数据项 | tushare | baostock | akshare |
|--------|---------|----------|---------|
| 日 K OHLCV（前复权） | native (`pro_bar` qfq) | native | native |
| 盘中实时报价 | native (`rt_k`，需单独权限) | **unsupported**（不可作实时源） | native |
| 用 daily 冒充实时 | **禁止** | n/a | n/a |

## 筹码

| 数据项 | tushare | baostock | akshare |
|--------|---------|----------|---------|
| 筹码分布 / 胜率 | unsupported（`cyq_perf` 需 5000 分，阶段 B 文档化降级） | unsupported | native |

## 市场情绪

| 分量 | tushare | baostock | akshare |
|------|---------|----------|---------|
| 涨跌停家数 | derived（`daily` pct_chg **近似**，≠ `limit_list_d`） | unsupported | native |
| 涨跌家数 | derived（daily） | unsupported | native |
| 两融环比 | native（`margin`） | unsupported | native |
| 换手率分位 | unsupported（V1） | unsupported | native |

## 个股资金面（两融 + 主力资金流）

> 2000 积分档实测（2026-09-24，`scripts/verify_fundflow_tushare.py`，样本 `600519`）；均为 T+1 日度数据。  
> `margin_detail` 与 `moneyflow` 均须传 **`trade_date=最近交易日`**（或用 start/end 区间），否则非交易日可能返回空。

| 内部字段 | tushare 源字段 | 单位 | 说明 |
|----------|----------------|------|------|
| rzye | `margin_detail.rzye` | 元 | 融资余额 |
| rqye | `margin_detail.rqye` | 元 | 融券余额 |
| rzrqye | `margin_detail.rzrqye` | 元 | 融资融券余额（= `rzye + rqye`） |
| rzmre | `margin_detail.rzmre` | 元 | 融资买入额 |
| rzche | `margin_detail.rzche` | 元 | 融资偿还额 |
| rqyl | `margin_detail.rqyl` | 股 | 融券余量（数量，非金额） |
| rqmcl | `margin_detail.rqmcl` | 股 | 融券卖出量（数量，非金额） |
| net_mf_amount | `moneyflow.net_mf_amount` | 万元 | 主力净流入额 |
| buy_elg_amount | `moneyflow.buy_elg_amount` | 万元 | 特大单买入额 |
| sell_elg_amount | `moneyflow.sell_elg_amount` | 万元 | 特大单卖出额 |
| buy_lg_amount | `moneyflow.buy_lg_amount` | 万元 | 大单买入额 |
| sell_lg_amount | `moneyflow.sell_lg_amount` | 万元 | 大单卖出额 |

> 单位归一约定：`stock_margin_detail` 金额列为**元**、数量列为**股**；`stock_moneyflow` 金额列统一为**万元**。  
> 变化率为无量纲百分比；`main_net_inflow_5d` 为 `net_mf_amount` 近 5 交易日累计，单位为**万元**。  
> baostock / akshare 均 **unsupported**（本能力仅 tushare 路径，无 AKShare 兜底）。
