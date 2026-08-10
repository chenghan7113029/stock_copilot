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
