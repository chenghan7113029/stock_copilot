## Context

CLI 报告由 `src/apps/formatters.py` 将 `TechAnalysisResult` / `ValueAnalysisResult` / dual 证据列表渲染为文本。价值方法在 `ValuationResult.details` 中常已含 `formula` 与入参（如 DDM 的 `dividend`/`growth_rate`/`required_return`），价值陷阱在 `value_trap.details` 含五维度风险，但呈现层几乎不展示。用户指南 §5 有白话词典，与报告文件脱节。

explore 定案：详解默认开；Applicable 方法完整卡片；dual 带入讲解；MOS 口径一并修。

**MOS 真源（已核实）：**

```text
aggregator: mos = ((base - price) / base) * 100   → 百分数点（7.14 = 7.14%）
value formatter:     f"{mos:.1f}%"                 → 正确
dual summary:        f"{mos:.1%}"                  → 错误（再 ×100）
dashboard value 区:  f"{mos:.1%}"                  → 错误
DualTrackConfig:     undervalued=0.20, overvalued=-0.10  → 按「比例」语义
signal_fusion 测试:  mos=0.25 期望 UNDERVALUED     → 与聚合器百分数点不一致
```

生产路径上 `ValueAnalyzer` 产出百分数点 MOS，却用比例阈值做 `derive_value_rating`，会导致「仅贵 0.8%」被判为高估（`-0.8 < -0.10`）。本 change **必须**统一单位，不能只改文案。

## Goals / Non-Goals

**Goals:**
- 提供单一讲解模块，供 tech/value/dual（及 dashboard MOS 格式）复用
- 默认文本报告可读：指标注释、方法卡片、价值陷阱拆解、评估词中文化
- 统一 MOS 为百分数点：展示、阈值、测试、文档一致
- dual 在证据分桶后附讲解（同源渲染，不复制文案）

**Non-Goals:**
- 不改各估值方法的公允价数值算法
- 不引入 LLM
- 本期不做 `--concise`
- 不强制重做 EvidenceBucketer 分桶规则（Altman 等），除非修 MOS 时顺带极低成本修正

## Decisions

### 决策 1：讲解落在 `service/report/explainers.py`，formatters 只编排

**选择**：新建 `src/service/report/explainers.py`（词典常量 + `render_tech_explanations` / `render_value_method_card` / `render_value_trap_explainer` / `format_mos_percent_points`）。`formatters.py` 与 `build_analysis_summary` / `dashboard_builder` 调用之。

**理由**：apps 层保持薄；dual 与 value 必须共用同一套中文讲解，避免分叉。

**备选**：讲解全写在 formatters — 拒绝，dual/dashboard 难以复用且难测。

### 决策 2：报告结构 — 决策摘要在前，讲解默认附后

**选择**：
- tech：指标数值区保持紧凑；每个出现的指标下附 1～2 行注释，或指标区后紧跟「指标说明」小节（实现时选可读性更好者，优先行下短注）
- value：顶部评估/区间不变；「估值方法」区对 Applicable 展开完整卡片；Not Applicable 保留一行白话原因；文末或方法区后附价值陷阱详解（若该方法 Applicable）
- dual：先摘要 + 多方/空方证据（Level 0 契约保留）；其后追加「--- 价值面讲解 ---」「--- 技术面讲解 ---」（调用同一渲染器）。JSON 模式：讲解可作为可选字段 `explanations` 对象，避免破坏 Skill 对 `bull_evidence`/`bear_evidence` 的既有解析；若加字段须向后兼容（Skill 可忽略未知键）

**理由**：用户要求默认开启且 dual 要带讲解；证据列表仍须可被 Skill 优先消费。

### 决策 3：方法卡片字段与入参来源

**选择**：卡片固定五块——是什么、适用场景、公式、本次入参（名/值/来源）、结果（公允价/评估中文）。  
入参优先读 `ValuationResult.details` / `components`；来源用静态映射表（如 `dividend`→「价值快照/财报字段」、`required_return`→「AssumptionProvider/配置」）。details 缺失时写「未在 details 中提供」，不编造数字。

**理由**：满足用户审计级透明；符合三层防御——讲解只复述确定性已有字段。

### 决策 4：MOS 统一为百分数点

**选择**：
1. 文档与代码注释明确：`margin_of_safety` 单位为百分数点
2. 提供 `format_mos_percent_points(mos) -> str`，禁止在展示路径使用 `:.1%` 作用于该字段
3. `DualTrackConfig.undervalued_mos_threshold = 20.0`，`overvalued_mos_threshold = -10.0`（与原「20% / -10%」产品语义对齐）
4. 修正 `test_signal_fusion` 等 fixture：用 `25.0` 而非 `0.25` 表示 25% 安全边际
5. 审计所有 `margin_of_safety:.1%` 调用点（至少 dual summary、dashboard_builder）

**理由**：聚合器与 value 报告已是百分数点真源；改阈值与测试比改聚合器破坏面更小、语义更直观。

**备选**：改聚合器去掉 `* 100`、全站改用比例 — 拒绝，将破坏 value 展示与大量已按百分数点编写的测试/文案。

### 决策 5：价值陷阱讲解

**选择**：从 `method_results["value_trap"].details` 读取 `overall_risk` 与各维度；输出中文维度名、风险等级、note；附固定白话：「看起来可能不贵，但基本面有坑时便宜也可能长期无法兑现」。High 时与既有 `value_trap_alert` 区块不重复矛盾（可交叉引用）。

### 决策 6：中文化评估词

**选择**：展示层映射 `Undervalued→低估`、`Overvalued→高估`、`Fair→合理`、`Not Applicable→不适用`、`Applicable→适用` 等；JSON 原始字段可保留英文枚举以免破坏下游，文本报告以中文为主。

## Risks / Trade-offs

- **[风险] 报告显著变长** → **接受**（用户明确默认开）；结构上摘要在前、讲解在后；后置 `--concise`
- **[风险] 改 MOS 阈值改变综合信号** → **预期修正**：原先用比例阈值套百分数点属于错误；改后信号更接近「±10%/20%」产品设计。须在测试与 changelog/user-guide 说明
- **[风险] 部分方法 details 缺公式/入参** → **缓解**：卡片标明缺失；tasks 含「按方法补映射/补 details」清单，优先高频方法（ddm/epv/owner_earnings/value_trap）
- **[风险] dual JSON 增加字段影响 Skill** → **缓解**：只追加可选键；Skill 文档可注「可忽略 explanations」

## Migration Plan

- 无 DB 迁移
- 行为变化：dual/dashboard MOS 数字；部分票的价值评级/综合信号可能从「错误高估」回到「合理」
- 回滚：恢复 formatters/config 与讲解模块删除即可

## Open Questions

- EvidenceBucketer 将「Altman Low Bankruptcy Risk」放入空方是否应改为中性/多方——本期可不改，另开 explore
- `--json` 是否默认带完整讲解（体积大）还是仅 `--explain-json`——建议 JSON 默认带精简 `explanations` 或仅文本模式讲解；apply 时选体积更小的方案并写进 tasks
