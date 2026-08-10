## 1. 前置检查

- [x] 1.1 确认 `add-industry-prototype-router`（T-7）的实施状态：若已归档/合并，确认 `src/service/value/router.py` 中存在 `_INDUSTRY_V2_UNIMPLEMENTED` 字典；若未实施，按 design.md 决策 1 备选方案评估是否临时自建最小字典，或推迟本 change 直到 T-7 完成

## 2. Router：方法论缺口说明

- [x] 2.1 `src/service/value/router.py`：新增字典 `_INDUSTRY_METHODOLOGY_GAP: dict[str, str]`，初始内容：`"保险"→"专用估值方法论（内含价值 EV/NBV 模型）暂缺"`、`"军工"→"专用估值方法论（在手订单驱动 + 资产重估模型）暂缺"`
- [x] 2.2 新增函数 `describe_unimplemented_industry(industry: str | None) -> tuple[str, str] | None`：复用 `_INDUSTRY_V2_UNIMPLEMENTED` 判断行业标签，命中后从 `_INDUSTRY_METHODOLOGY_GAP` 查询缺口说明（查不到时用通用占位"专用估值方法论暂缺"，不抛异常）；`industry` 为空或未命中 `_INDUSTRY_V2_UNIMPLEMENTED` 时返回 `None`

## 3. ValueAnalyzer：精确 fallback 文案

- [x] 3.1 `src/service/value/analyzer.py`：`_analyze_stock()` 的 `prototype == "unknown"` 分支改为先调用 `describe_unimplemented_industry(stock.industry)`；命中时追加精确文案（格式：`f"检测到{label}行业，{gap_note}，当前使用通用方法，结果参考性有限"`）；未命中时保留现有固定文案"原型未识别，使用通用方法集，置信度低"

## 4. 单元测试

- [x] 4.1 `test/service/value/test_router.py`：新增用例——`describe_unimplemented_industry("保险")` 返回 `("保险", "专用估值方法论（内含价值 EV/NBV 模型）暂缺")`；`describe_unimplemented_industry("国防军工")` 返回标签"军工"对应结果（子串匹配）
- [x] 4.2 同文件新增用例——`describe_unimplemented_industry("")`/`describe_unimplemented_industry(None)`/`describe_unimplemented_industry("某未收录行业")` 均返回 `None`
- [x] 4.3 同文件新增用例——`_INDUSTRY_V2_UNIMPLEMENTED` 中存在但 `_INDUSTRY_METHODOLOGY_GAP` 缺失对应标签时（边界场景，模拟未来字典不同步），返回通用占位缺口说明，不抛异常
- [x] 4.4 `test/service/value/test_analyzer.py`：新增用例——`StockData(industry="保险", ...)` 且路由判定为 `unknown` 时，`ValueAnalysisResult.warnings` 包含精确文案（含"保险"与"EV/NBV"关键词）
- [x] 4.5 同文件新增用例——`StockData(industry="", ...)` 且路由判定为 `unknown` 时，`warnings` 包含现有固定文案"原型未识别"（回归验证，确保未破坏现状场景）
- [x] 4.6 回归确认现有 `test_unknown_when_insufficient_data`（`test_router.py`）与相关 `test_analyzer.py` 用例全部保持通过

## 5. 端到端验证

- [x] 5.1 对中国平安 601318（或其他确认为保险行业的真实 A 股代码）运行 `python -m apps.cli sync 601318` + `python -m apps.cli report value 601318`，确认输出的 `--- 警告 ---` 区块包含精确的"检测到保险行业...EV/NBV..."文案，而不是笼统的"原型未识别"
- [x] 5.2 对一个行业信息缺失或不在 V2 清单中的样本股验证 fallback 文案保持现有通用措辞
- [x] 5.3 运行 `pytest test/ -q -m "not network"`，确认全量测试通过，无回归

## 6. 文档更新

- [x] 6.1 更新 `docs/mrd/features/value-analysis.md` §10 场景 5：标注该验收场景已通过精确文案实现
- [x] 6.2 更新 `docs/mrd/features/value-analysis.md` §14.1：T-15 状态由"当前 unknown 通用集，无'方法论暂缺'标注"更新为已实现，并注明依赖 `add-industry-prototype-router` 的行业识别字典
- [x] 6.3 更新 `docs/mrd/roadmap-todo.md` §4.1：T-15 行状态由 `[ ] 待建` 改为 `[x]`，并在变更记录追加一行

## 7. 归档

- [x] 7.1 确认 tasks.md 全部任务完成（归档任务 7.2 按请求跳过）
- [ ] 7.2 运行归档流程（`openspec archive add-prototype-fallback-message` 或对应 Skill），同步 delta 内容回 `docs/mrd/features/value-analysis.md`
