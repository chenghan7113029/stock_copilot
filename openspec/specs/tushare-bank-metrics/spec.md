# tushare-bank-metrics Specification

## Purpose

Tushare 银行专项指标（净息差、不良率、拨备覆盖率）与 `stock_basic.industry` 的字段映射与缺失降级语义。

## Requirements

### Requirement: Tushare 提供银行专项指标（NIM、NPL、拨备覆盖率）
`TushareFetcher` SHALL 为银行原型股票拉取以下三个专项指标并写入 `FetchResult.data`：

| 字段 | Tushare 来源 | 说明 |
|---|---|---|
| `net_interest_margin` | `fina_indicator.netint_margin` | 净息差（%），银行核心盈利指标 |
| `npl_ratio` | `fina_indicator.npl_ratio` 或 `stk_fin_audit` | 不良贷款率（%），信用风险指标 |
| `provision_coverage` | `fina_indicator.prov_cov` | 拨备覆盖率（%），风险缓冲指标 |

若某字段 Tushare 接口未返回或无权限，标注 missing，不中断整体 fetch。

#### Scenario: 银行股正常拉取三大指标
- **WHEN** sync 601398，`fina_indicator` 返回含 `netint_margin`、`prov_cov` 字段
- **THEN** `StockData.net_interest_margin` 和 `StockData.provision_coverage` 不为 None，`field_sources["net_interest_margin"] = "tushare"`

#### Scenario: npl_ratio 无法获取时 missing 不报错
- **WHEN** `fina_indicator` 不含 `npl_ratio` 字段
- **THEN** `StockData.npl_ratio = None`，`missing_fields` 含 `npl_ratio`，整体流程不中断

#### Scenario: 非银行股 fina_indicator 无银行字段时 missing
- **WHEN** sync 600519（非银行），`fina_indicator` 不含银行专项列
- **THEN** `net_interest_margin`/`npl_ratio`/`provision_coverage` 为 None 并列入 missing，整体 fetch 不中断

### Requirement: Tushare stock_basic 提供 industry
`TushareFetcher.fetch_fundamentals()` SHALL 调用 `stock_basic` 并将 `name`、`industry` 写入 `FetchResult.data`（字符串字段，非数值缩放）。

#### Scenario: 601398 industry 写入
- **WHEN** `stock_basic` 返回 `industry="银行"`
- **THEN** `FetchResult.data["industry"] = "银行"`
