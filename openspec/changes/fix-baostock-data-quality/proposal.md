## Why

当前 Baostock 数据在三个维度存在系统性错误：`netProfit` 被误当年度净利使用（实为单季/累计值）、`historical_pe` 字段不存在于 API 导致 PE Relative 方法无法运行、`operCashTTM` 对部分标的（如茅台）全部返回 None。这三个问题导致实际估值结果比合理水平低 3-4 倍（茅台：281-436 元 vs 合理区间 1,340-1,474 元）。现阶段需要在不依赖 Tushare 财报接口权限的前提下最大化估值准确性。

## What Changes

- **修复 `net_income` 语义**：Baostock `netProfit` 按季度是累计值（Q4 = 全年），当前代码取最近季度（Q1 单季），导致年度净利被低估 ~3-4 倍。改为优先取 Q4 全年值；TTM 净利使用 `epsTTM × shares_outstanding` 推导（字段已有，精度高）。
- **新增 `historical_pe` 计算**：Baostock K 线 API 不提供 `peTTM` 字段（实测 error 10004012）。改为：按季末取历史收盘价（Baostock K 线）+ `epsTTM`（`query_profit_data`），计算每个季末 PE 快照，取最近 2 年（8 个季度均值）作为 `historical_pe`，启用 `pe_relative` 估值方法。
- **修复 FCF 推导链**：`operCashTTM` 对部分标的返回 None（如茅台，受金融子公司影响）。建立优先级链：① `operCashTTM`（有则直接用）→ ② `CFOToOR × revenue` 反推 OCF（CFOToOR 数据稳定，且实测精度高：0.541 × 1702 亿 ≈ 921 亿 vs 真实 924 亿）→ ③ `net_income × fcf_rate`（配置化 fallback）。
- **修复 `growth_rate` 计算**：当前使用单季 `YOYNI`（2025 年茅台单季同比约 0%，Graham 公式输出 467 元）。改为使用 2 年净利 CAGR（两个 Q4 年度值计算），茅台为 ~5%，Graham 输出修正为 ~1,013 元。
- **`ValuationAggregator` 增加锚定方法检测**：若 `value_growth` 原型的 DCF 和 PE Relative 均为 N/A，则置信度强制标注为「数据不足-不可信」，不输出误导性的窄区间。

## Capabilities

### New Capabilities

- `baostock-net-income-ttm`: 从 `epsTTM × shares_outstanding` 推导 TTM 净利，替代直接使用 `netProfit` 单季值。
- `baostock-historical-pe`: 从 K 线季末收盘价 + `epsTTM` 计算历史 PE 序列（最近 2 年，8 个季末快照），填充 `historical_pe` 字段。
- `baostock-fcf-fallback`: FCF 推导优先级链，包含 `CFOToOR × revenue` 反推路径。
- `growth-rate-cagr`: 使用最近两个 Q4 年度净利计算 2 年 CAGR，替代单季 YOYNI。
- `valuation-reliability-guard`: Aggregator 锚定方法（primary methods）缺失时，强制输出「不可信」标注。

### Modified Capabilities

（无现有 spec 级别的需求变更）

## Impact

**受影响模块**：
- `src/data_provider/baostock/fetcher.py` — 核心修改：netProfit 取值逻辑、新增历史 PE 计算、FCF 推导链
- `src/data_provider/baostock/field_mapping.py` — 字段映射调整
- `src/service/value/aggregator.py` — 增加锚定方法检测逻辑
- `src/service/value/valuation/assumptions.py` — 新增 `fcf_rate` 配置项（FCF/净利率 fallback）
- `config/app.yaml` — 新增 `value_analysis.fcf_rate` 等可配置项

**预期效果**（以茅台 600519 为基准）：
- PE Relative: N/A → ~1,380-1,480 元（目标 ±5%）
- Owner Earnings: 157 元 → ~1,300-1,500 元
- Graham: 467 元 → ~1,000-1,050 元
- EV/EBITDA: 405 元 → ~1,000-1,200 元
- 聚合区间: 281-436 元 → ~1,150-1,450 元
- vs Gemini 参考值 1,340-1,474 元，整体误差 ±10-15%，PE Relative 单项 ±5%
