## Context

`docs/mrd/features/value-analysis.md` §10 场景 5（Given/When/Then）：

> **Given** 用户请求分析 `中国平安 601318`（保险，V2）；**When** 调用价值面分析；**Then** 系统标注"保险原型方法论暂缺"，降级为相对估值并明确提示置信度低，**不静默套用 PB/PE 误判**

当前 `src/service/value/analyzer.py::ValueAnalyzer._analyze_stock()` 的相关代码：

```python
prototype, method_keys = self._router.route(stock)
warnings: list[str] = []
if prototype == "unknown":
    warnings.append("原型未识别，使用通用方法集，置信度低")
```

这条固定文案已经满足"降级 + 置信度低提示"的字面要求（`_PROTOTYPE_METHODS["unknown"]` 本身就是通用方法集，`confidence` 计算逻辑本身会因方法数少/离散度大而偏低，见 `value-aggregator` capability），**唯一缺口**是文案没有说明"为什么未识别"——这个缺口只有在系统**已经知道**具体行业（保险/军工等）却仍然落到 `unknown` 分支时才有意义去精确化；如果系统连行业信息都没有（`stock.industry` 为空），"未识别"本身就是准确描述，没有更精确的话可说。

因此本 change 的可行性直接取决于"系统是否已经具备行业识别能力"——这正是 `add-industry-prototype-router`（T-7）引入的 `_INDUSTRY_V2_UNIMPLEMENTED` 字典（行业名称 → 人类可读标签，如"保险"、"军工"，命中时短路路由到 `"unknown"` 但保留"已识别"这一事实）。

## Goals / Non-Goals

**Goals:**
- 当 `prototype == "unknown"` 且系统能识别出具体行业（保险/军工等 V2 清单行业）时，输出精确的"检测到 X 行业，Y 方法论暂缺"文案
- 无法识别具体行业时，保留现有通用文案作为兜底，不回归、不报错
- 明确记录本 change 与 `add-industry-prototype-router`（T-7）的依赖关系与先后实施建议

**Non-Goals:**
- 不实现任何 V2 原型的真实估值方法论（保险 EV/NBV、军工订单模型等，属于 T-4/T-5，未来独立 change）
- 不改变 `unknown` 原型的 `method_keys`（仍是通用方法集，不因识别出具体行业而调整方法选择——"方法论暂缺"就是暂缺，不能因为知道是保险就临时套用错误方法，这正是场景 5 强调的"不静默套用 PB/PE 误判"）
- 不修改 `_classify()` 的判定逻辑或判定结果，只修改"识别结果为 unknown 时如何描述原因"
- 不扩展 `_INDUSTRY_V2_UNIMPLEMENTED` 覆盖的行业范围（沿用 T-7 的既有内容，扩展行业清单是 T-7 的维护范畴，不是本 change 的职责）

## Decisions

### 决策 1：本 change 依赖 `add-industry-prototype-router`（T-7）已引入的行业识别字典，不重复建设

**选择**：`describe_unimplemented_industry()` 直接复用 T-7 的 `_INDUSTRY_V2_UNIMPLEMENTED` 字典（行业名称子串 → 人类可读标签），本 change 只新增一个"标签 → 方法论缺口说明"的映射（`_INDUSTRY_METHODOLOGY_GAP`）和一个组合两者的工具函数，不重新定义行业识别逻辑。

**理由**：行业识别（"这是不是保险行业"）与方法论缺口描述（"保险行业具体缺什么方法"）是两个独立关注点，前者已经是 T-7 的职责，本 change 只负责后者，符合单一职责与不重复建设的原则。

**备选方案（拒绝，即"T-7 未实施时的降级路径"）**：
- **方案 B：本 change 独立维护一份最小行业识别字典**（不依赖 T-7，自己在 `analyzer.py` 或 `router.py` 里新增一个功能重叠的 `industry in ("保险", "国防军工", "军工")` 判断）——**技术上可行但明确不推荐**，属于本 change 与 T-7 的接口重复建设：如果两个 change 都各自维护一份"哪些行业属于 V2 未实现清单"的字典，未来任何一方扩展清单（如新增"周期"行业）都需要记得同步另一份，产生维护负担。**本 change 的推荐路径是等待/协调 T-7 先行**，方案 B 仅作为"若确实需要独立交付本 change"的兜底选项记录在此，实施前应重新确认 T-7 的排期。

### 决策 2：`unknown` 分支的 warning 生成逻辑——"先尝试精确，后回退通用"，不是"替换"

**选择**：

```python
if prototype == "unknown":
    detail = describe_unimplemented_industry(stock.industry)
    if detail is not None:
        label, gap_note = detail
        warnings.append(f"检测到{label}行业，{gap_note}，当前使用通用方法，结果参考性有限")
    else:
        warnings.append("原型未识别，使用通用方法集，置信度低")
```

**理由**：`prototype == "unknown"` 的成因有两类——"行业已识别但方法论未实现"（本 change 目标场景）与"行业信息缺失/财务字段严重不足"（现状场景，`test_unknown_when_insufficient_data` 覆盖的场景）。两类成因用不同文案描述是必要的，不能用同一句话覆盖；`describe_unimplemented_industry()` 返回 `None` 时保留原有文案，保证第二类场景的现有行为、现有测试（`test_analyzer.py`/`test_router.py` 中依赖"原型未识别"文案的用例，若存在）不受影响。

