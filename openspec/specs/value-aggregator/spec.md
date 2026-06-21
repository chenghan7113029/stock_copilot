# value-aggregator Specification

## Purpose
TBD - created by archiving change add-value-analyzer-core. Update Purpose after archive.
## Requirements
### Requirement: 聚合过滤无效方法结果
`ValuationAggregator.aggregate(results, current_price)` SHALL 在聚合前过滤以下结果：
- `result.error is not None`
- `result.applicability == "Not Applicable"`
- `result.details.get("output_type") == "score"`（评分类：altman_z、piotroski_f、beneish_m、value_trap、sbc）

被过滤的评分类方法 SHALL 将 `result.details` 关键信息追加到 `warnings` 列表返回。

#### Scenario: 评分类方法不影响公允价区间
- **WHEN** results 包含 altman_z（score 类）、piotroski_f（score 类）和 dcf（value_estimate=700）
- **THEN** `fair_value_range` 仅基于 dcf；`warnings` 中包含 altman_z 和 piotroski_f 的摘要信息

#### Scenario: 全部结果均不可用
- **WHEN** results 中所有方法均为 "Not Applicable" 或含 error
- **THEN** `fair_value_range=None`，`margin_of_safety=None`，`assessment="数据不足"`，`confidence="Low"`

#### Scenario: 单一有效结果
- **WHEN** 仅 1 个方法返回有效公允价（如 graham_number=500）
- **THEN** `fair_value_range.low=fair_value_range.base=fair_value_range.high=500`（单值退化），`confidence="Low"`

### Requirement: IQR 异常值过滤
当有效公允价集合 `len >= 4` 时，SHALL 使用 IQR 方法（Q1 - 1.5×IQR, Q3 + 1.5×IQR）剔除极端值。过滤后若 len < 2，则回退为不过滤的原始集合（保留全部有效值）。

#### Scenario: 异常值被剔除
- **WHEN** 有效公允价集合为 [500, 520, 540, 3000]（3000 为异常值）
- **THEN** 聚合基于 [500, 520, 540]，3000 被剔除；`warnings` 中包含异常值说明

#### Scenario: 少于 4 个值时不过滤
- **WHEN** 有效公允价集合为 [500, 3000]（2 个值）
- **THEN** 两者均参与聚合，不执行 IQR 过滤

### Requirement: 聚合输出区间与 MOS
聚合后 SHALL 计算：
- `base = median(filtered_values)`
- `low = percentile(filtered_values, 25)`
- `high = percentile(filtered_values, 75)`
- `margin_of_safety = (base - current_price) / base * 100`（%）
- `price_percentile`：current_price 在 [low, high] 中的线性百分位，low 时为 0，high 时为 100，超出范围 clamp 到 [0, 100]

#### Scenario: 正常聚合计算
- **WHEN** filtered_values=[600, 700, 800]，current_price=650
- **THEN** base=700，low=650（Q1），high=750（Q3），MOS≈7.14%，assessment 为"合理偏低"

#### Scenario: 当前价高于 base（高估）
- **WHEN** filtered_values=[600, 700, 800]，current_price=900
- **THEN** MOS≈-28.6%，assessment 为"高估"

### Requirement: 置信度评估
`confidence` SHALL 按以下规则赋值：
- 有效方法数 ≥ 3 且变异系数 `cv = std/mean < 0.3` → `"High"`
- 有效方法数 ≥ 2 → `"Medium"`
- 有效方法数 < 2 → `"Low"`

#### Scenario: 三方法低离散度 → High
- **WHEN** 3 个有效公允价为 [680, 700, 720]（cv≈0.03）
- **THEN** `confidence="High"`

#### Scenario: 两方法 → Medium
- **WHEN** 2 个有效公允价为 [600, 900]
- **THEN** `confidence="Medium"`

