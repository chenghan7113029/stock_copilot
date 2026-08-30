# Tushare 接口权限扫描 — 2000 积分档

> 最后更新：2026-08-29  
> 用途：记录 Owner **2000 积分** Token 下的接口权限、项目已用/未用对照，以及 Roadmap 接入建议。  
> 复测脚本：`scripts/scan_tushare_permissions.py`  
> 相关文档：[features/data-source-migration.md](features/data-source-migration.md) §5.B.3、[design/data-source-field-matrix.md](../design/data-source-field-matrix.md)

## 变更记录

| 日期 | 摘要 |
|------|------|
| 2026-08-29 | 初稿：本地 Token 实测 + 官方积分档对照；新增 `scan_tushare_permissions.py` |

---

## 1. 扫描说明

| 项 | 内容 |
|----|------|
| 积分档位 | **2000**（约 200 元/年档） |
| 扫描日期 | 2026-08-29（周六，非交易日） |
| 探测基准日 | 最近交易日 **20260828**（市场类接口须用交易日，不能用扫描日当天） |
| Token 来源 | `config/app.yaml`（不入库） |
| 官方权限表 | [doc_id=108](https://tushare.pro/document/1?doc_id=108) |
| 频次上限 | [doc_id=290](https://tushare.pro/document/1?doc_id=290)：200 次/分钟、10 万次/日/API |

**结论摘要：**

- 项目已调用 **12** 个接口，其中 **11** 个可用；**`rt_k` 无权限**（单独月费，非 2000 分自带）。
- 2000 分档下另有 **大量接口可用但项目未接入**，与 PO-11～PO-13 高度相关。
- **`cyq_perf`（筹码）、`fund_portfolio`（基金持仓）** 需 5000+；筹码继续依赖 AKShare `stock_cyq_em`。

---

## 2. 2000 积分档通用规则

| 档位 | 每分钟 | 每 API 日上限 | 说明 |
|------|--------|---------------|------|
| 120 | 50 | 8000 | 仅非复权 `daily` 等极少数 |
| **2000** | **200** | **10 万/API** | 常规行情、财报、龙虎榜、两融等（见 §4） |
| 5000+ | 500 | 常规无上限 | 筹码、基金持仓等 |
| 10000+ | 500 | 含特色数据 | 盈利预测、券商金股等 |

积分是**权限门槛**，正常调用不消耗积分。

---

## 3. 项目已使用的接口

| API | 最低分 | 代码位置 | 用途 | 实测 |
|-----|--------|----------|------|------|
| `stock_basic` | 120+ | `tushare/fetcher.py`、`config_loader.verify_tushare_access` | 行业、名称、Token 探测 | ✅ |
| `daily` | 120+ | `fetcher.py`、`sentiment/tushare_sentiment_fetcher.py` | 最新价；全市场 `pct_chg` 近似涨跌停 | ✅ |
| `daily_basic` | 2000 | `fetcher.py` | PE/PB/市值；5 年季末 `historical_pe/pb` | ✅ |
| `pro_bar` | 2000 | `fetcher.fetch_kline` | 前复权日 K | ✅ |
| `rt_k` | **单独月费** | `fetcher.fetch_realtime_quote` | 盘中实时 OHLCV | ❌ 无权限 |
| `income` | 2000 | `fetcher.fetch_fundamentals` | 利润表 | ✅ |
| `balancesheet` | 2000 | 同上 | 资产负债表 | ✅ |
| `cashflow` | 2000 | 同上 | 现金流；FCF 推导 | ✅ |
| `fina_indicator` | 2000 | 同上 | 财务指标；银行 NIM/NPL 等 | ✅ |
| `dividend` | 2000 | 同上 | 分红 | ✅ |
| `margin` | 2000 | `sentiment/tushare_sentiment_fetcher.py` | 两融余额环比（沪深合计） | ✅ |
| `trade_cal` | 2000 | 同上 | 最近交易日 | ✅ |

**未走 Tushare 的相邻能力：**

| 能力 | 当前实现 | 原因 |
|------|----------|------|
| 筹码分布 | AKShare `stock_cyq_em` | `cyq_perf` 需 5000 分（实测 ❌） |
| 精确涨跌停名单 | `daily` 9.5% 阈值近似 | `limit_list_d` 权限不足（实测 ❌） |
| 实时行情 | EOD 降级 + 警告 | `rt_k` 未开通月费 |

---

## 4. 2000 分可用 · 项目未使用（实测 ✅）

> 市场级接口（龙虎榜、两融明细等）须传 **trade_date=最近交易日**，否则易误判为「无权限」。

### 4.1 与 Roadmap 直接相关（建议优先）

| API | 官方最低分 | 可支撑能力 | Roadmap |
|-----|------------|------------|---------|
| `top_list` | 2000 | 龙虎榜每日明细 | PO-13 |
| `top_inst` | 2000 | 龙虎榜机构席位 | PO-13 |
| `margin_detail` | 2000 | 个股两融明细 | PO-12 |
| `moneyflow` | 2000 | 个股主力资金流 | PO-12 |
| `moneyflow_hsgt` | 2000 | 沪深港通北向资金 | PO-11 流动性 |
| `share_float` | 文档 3000；**实测 2000 可用** | 限售股解禁 | PO-11 治理 |
| `stk_holdertrade` | 2000 | 股东增减持 | PO-11 |
| `stk_holdernumber` | 2000 | 股东人数 | 价值/情绪辅助 |
| `block_trade` | 2000 | 大宗交易 | PO-11 |
| `pledge_detail` / `pledge_stat` | 2000 | 股权质押 | PO-11 |
| `repurchase` | 2000 | 股票回购 | PO-11 |
| `hk_hold` | 2000 | 沪深股通持股明细 | PO-11 |
| `stk_limit` | 2000 | 每日涨跌停价格 | 情绪面精确化 |

### 4.2 价值面 / 技术面 / 宏观增强

| API | 官方最低分 | 可支撑能力 |
|-----|------------|------------|
| `forecast` | 2000 | 业绩预告 |
| `express` | 2000 | 业绩快报 |
| `fina_mainbz` | 2000 | 主营业务构成 |
| `fina_audit` | 2000 | 财务审计意见 |
| `disclosure_date` | 2000 | 财报披露计划 |
| `weekly` | 2000 | 周线行情 |
| `monthly` | 2000 | 月线行情（MRD 已决策不做月 K 产品入口） |
| `index_daily` | 2000 | 指数日线（如沪深 300 基准） |
| `index_classify` | 2000 | 申万行业分类（可补强 T-7 行业→原型） |
| `index_member_all` | 2000 | 申万行业成分 |
| `index_dailybasic` | 文档 4000；**实测 2000 可用** | 大盘指数每日指标 |

---

## 5. 2000 分仍不可用（实测 ❌）

| API | 原因 | 对项目影响 |
|-----|------|------------|
| **`rt_k`** | 单独月费（约 200 元/月，见 [doc_id=372](https://tushare.pro/document/2?doc_id=372)） | `sync --realtime` 永久 EOD 降级 |
| **`cyq_perf`** | 需 **5000** 分 | Tushare 筹码不可用；维持 AKShare |
| **`fund_portfolio`** | 需 **5000** 分 | 基金持仓数据不可用 |
| **`limit_list_d`** | 权限不足（特色/更高档） | 无法用精确涨跌停名单 |
| **`ths_index`** | 权限不足 | 同花顺概念不可用；可用申万 `index_classify` |

---

## 6. 权限域示意

```text
2000 积分权限域
├── ✅ 已用（11/12 可用）
│   ├── 行情: daily, daily_basic, pro_bar
│   ├── 财报: income / balancesheet / cashflow / fina_indicator / dividend
│   ├── 基础: stock_basic, trade_cal
│   ├── 情绪: margin
│   └── ❌ rt_k（月费另开）
│
├── 🔓 可用未用（Roadmap 优先）
│   ├── PO-11~13: top_list, moneyflow, share_float, stk_holdertrade …
│   └── 增强: forecast, index_daily, weekly …
│
└── 🔒 不可用
    ├── rt_k（月费）
    ├── cyq_perf, fund_portfolio（5000+）
    └── limit_list_d, ths_index（更高档）
```

---

## 7. 接入建议（ROI 排序）

| 排序 | 动作 | 成本 | 映射 |
|------|------|------|------|
| 1 | 接入 `top_list` + `moneyflow` + `share_float` + `stk_holdertrade` | 无额外积分 | PO-11～PO-13 |
| 2 | 情绪面用 `stk_limit` 替代 `daily` 9.5% 近似（或保留近似作 fallback） | 无 | PO-06 增强 |
| 3 | 评估是否开通 **`rt_k` 月费** | ~200 元/月 | 实时 overlay |
| 4 | 筹码：冲 **5000** 接 `cyq_perf`，或继续 **AKShare** | 积分/依赖 | F-17 |
| 5 | 行业映射：用 `index_classify` / `index_member_all` 标准化 T-7 | 无 | T-7 演进 |

---

## 8. 复测方法

```powershell
# 完整扫描（已用 / 未用 / 高档对照）
python scripts/scan_tushare_permissions.py

# 仅验证四表财报权限
python scripts/verify_tushare_financials.py 600519
```

**注意：**

- 扫描脚本对 `top_list` 等仍用「当日」参数时，非交易日可能显示 `FAIL(no rows)`；以 §1 基准日手动复测为准。
- Token 变更或积分升级后应重新扫描并更新本文档「变更记录」。

---

## 9. 相关文档

| 文档 | 说明 |
|------|------|
| [features/data-source-migration.md](features/data-source-migration.md) | 数据源三阶段；§5.B.3 Tushare 积分说明 |
| [design/data-source-field-matrix.md](../design/data-source-field-matrix.md) | 字段能力矩阵（rt_k、cyq、情绪近似） |
| [features/value-analysis.md](features/value-analysis.md) | 财报接口 ≥2000 积分要求 |
| [roadmap-todo.md](roadmap-todo.md) | PO-11～PO-14 待办 |
| [competitive-reference.md](competitive-reference.md) | 外部项目 Feature 参考（龙虎榜/解禁等 Agent 角色） |
