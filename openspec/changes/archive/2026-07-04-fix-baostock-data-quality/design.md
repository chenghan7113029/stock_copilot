## Context

当前 `BaostockFetcher` 存在三个系统性数据质量问题，均已通过实验验证（见探索记录）：

1. **netProfit 语义混乱**：Baostock `query_profit_data` 返回累计值（Q1=单季, Q2=H1累计, Q3=Q1-Q3累计, Q4=全年），但代码通过 `_recent_quarters` 取最近完整季度（通常为 Q1 或 Q2），导致 `net_income` 被低估 3-4 倍。
2. **历史 PE 无法从 K 线取**：`query_history_k_data_plus` 的 `peTTM` 字段不可用（error 10004012），所有 PE/PB 历史字段均报错。需要自行从价格 + `epsTTM` 计算。
3. **`operCashTTM` 对特定标的为 None**：实验中茅台（600519）4 个季度均返回 None，可能因金融子公司特殊会计处理影响 TTM 计算。`CFOToOR`（现金流/营收比率）有稳定数据，可用于反推。

约束条件：
- AKShare 基本不可用（quote 接口频繁报错）
- Tushare `income` / `cashflow` / `balancesheet` / `fina_indicator` 均无权限（当前 token）
- 变更范围限定在 `src/data_provider/baostock/` 和 `src/service/value/aggregator.py`

## Goals / Non-Goals

**Goals:**
- 修复 `net_income` 为 TTM 年度级别数据
- 让 `pe_relative` 方法在 Baostock 纯数据下能运行（需 `historical_pe`）
- 建立 FCF 推导链，使 DCF 方法对主流 A 股标的均可运行
- 修复 `growth_rate` 为 2 年 CAGR，改善 Graham/Owner Earnings 准确性
- Aggregator 在核心方法均 N/A 时输出「不可信」标注，而非误导性窄区间
- 茅台 PE Relative 估值误差控制在 ±5% 内

**Non-Goals:**
- 不接入 Tushare 财报接口（这是层 B 的范畴）
- 不引入新的数据源依赖
- 不修改估值方法（DCF/Graham/OwnerEarnings）的核心逻辑
- 不处理北交所（Baostock 本就不支持）
- 不实现 multi-year 滚动平均 OCF（过于复杂，留给层 B）

## Decisions

### 决策 1：net_income TTM 使用 `epsTTM × shares` 而非 Q4 年度值

**方案 A（选用）**：`net_income_ttm = epsTTM × shares_outstanding`
- 优点：epsTTM 已有（稳定、准确），shares 已有，一行推导，无需额外 API 调用
- 缺点：epsTTM 包含所有股份（包括回购未注销部分），精度差异极小（<0.5%）

**方案 B**：显式查询 Q4 数据取全年累计值
- 优点：语义直接
- 缺点：需要额外季度判断逻辑，且 Q4 全年值（893.35 亿）vs 年报（862.28 亿）有 ~3% 误差（归母 vs 合并口径差异）

**选用方案 A**：精度更高，代码更简洁。在 `_fetch_profit_in_session` 中，取到 `epsTTM` 和 `shares_outstanding` 后，写入 `net_income = epsTTM × shares`（单位换算为元）。

---

### 决策 2：historical_pe 从「季末收盘价 ÷ epsTTM」计算

**方案（唯一可行）**：在 `_session` 内：
1. 用 `query_history_k_data_plus` 取过去 2 年日线数据（`date,close`）
2. 取每个季末（3/31, 6/30, 9/30, 12/31）最近一个交易日的收盘价
3. 同期 `epsTTM` 从 `query_profit_data` 各季度获取（已有季度回溯逻辑）
4. `pe = price / epsTTM`，过滤负值和极值（> 200），取均值

数据结构：
```
historical_pe_data = {
    "2024Q1": (price_q1_2024, eps_ttm_2024q1),
    "2024Q2": (price_q2_2024, eps_ttm_2024q2),
    ...
}
→ historical_pe: list[float]  # 8个季度PE值
```

API 调用成本：1次额外 K 线查询（已在 session 内，无额外 login/logout）。

---

### 决策 3：FCF 推导链实现

