## Why

`docs/mrd/features/value-analysis.md` §10 场景 5 要求："系统标注'保险原型方法论暂缺'，降级为相对估值并明确提示置信度低，不静默套用 PB/PE 误判"；roadmap T-15 状态为"当前 unknown 通用集，无'方法论暂缺'标注"。当前 `ValueAnalyzer._analyze_stock()`（`src/service/value/analyzer.py`）在 `prototype == "unknown"` 时只追加一条固定文案："原型未识别，使用通用方法集，置信度低"——这条 warning 已经覆盖了"降级使用通用方法 + 提示置信度低"的字面要求，但**没有说明是哪个行业、缺哪种方法论**，用户看到"未识别"容易误以为是数据问题（如财报字段缺失），而不是"系统已经知道这是保险股，只是保险专用方法（EV/NBV）还没做"——这是两种性质完全不同的局限，笼统提示会误导用户对结果可信度的判断。

## What Changes

- `src/service/value/router.py` 新增只读工具函数 `describe_unimplemented_industry(industry: str | None) -> tuple[str, str] | None`：复用 `add-industry-prototype-router`（T-7）引入的 `_INDUSTRY_V2_UNIMPLEMENTED` 字典，命中时返回 `(行业标签, 方法论缺口说明)` 二元组（如 `("保险", "专用估值方法论（内含价值 EV/NBV 模型）暂缺")`），未命中返回 `None`
- `src/service/value/router.py` 新增字典 `_INDUSTRY_METHODOLOGY_GAP: dict[str, str]`（行业标签 → 具体缺口说明），V1 覆盖"保险"（EV/NBV 模型）与"军工"（订单驱动 + 资产重估模型），对齐 MRD §2.2 V2 原型清单
- `ValueAnalyzer._analyze_stock()`：`prototype == "unknown"` 时，先调用 `describe_unimplemented_industry(stock.industry)`；命中则追加精确文案（如"检测到保险行业，专用估值方法论（内含价值 EV/NBV 模型）暂缺，当前使用通用方法，结果参考性有限"）；未命中（行业信息缺失或不在已识别 V2 清单中）则保留现有通用文案"原型未识别，使用通用方法集，置信度低"（不移除，作为无法精确识别时的兜底）
- **明确的实施顺序建议（本 change 的核心依赖说明）**：本 change 建议在 `add-industry-prototype-router`（T-7）之后实施，因为精确文案的前提是"能识别出具体是哪个行业"——这正是 T-7 引入的行业映射能力；若 T-7 尚未实施，本 change 必须先在自己范围内补一份最小化的行业识别字典才能达到同等效果，属于重复建设，价值有限（详见 design.md 依赖章节）

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `value-prototype-router`：新增 `describe_unimplemented_industry()` 工具函数与方法论缺口说明字典
- `value-analyzer`：`prototype == "unknown"` 时的 warning 文案逻辑从"固定文案"改为"先尝试精确文案，未命中回退固定文案"

## Impact

- **修改文件**：
  - `src/service/value/router.py`：新增 `_INDUSTRY_METHODOLOGY_GAP` 字典与 `describe_unimplemented_industry()` 函数（依赖 `add-industry-prototype-router` 已引入的 `_INDUSTRY_V2_UNIMPLEMENTED`）
  - `src/service/value/analyzer.py`：`_analyze_stock()` 的 unknown 分支 warning 生成逻辑
- **不修改**：`_classify()` 判定逻辑本身（本 change 只影响"识别后如何措辞"，不影响"识别结果是什么"）、`_PROTOTYPE_METHODS`（不新增 method_keys 集合）
- **测试**：`test/service/value/test_router.py`、`test/service/value/test_analyzer.py`（新增/扩展用例；本 change 只产出方案文档，不实现代码）
- **文档**：`docs/mrd/features/value-analysis.md` §10 场景 5、§14.1（T-15 状态）、`docs/mrd/roadmap-todo.md` §4.1（T-15 行）
- **依赖关系（强关联，需在双方 design.md 交叉说明）**：**强烈建议先实施 `add-industry-prototype-router`（T-7）**，本 change 直接复用其 `_INDUSTRY_V2_UNIMPLEMENTED` 字典；若先实施本 change，需要接受"文案精度退化为通用提示优化"的降级方案（design.md 详细展开两种路径）。与 `add-prototype-override-persistence`（T-8）无直接依赖——人工覆盖生效时 `prototype != "unknown"`，本 change 的分支不会被触发，两者不冲突。