**备选方案（拒绝）**：
- **完全替换固定文案，行业信息缺失时也尝试给出"更友好"的话**——拒绝，行业信息真正缺失时没有更多确定性信息可供生成精确文案，编造"可能属于某行业"的猜测违反"确定性计算不猜测"的三层防御原则（`docs/agent-engineering-quality.md`），保留现状文案是唯一诚实的选择。

### 决策 3：方法论缺口说明文案内容——V1 覆盖保险与军工两个高确定性案例

**选择**：`_INDUSTRY_METHODOLOGY_GAP = {"保险": "专用估值方法论（内含价值 EV/NBV 模型）暂缺", "军工": "专用估值方法论（在手订单驱动 + 资产重估模型）暂缺"}`，与 T-7 的 `_INDUSTRY_V2_UNIMPLEMENTED` 字典的行业标签集合一一对应（当前 T-7 覆盖"保险"、"军工"）。若 T-7 未来扩展识别更多 V2 行业（如"周期"、"成长科技"），本字典 SHALL 同步补充对应缺口说明，否则 `describe_unimplemented_industry()` 会命中行业标签但查不到缺口说明文案——需要防御性处理（缺口说明缺失时用通用占位"专用估值方法论暂缺"，不抛异常，不阻断流程）。

**理由**：与 MRD §2.2/§4 V2 原型清单的"原因"列一一对应（保险缺 EV/NBV、军工 DCF 不稳），文案直接引用 MRD 已有措辞，保持术语一致性，不是本 change 自创。

**备选方案（拒绝）**：
- **通用缺口说明**（如统一说"该行业专用方法论暂缺"，不区分保险/军工的具体缺口内容）——拒绝，会削弱本 change 的核心价值（"从模糊到精确"），如果不说明具体缺什么方法，价值增量非常有限，等同于换了个说法的"未识别"。

## Risks / Trade-offs

- **[风险] 若 `add-industry-prototype-router` 未先实施，本 change 无法工作**（`_INDUSTRY_V2_UNIMPLEMENTED` 不存在，`describe_unimplemented_industry()` 无字典可查）→ **缓解**：proposal.md 与本 design.md 已明确记录先后实施建议；tasks.md 会将"确认 T-7 已实施"列为前置检查任务，若尚未实施则按决策 1 备选方案（方案 B）临时建一份最小字典，作为技术兜底但需要在实施时重新评估是否值得（可能价值不足以立项，应推迟等待 T-7）。
- **[风险] `_INDUSTRY_METHODOLOGY_GAP` 与 T-7 的 `_INDUSTRY_V2_UNIMPLEMENTED` 未来可能不同步**（T-7 扩展行业清单但本 change 忘记补充对应缺口说明）→ **缓解**：决策 3 已设计防御性回退（缺失缺口说明时用通用占位文案，不阻断），且单测应覆盖"标签存在但缺口说明缺失"的边界场景，防止未来 T-7 扩展清单时静默出现不完整文案。
- **[风险] 文案本身仍然是"通用方法集"的免责声明，可能被用户忽略，与 T-2（value_trap High 专项提示）类似的"用户忽略警告"风险**→ **接受**：本 change 范围是"提高文案精确度"，不涉及"如何让用户更重视警告"（如是否需要像 T-2 一样做醒目区块渲染）；若未来发现精确文案仍被忽略，可以复用 T-2 已建立的"醒目区块"渲染模式（`add-value-trap-high-alert` 的 CLI 渲染方案），但那是另一个独立的小 change，不在本 change 范围内预先设计。

## Migration Plan

- 无数据库变更
- `describe_unimplemented_industry()` 是新增纯函数，`_analyze_stock()` 的分支逻辑变化仅影响 `prototype == "unknown"` 且行业信息命中 `_INDUSTRY_V2_UNIMPLEMENTED` 的场景；其余场景（`prototype != "unknown"`，或 `unknown` 但行业未命中）warning 文案与本 change 之前完全一致
- 回滚：还原 `_analyze_stock()` 的 unknown 分支为固定文案，删除 `describe_unimplemented_industry()`/`_INDUSTRY_METHODOLOGY_GAP` 即可，不影响路由判定结果本身

## Open Questions

- 若 `add-industry-prototype-router` 的实施排期不确定，是否应该按决策 1 备选方案（方案 B）先做一个不依赖它的最小版本？建议：不建议，价值有限（详见决策 1），除非产品侧明确要求"平安必须尽快看到精确文案"且 T-7 排期明显滞后，才考虑临时方案，正常情况下应等待/协调 T-7 先行。
- 未来若 T-4/T-5（保险 EV/NBV、军工订单模型）真正实现，本 change 引入的 `_INDUSTRY_METHODOLOGY_GAP` 文案和 `unknown` 分支逻辑需要相应移除或调整（届时"保险"行业会有真正的 prototype 而不再落入 `unknown` 分支）——本 change 不预先设计这个过渡，留给 T-4/T-5 的 change 处理。
