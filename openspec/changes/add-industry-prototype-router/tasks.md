## 1. 行业映射字典与判定层

- [x] 1.1 `src/service/value/router.py`：新增字典常量 `_INDUSTRY_PROTOTYPE_MAP: dict[str, str]`（子串 → `bank`/`high_dividend`），初始内容：`"银行"→"bank"`、`"电力"→"high_dividend"`、`"水务"→"high_dividend"`、`"燃气"→"high_dividend"`、`"高速公路"→"high_dividend"`、`"港口"→"high_dividend"`
- [x] 1.2 新增字典常量 `_INDUSTRY_V2_UNIMPLEMENTED: dict[str, str]`（子串 → 人类可读行业标签），初始内容：`"保险"→"保险"`、`"国防军工"→"军工"`、`"军工"→"军工"`
- [x] 1.3 新增私有方法 `PrototypeRouter._classify_by_industry(industry: str) -> str | None`：空字符串直接返回 `None`；先查 `_INDUSTRY_PROTOTYPE_MAP`（子串匹配，命中返回对应 prototype）；再查 `_INDUSTRY_V2_UNIMPLEMENTED`（命中返回 `"unknown"`）；否则返回 `None`
- [x] 1.4 修改 `_classify()`：在 `_CODE_OVERRIDE` 命中检查之后、原有第 2 步（`"银行" in stock.industry`）与后续启发式之前，插入 `_classify_by_industry()` 调用；非 `None` 时直接返回；移除原有第 2 步的行内"银行"检查（已被 `_INDUSTRY_PROTOTYPE_MAP` 覆盖，避免重复逻辑）
- [x] 1.5 确保 `_classify()` 后续第 3–6 步（关键字段全 None 判 unknown、杠杆率、股息率、兜底 value_growth）逻辑原样保留，不做内部修改

## 2. 单元测试

- [x] 2.1 `test/service/value/test_router.py`：新增用例——`industry="保险"` 的股票（即使 `total_liabilities/total_assets > 0.85`）路由结果为 `"unknown"`，而不是 `"bank"`（复现并验证修复 Context 中描述的误判 bug）
- [x] 2.2 同文件新增用例——`industry="国防军工"` 或 `"军工"` 路由结果为 `"unknown"`
- [x] 2.3 同文件新增用例——`industry="电力"` 且不满足高杠杆/高股息启发式阈值时，仍路由为 `"high_dividend"`（验证行业映射优先于启发式，而不是仅在启发式命中时才生效）
- [x] 2.4 同文件新增用例——`industry=""` 或 `industry=None` 时，行为与本 change 之前完全一致（回退到现有启发式路径），复用/扩展现有 `test_high_leverage_routes_to_bank`、`test_high_dividend_low_growth_heuristic`、`test_normal_stock_defaults_value_growth` 用例确认无回归
- [x] 2.5 确认现有 `test_bank_classification_by_industry`（`industry="商业银行"`）用例在改动后仍通过（子串匹配兼容性）
- [x] 2.6 确认现有 `test_icbc_hardcoded_bank`、`test_yangtze_power_hardcoded_high_dividend`、`test_moutai_hardcoded_value_growth`、`test_unknown_when_insufficient_data` 全部保持通过（`_CODE_OVERRIDE` 优先级不变的回归验证）

## 3. 端到端验证

- [x] 3.1 对中国平安 601318（或其他确认为保险行业的真实 A 股代码）运行 `python -m apps.cli sync 601318`，检查同步后 `StockData.industry`（或 `StockSnapshot.industry` 落库值）的真实字符串取值
- [x] 3.2 若真实取值与 `_INDUSTRY_V2_UNIMPLEMENTED` 字典假设的字符串不一致（如"保险业"而非"保险"），调整字典内容或改为更宽松的子串匹配，重新验证
- [x] 3.3 运行 `python -m apps.cli report value 601318`，确认输出的 `原型` 字段为 `unknown`（而不是本 change 之前可能误判的 `bank`）
- [x] 3.4 运行 `pytest test/ -q -m "not network"`，确认全量测试通过，无回归

## 4. 文档更新

- [x] 4.1 更新 `docs/mrd/features/value-analysis.md` §14.2-C：行业代码映射状态由"待实现"更新为已实现，并注明"复用 Tushare `stock_basic.industry` 简化分类，非 SW/CS 官方多级代码"这一实现范围说明
- [x] 4.2 更新 `docs/mrd/roadmap-todo.md` §4.1：T-7 行状态由 `[ ] 待建` 改为 `[x]`，并在变更记录追加一行，注明保险误判 bank 的修复
- [x] 4.3 在 `docs/mrd/features/value-analysis.md` 相关章节补充 Open Question：SW/CS 官方行业代码接入留待未来独立 change

## 5. 归档

- [ ] 5.1 确认 tasks.md 全部任务完成
- [ ] 5.2 运行归档流程（`openspec archive add-industry-prototype-router` 或对应 Skill），同步 delta 内容回 `docs/mrd/features/value-analysis.md`
