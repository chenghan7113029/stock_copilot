## Context

银行原型在 `PrototypeRouter` 中的分类规则：`银行行业代码 B 或 SIC 银行`（当前实现需确认）。工商银行行业分类为「商业银行」，Tushare `basic_info` 返回 `industry = "银行"`。

Tushare 银行专项指标来源（经调研）：
- `net_interest_margin`（净息差 %）：`fina_indicator` 字段 `netint_margin` 或 Tushare 专项接口
- `npl_ratio`（不良贷款率 %）：需 `stk_fin_audit`（财务摘要）或 `bankloans_stats` 接口
- `provision_coverage`（拨备覆盖率 %）：`fina_indicator` 字段 `prov_cov` 或 `stk_fin_audit`

## Goals / Non-Goals

**Goals:**
- 确认或补充 Tushare 银行指标字段映射
- 确认 PrototypeRouter 对 601398 正确分类为 `bank`
- E2E：sync 601398 → offline report 无异常，主要方法可计算
- 文档记录银行原型所用估值方法与数据来源

**Non-Goals:**
- 不实现 DDM（股息折现）估值引擎（DDM 属于单独 feature）
- 不覆盖所有银行股，601398 作为 P0 验证样本

## Decisions

### 决策 1：银行指标 API 选择

优先使用 `fina_indicator` 已有字段：
- `net_interest_margin` → `fina_indicator.netint_margin`（若为净利息收入/平均总资产，需换算）
- `provision_coverage` → `fina_indicator.prov_cov`（若存在）
- `npl_ratio` → Tushare 无标准接口；使用 `fina_indicator.npl_ratio` 或 `stk_fin_audit`

若 `fina_indicator` 无银行专项字段，则标注 missing；第一阶段优先确保 NIM 和 provision_coverage，NPL ratio 作为 best-effort。

### 决策 2：PrototypeRouter 银行分类

在 `_classify(stock)` 中，检查 `StockData.industry` 字段是否包含「银行」；或 `stock.code` 在已知银行列表（备选）。推荐：行业字段匹配「银行」或「商业银行」即归类 `bank`。

### 决策 3：E2E 测试范围

测试文件：`test/service/value/test_bank_e2e.py`，使用 offline mock（不调真实 API），验证：
1. PrototypeRouter 分类 601398 为 `bank`
2. 银行方法（pe_relative、ev_ebitda 等）能正常运行（不因 NIM/NPL 为 None 抛异常）
3. 聚合中位有值

## Risks / Trade-offs

- **[风险] Tushare fina_indicator 银行字段可能需要高级 token**：2000 积分已满足基础接口；若银行专项需更高权限，降级为 missing + 文档说明。
- **[权衡] NPL ratio 可能无法获取**：V1 允许 missing，银行专项方法仍可基于 NIM + provision_coverage 评分。
