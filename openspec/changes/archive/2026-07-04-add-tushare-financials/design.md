## Context

`TushareFetcher` 的 `fetch_fundamentals` 已经实现了 income / cashflow / balancesheet / fina_indicator 的查询逻辑（`src/data_provider/tushare/fetcher.py`），并有完整的 field_mapping。实测显示这些接口全部返回「无权限」错误，原因是当前 token 积分不足（需 120+ 积分）。

技术层面，`TushareFetcher._derive_fcf` 已经实现了 `fcf = n_cashflow_act - abs(capex)` 的正确推导。`SourceManager` 也已经有多源合并逻辑（`_merge_fields`）。层 B 的核心工作量是：
1. **验证 token 权限**（前置）
2. **补充缺失字段映射**（`money_cap` → `cash`，`net_debt` 推导）
3. **确保 net_debt 参与估值计算**（EV/EBITDA、DCF 的企业价值桥梁）
4. **测试覆盖**（多源合并路径）

已知约束：Tushare 财报接口每分钟请求频率有限制（通常 200次/分钟），当前 daily_basic / dividend 接口有 1次/小时 的限制提示（但 income 等 120 积分接口通常限制更宽松）。

## Goals / Non-Goals

**Goals:**
- 让 Tushare 财报接口在有权限时自动被 SourceManager 调用并补全关键字段
- `net_debt` 字段正确填充并参与 EV/EBITDA 和 DCF 计算
- 茅台等净现金公司的估值结果包含净现金溢价
- 全方法估值误差达到 ±5%（在层 A 基础上）
- 与层 A 无侵入式兼容：层 A 优先，层 B 字段覆盖层 A 的估算值

**Non-Goals:**
- 不引入新的数据源
- 不修改 Tushare token（由用户自行升级）
- 不处理 Tushare 接口限流降级（超出本 change 范围）
- 不修改估值方法核心逻辑（仅补数据）

## Decisions

### 决策 1：net_debt 计算方式

**方案 A（选用）**：从 balancesheet 提取  
`total_debt = short_term_debt + long_term_debt`  
`cash_and_equiv = money_cap`（货币资金，Tushare 字段 `money_cap`）  
`net_debt = total_debt - cash_and_equiv`  
负值（净现金状态）正常使用，不 clamp 为 0。

**方案 B**：从 fina_indicator 取 `debt_to_assets × total_assets - total_equity`  
缺点：多步推导，误差累积，且 fina_indicator 的 `debt_to_assets` 是总负债/总资产，包含经营性负债（应付账款等），会高估金融债务。

**选用方案 A**：语义准确，字段可直接映射。

新增 `tushare/field_mapping.py` 中的 balancesheet 映射：
```python
"money_cap": "cash",        # 货币资金
"st_borr": "short_term_debt",  # 短期借款（已有）
"lt_borr": "long_term_debt",   # 长期借款（已有）
```

在 `TushareFetcher._derive_net_debt(data)` 中：
```python
def _derive_net_debt(data):
    cash = data.get("cash")
    st_debt = data.get("short_term_debt", 0) or 0
    lt_debt = data.get("long_term_debt", 0) or 0
    if cash is not None:
        data["net_debt"] = st_debt + lt_debt - cash
```

---

### 决策 2：Tushare 财报数据覆盖 Baostock 估算值的策略

层 A 中 FCF 和 revenue 可能是估算值（带 warning）。层 B Tushare 提供真实值时应覆盖。

当前 `SourceManager._merge_fields` 逻辑：先到先得，已有值不覆盖。

**问题**：若 Baostock 先运行并写入 `fcf`（层 A 的 CFOToOR 推导值），Tushare 的真实 FCF 无法覆盖。

**修复**：在 SourceManager 合并逻辑中，增加「Tushare 财报字段强制覆盖」规则：对 `fcf`、`revenue`、`capex`、`net_debt`、`ebit`、`depreciation` 这些可能来自估算的字段，若 Tushare 提供了实测值（非估算），则覆盖 Baostock 的估算值。

实现方式：在 `FetchResult` 中增加 `estimated_fields: set[str]` 标记，合并时对非估算的 Tushare 字段强制覆盖。

**替代方案（简单版）**：调整执行顺序，Baostock 先运行（行情 + 季频财务），Tushare 后运行（财报补充），后运行者覆盖前者的财报字段。风险：Tushare 行情字段（price）可能覆盖 Baostock 的更新行情。需在 field_mapping 层面区分「行情字段」和「财报字段」。

**选用简单版 + 字段分类**：行情字段（`current_price`, `pe_ratio`, `pb_ratio`）以 Baostock 为准；财报字段（`revenue`, `fcf`, `capex`, `net_debt` 等）以 Tushare 为准（若有）。

---

### 决策 3：net_debt 字段在 StockData 中的定义

检查 `src/common/models/stock_data.py`：确认 `net_debt`、`cash` 字段是否已定义。若未定义，本 change 新增这两个字段。`cash` 是中间字段（用于计算 net_debt），可标记为 `_cash`（内部）。

## Risks / Trade-offs

**[Risk 1] Tushare 积分升级需要费用** → 这是用户决策，非技术风险。建议先升级至「基础版」（120 积分，约 CNY 120/年），覆盖 income / cashflow / balancesheet / fina_indicator。

**[Risk 2] Tushare 财报数据为季度数据还是年度数据** → `income(ts_code, limit=8)` 返回最近 8 期报告期数据，按 `end_date` 降序排列，取第一条即为最近一期（可能是季报或年报）。若最近一期是 Q1/Q2/Q3 季报，revenue 会比年报值低。建议：同时取 `end_date` 以 12 月底结尾的最新年报数据，用年报 revenue 而非季报。需在 `_fetch_latest` 中增加「优先取年报（Q4）」逻辑。

**[Risk 3] money_cap（货币资金）不等于真实可用现金** → 茅台的 money_cap 包含金融子公司吸收的存款，实际可用现金更少。这会高估净现金，进而高估股权价值。短期接受这个近似（误差范围可控），长期可接入更细粒度的现金科目。

**[Trade-off] 层 B 强依赖外部权限** → 若 Tushare 积分不升级，层 B 无法生效，但层 A 仍独立工作。设计上两层完全解耦，层 B 失败不影响层 A 的结果。
