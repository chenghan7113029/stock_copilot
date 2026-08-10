## 1. Router：诚实名单与缺口描述

- [x] 1.1 Modify `src/service/value/router.py`：新增 `_CODE_V2_HONESTY`（至少 `002594`、`002027`）及标签/文案；`_classify` 在 `_CODE_OVERRIDE` 前短路为 `unknown`
- [x] 1.2 Modify `src/service/value/router.py`：实现 `describe_honesty_gap(code, industry)`（code 优先）；升级保险/军工缺口文案含「不应用于买卖决策」；保持 `describe_unimplemented_industry` 兼容
- [x] 1.3 Test `test/service/value/test_router.py`：比亚迪/分众 → unknown；保险/军工缺口文案；600519 不受影响；override 可覆盖诚实名单

## 2. ValueAnalyzer：三层压制（评估层）

- [x] 2.1 Modify `src/service/value/models/analysis_result.py`：新增 `methodology_applicable: bool = True`
- [x] 2.2 Modify `src/service/value/analyzer.py`：命中诚实缺口且非已实现原型 override 时，置 `methodology_applicable=False`、`assessment="方法暂不适用"`、confidence≤Low、warnings 置顶
- [x] 2.3 Test `test/service/value/test_analyzer.py`（或新建）：002594/002027/601318 压制；600519 不压制；override value_growth 豁免

## 3. Dual-track：价值评级强制 UNKNOWN

- [x] 3.1 Modify `src/service/dual_track/signal_fusion.py`：`methodology_applicable is False` 时忽略 MOS，`value_rating=UNKNOWN`
- [x] 3.2 Test `test/service/dual_track/`：诚实降级 + 高 MOS + 技术 BUY → rating UNKNOWN 且不走 UNDERVALUED 矩阵；正常标的回归不变
- [x] 3.3 （可选）Modify `evidence_bucketer.py`：诚实降级时跳过 method assessment 的低估/高估关键词分桶，减少红蓝噪声

## 4. CLI 价值报告展示

- [x] 4.1 Modify `src/apps/formatters.py`（`format_value_report`）：`methodology_applicable=False` 时置顶警告、评估「方法暂不适用」、MOS/区间旁「对照用」标注
- [x] 4.2 Test 对应 formatter / cli-report-value 单测；JSON 含 `methodology_applicable`
- [x] 4.3 （目视）对本地有快照的 `002594`/`002027`/`601318` 跑 `report value`，确认无「价值低估→可买入」主叙事

## 5. 文档与收尾

- [x] 5.1 Update `docs/mrd/features/value-analysis.md`：场景 5 扩展为三层压制；记录 code 白名单与 T-15 补完说明
- [x] 5.2 Update `docs/mrd/roadmap-todo.md`（若有对应行）：标注 V2 诚实层 / 本 change
- [x] 5.3 Update `propose_list.md`：本 change 状态
- [x] 5.4 归档前：合并 proposal/design/specs 要点回 `docs/mrd`（或 `docs/design`），再执行 archive 流程
