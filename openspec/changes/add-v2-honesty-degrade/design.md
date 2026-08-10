## Context

价值面 `PrototypeRouter` 已将保险/军工行业短路为 `unknown`，并由 `describe_unimplemented_industry` + `ValueAnalyzer` 输出「方法论暂缺、参考性有限」警告（T-15）。但：

1. 比亚迪（`002594`）、分众（`002027`）行业未进 V2 暂缺表，财务启发落到 `value_growth`，**无任何警告**。
2. 即使保险/军工有警告，`ValuationAggregator` 仍按通用方法算出 MOS → `assessment`「低估/高估」；`SignalFusion.derive_value_rating(mos)` 可得到 `UNDERVALUED` 并融合成「买入」。

Owner 拍板：名单 = 比亚迪+分众 code + 保险/军工行业；三层都压；保险/军工与持仓同标准。本设计只实现诚实层，不实现专用估值模型。

## Goals / Non-Goals

**Goals:**

- 名单内标的不再静默呈现可执行的「价值低估 → 买入」叙事
- 警告对非金融背景可读：缺什么、为何会偏、不能当买卖依据
- 对照用区间/MOS 可保留，但主评估与双轨价值评级去行动化
- 与现有 override、unknown 通用兜底、银行/高股息/价值成长正常路径共存

**Non-Goals:**

- 情景 DCF、CyclicalStock、EV/NBV、订单模型、华测 PEG 路由
- 按「汽车」「传媒」等行业名批量扩容
- 删除方法明细或禁止跑通用方法（仍可算对照数字）
- 改技术面 `BuySignal` 语义（仅切断假价值面对融合的加成）
- 猜测精确「高估了 X%」（只用条件性「容易偏乐观/悲观」）

## Decisions

### D1：识别用 code 白名单 + 既有行业表，不用宽行业子串

| 入口 | 键 | 标签（报告用） |
|------|-----|----------------|
| `_CODE_V2_HONESTY`（新） | `002594` | 成长+制造周期 |
| 同上 | `002027` | 现金流+广告周期 |
| `_INDUSTRY_V2_UNIMPLEMENTED`（既有） | 保险 / 军工… | 保险 / 军工 |

**理由**：持仓少、应用优先；「汽车」「广告」子串误伤面大。  
**备选否决**：仅靠行业名识别比亚迪/分众。

分类：code 命中诚实名单 → `prototype="unknown"`（优先级：人工 override > code 诚实名单 > 既有 `_CODE_OVERRIDE` > 行业 > 启发）。这样不会再跑 `value_growth` 主方法集。

### D2：统一缺口描述 API

将「行业-only」扩展为：

`describe_honesty_gap(code: str, industry: str | None) -> HonestyGap | None`

其中 `HonestyGap` 含：`label`、`methodology_gap`、`bias_note`（可选短句）、`decision_ban` 固定语义。

- code 命中优先于 industry
- 保险/军工继续复用 `_INDUSTRY_METHODOLOGY_GAP`，并**追加**「通用方法得出的低估/高估不应用于买卖决策」
- 比亚迪/分众使用探索阶段敲定的文案骨架（见 proposal / specs）

保留 `describe_unimplemented_industry` 作为薄封装或内部复用，避免破坏既有测试的最小面：可让旧函数转调新 API（仅 industry），或 analyzer 只调新 API。

### D3：结果契约增加 `methodology_applicable: bool`

`ValueAnalysisResult` 新增字段，默认 `True`。

当 `describe_honesty_gap(...)` 非空（且未被「覆盖到已实现原型」跳过）时：

| 字段 | 行为 |
|------|------|
| `methodology_applicable` | `False` |
| `assessment` | 强制 `"方法暂不适用"`（覆盖 aggregator 的低估/高估） |
| `confidence` | 至少降至 `"Low"`；若已是 `"不可信"` 则保持 |
| `fair_value_range` / `margin_of_safety` | **保留**（对照用） |
| `warnings` | 插入置顶诚实警告（精确文案） |

**理由**：双轨与报告用显式布尔，比解析中文 assessment 更稳。  
**备选否决**：只改 warning、不改 assessment（半诚实依旧）。

### D4：双轨强制 `ValueRating.UNKNOWN`

`SignalFusion.fuse` / `derive_value_rating`：若 `value_result.methodology_applicable is False`，**忽略 MOS**，`value_rating=UNKNOWN`。

既有矩阵：`UNKNOWN` + 有技术面 → 仅跟技术面；无技术面 → `WAIT`。  
这样不会出现「价值低估 × 技术买入 → 强烈买入」的假共振。

证据分桶：`value_rating` 不再贡献「[价值评级] 低估」；主 `assessment` 已无「低估」关键字。方法行英文 Undervalued 仍可能进分桶——本期可接受为残余噪声；若单测暴露过大，可对 `methodology_applicable=False` 跳过 method assessment 关键词分桶（可选加固，tasks 中列为可选）。

### D5：人工 override 豁免诚实压制

若 `override_repo` 将原型覆盖为 `bank` / `high_dividend` / `value_growth`，则 **不** 将 `methodology_applicable` 置 False（用户知情选择）。仍可保留一条「已覆盖，诚实降级未启用」类提示（可选，非必须）。

覆盖为 `unknown` 或未覆盖且命中诚实名单 → 正常压制。

### D6：CLI 报告展示

`format_value_report`（或等价路径）：当 `methodology_applicable is False`：

- 警告置顶或紧挨评估行
- 主评估行显示「方法暂不适用」
- MOS/区间旁标注「对照用」或等价短注（中文）

不改 `--json` 字段语义，仅多一个布尔字段。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| Owner 看习惯了「低估」会以为系统坏了 | 文案明确「对照数字仍在、不能决策」；MRD 场景写清 |
| 方法明细仍写 Undervalued，红蓝证据噪声 | 主路径已断；可选跳过 method 关键词分桶 |
| code 名单漂移（换持仓） | 名单集中在 router 常量；扩容走新 change，禁止 silently 用宽行业 |
| 与未来情景 DCF 冲突 | 专用原型落地后从诚实名单移除该 code，恢复 applicable |

## Migration Plan

1. 实现 router/analyzer/result 字段 + 单测  
2. 实现 dual-track 强制 UNKNOWN + 单测  
3. CLI 文案 + 样例离线报告目视（002594 / 002027 / 601318）  
4. 更新 value-analysis MRD 场景 5  
5. 回滚：还原字段默认 True 即恢复旧行为（无数据迁移）

## Open Questions

- 无（Owner 已拍板名单、三层压制、保险/军工同标）。实现期若发现 dashboard/综合报告另有「买入」入口未吃 `methodology_applicable`，记 follow-up 而非扩大本期 scope。
