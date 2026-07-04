## ADDED Requirements

### Requirement: 核心方法全部 N/A 时标注「不可信」
`ValuationAggregator.aggregate()` SHALL 检测「锚定估值方法」是否均因数据不足而 N/A，若是，则在结果中标注置信度为「不可信」并插入显著警告，而非输出误导性的窄区间。

锚定方法定义（按原型分类）：
- `value_growth` 原型：`dcf`、`pe_relative` 为核心锚定方法
- `bank` 原型：`pb_relative`、`residual_income` 为核心锚定方法
- `high_dividend` 原型：`ddm`、`two_stage_ddm` 为核心锚定方法

原型推断规则：从 `results` dict key 集合推断（若同时包含 `dcf` 和 `pe_relative`，则为 `value_growth`）。

#### Scenario: 核心方法全部 N/A
- **WHEN** `results` 中所有核心锚定方法的 `applicability == "Not Applicable"`
- **THEN** `AggregateResult.confidence = "不可信"`，且 `warnings` 列表首位插入警告：`"⚠ 核心估值方法（DCF、历史PE）均因数据不足未运行，当前区间参考意义有限"`

#### Scenario: 部分核心方法可用
- **WHEN** 至少一个核心锚定方法成功运行（`applicability != "Not Applicable"` 且 `fair_value > 0`）
- **THEN** 正常聚合，`confidence` 由原有逻辑（方法数量 + CV）决定，不触发「不可信」标注

#### Scenario: 无锚定方法的结果集（无法推断原型）
- **WHEN** `results` 中不包含任何锚定方法的 key（如仅有 DDM、PB 等）
- **THEN** 跳过检测，不触发「不可信」标注

#### Scenario: 辅助方法产出区间但区间值差异大
- **WHEN** 仅有辅助方法产出结果，且 IQR 过滤后方法数 ≤ 2
- **THEN** `confidence` 保持 "Low"（原有逻辑），同时触发「不可信」警告（若核心方法也均 N/A）
