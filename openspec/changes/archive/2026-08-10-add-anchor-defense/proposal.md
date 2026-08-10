## Why

`product-overview.md` §5.2 将「锚定效应」列为 P1 决策护航机制：「盯历史最高价或买入成本」→ Copilot 机制「模糊区间概率估值：隐藏易锚定数字；展示动态合理区间分位（如未来 1 年胜率 60% 区间）」，对应 `roadmap-todo.md` PO-07。

调研现状发现：`ValueAnalysisResult.price_percentile` 字段（`src/service/value/aggregator.py::_price_percentile`）**已经存在**并已在 `report value` CLI 输出中展示（`src/apps/formatters.py:149-150`「价格分位: X%」）。该字段计算的是「当前价格在多方法估值聚合出的公允价区间 `[low, high]` 中所处的百分位」，是一个真实存在的确定性概率化表达，但与 MRD 设想的「未来 1 年胜率 60% 区间」（一个基于历史统计的前瞻性胜率区间）在语义上并不完全等价——前者是"当前价格相对合理估值区间的静态位置"，后者是"基于历史相似分位后续表现的前瞻性统计"。同时，当前系统**没有任何字段或呈现规则涉及"历史最高价"或"用户买入成本"**（技术面 `resistance_levels` 仅为近 20 日高点，不是长期锚定意义上的历史最高价；持仓成本价数据完全不存在，因为持仓/交易记录基础设施尚未建设，见 `add-fresh-entry-check`/`add-trade-review-attribution` 未实现）。

因此本 change 的定位是**呈现层增强**，而非从零新建计算模块：消费已有的 `price_percentile`，将其从"一个数字"包装为"锚定防御"语境下的概率化定性表达，并建立一条"默认不展示原始锚定数字"的呈现护栏规则，为未来任何新增功能（如历史最高价、持仓成本价）预先设定"不得默认暴露"的约束，避免重蹈"顺手加一行现价对比历史最高价"从而制造新锚点的覆辙。

## What Changes

- 新增呈现规则层 `service/value/` 内的分位定性映射函数：将 `price_percentile`（0–100 的数值）映射为定性分档描述（如"历史估值区间低位/中低位/中性/中高位/高位"），文本化输出弱化具体数字、强调相对位置
- **修改** `report value` CLI 输出：默认呈现分位定性描述 + 弱化的数值标注（如置于括号内、不作为首行），不再以"价格分位: X%"作为孤立呈现该数字的方式（对齐"隐藏易锚定数字"的产品要求：具体数字仍可查但不是视觉/语义焦点）
- 新增"历史最高价"计算能力（基于本地 K 线缓存的滚动窗口最高价，如近 1 年/近 3 年/上市以来可得数据的最高价），但**默认不在任何报告中展示**，仅作为内部计算基础设施与未来功能（如告警、回测）预留字段；新增显式 opt-in 参数/flag 才会展示，建立"任何绝对价格锚点默认隐藏，需要显式声明才能展示"的呈现护栏惯例
- **明确不做**（因依赖未就绪）：用户买入成本价/持仓盈亏的隐藏规则——因为当前无任何持仓/交易记录数据模型（`add-fresh-entry-check` 未实现），系统本身还没有"成本价"这个数据可以展示或隐藏；本 change 仅处理"公开的历史最高价"这一类数据的呈现护栏，成本价护栏留给 `add-fresh-entry-check` 落地时复用本 change 建立的护栏惯例

## Capabilities

### New Capabilities
- `anchor-defense-presentation`：分位定性分档映射（数值 → 定性描述）+ 历史最高价计算（默认隐藏，opt-in 展示）的呈现护栏规则

### Modified Capabilities
- `cli-report-value`：`report value` 文本输出格式调整，`price_percentile` 呈现方式从"孤立数字"改为"定性分档描述为主、数值为辅"

## Impact

- **新增文件**：
  - `src/service/value/anchor.py`（分位定性分档映射函数、历史最高价计算函数）
  - `test/service/value/test_anchor.py`
- **修改文件**：
  - `src/apps/formatters.py`：`format_value_report` 调整 `price_percentile` 展示方式，新增（默认不触发的）历史最高价展示分支
  - `src/apps/cli.py`：`report value` 新增可选 `--show-anchor-price` flag（opt-in 展示历史最高价，默认关闭）
  - `test/apps/test_formatters.py`、`test/apps/test_cli_report.py`：覆盖新呈现规则
- **依赖**：无强制前置 change；成本价隐藏规则明确留给未来 `add-fresh-entry-check`（若该 change 先行落地，须复用本 change 建立的"默认隐藏、opt-in 展示"惯例，不应重新发明）
- **文档**：`docs/mrd/product-overview.md` §5.2/§7（PO-07 状态更新）、`docs/mrd/roadmap-todo.md`（新增变更记录）