```
优先级：
  1. operCashTTM（有值且 > 0 → 直接用）
  2. CFOToOR × revenue
     - CFOToOR 来自 query_cash_flow_data（实测稳定）
     - revenue 来自 MBRevenue（季度，需乘以季度系数）或配置中的 revenue 字段
     → 建议用 TTM revenue（epsTTM / (net_income_margin) 可估算；或用 annualized MBRevenue×4）
  3. net_income × fcf_rate（config: value_analysis.fcf_rate，默认 0.85，白酒行业适用）
```

实现位置：`BaostockFetcher._derive_fcf_in_session()`，在 `_fetch_cashflow_in_session` 之后调用。

`fcf_rate` 写入 `config/app.yaml`：
```yaml
value_analysis:
  fcf_rate: 0.85  # FCF/净利润 比率 fallback，白酒行业参考值
```

---

### 决策 4：growth_rate 使用 2 年净利 CAGR

当前实现直接取 `YOYNI`（单季净利润同比）。改为：
1. 取最近 Q4（全年 netProfit，或用 epsTTM×shares 计算的 TTM）
2. 取 2 年前 Q4（同样方式）
3. `growth_rate = (TTM_now / TTM_2y_ago)^0.5 - 1`

实现：在 `_fetch_growth_in_session` 中，额外查询 `(year-2, 4)` 的 `epsTTM`，与当前 TTM 比较。

**边界处理**：CAGR < -50% 或 CAGR > 100% 时 clamp 到合理范围，并写入 warning。

---

### 决策 5：Aggregator 锚定方法检测

在 `ValuationAggregator.aggregate()` 中增加：

```python
PRIMARY_METHODS = {
    "value_growth": frozenset({"dcf", "pe_relative"}),
    "bank": frozenset({"pb_relative", "residual_income"}),
    "high_dividend": frozenset({"ddm", "two_stage_ddm"}),
}

# 检查：若 primary methods 全部为 N/A
primary_na_count = sum(
    1 for k, r in results.items()
    if k in primary_for_prototype and r.applicability == "Not Applicable"
)
if primary_na_count == len(primary_for_prototype):
    confidence = "不可信"
    warnings.insert(0, "⚠ 核心估值方法（DCF、历史PE）均因数据不足未运行，当前区间参考意义有限")
```

需要 `aggregate()` 接收 `prototype` 参数（当前不接收），或从 `results` 的 key 集合推断。

## Risks / Trade-offs

**[Risk 1] epsTTM 季度数据延迟** → Baostock 财务数据有约 1 个月的披露延迟，季末可能取不到最新 epsTTM。已有 `_recent_quarters` 回溯逻辑可覆盖。

**[Risk 2] 季末收盘价与 epsTTM 时间点不完全对齐** → 季末 K 线价格与该季度 epsTTM 是同期的合理近似，但 epsTTM 包含追溯修正，轻微偏差可接受（PE 估算误差 < 3%）。

**[Risk 3] CFOToOR 反推 FCF 精度** → `CFOToOR` 是现金流/营收比，反推需要 revenue。若 revenue 也为 None（如茅台 MBRevenue 有时返回空），则退化到方案 3（net_income × fcf_rate）。fcf_rate 默认 0.85 是白酒行业经验值，对其他行业可能不准，但这是最后 fallback，已有「数据估算」警告。

**[Risk 4] growth_rate CAGR 使用 2 年窗口可能受单年异常影响** → 茅台 2025 年利润同比下降 4.53%，CAGR 为 ~5%，比市场对未来增速预期略保守（市场预期 8-12%）。可后续在 config 中允许用户覆盖 growth_rate。

**[Trade-off] historical_pe 计算增加 1 次额外 K 线查询** → 每次 sync 增加约 1-2 秒 API 时间，在单次 session 内完成，不新增 login/logout 次数。

**[Trade-off] Aggregator 加入 prototype 参数** → `aggregate()` 当前是纯数据方法，加入 prototype 使其与业务逻辑耦合。替代方案：results dict key 已隐含原型信息，可通过 key 集合推断（若含 dcf 且含 pe_relative，则为 value_growth 原型）。选用后者避免接口变更。
