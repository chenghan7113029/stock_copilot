## 1. Aggregator：value_trap High 专项检测

- [x] 1.1 `src/service/value/aggregator.py`：`AggregateResult` dataclass 新增字段 `value_trap_alert: str | None = None`
- [x] 1.2 新增私有方法 `ValuationAggregator._value_trap_alert_message(value_trap_result: ValuationResult) -> str | None`：读取 `value_trap_result.details`，当 `overall_risk == "High"` 时拼接 High 维度中文名生成醒目文案（decision 3 格式），否则返回 `None`
- [x] 1.3 新增私有方法 `ValuationAggregator._downgrade_confidence(confidence: str) -> str`：映射表 `{"High": "Medium", "Medium": "Low", "Low": "Low", "不可信": "不可信"}`
- [x] 1.4 `aggregate()` 主流程：在现有 confidence 计算完成后，若 `results.get("value_trap")` 存在且其 `details.overall_risk == "High"`，则设置 `AggregateResult.value_trap_alert` 与降级后的 `confidence`（调用 1.2/1.3 新增方法）
- [x] 1.5 确认 High 专项逻辑不影响 `_score_summary()` 现有行为（`warnings` 列表仍保留 value_trap 摘要行，两者并存，不去重不冲突）

## 2. ValueAnalysisResult 与 ValueAnalyzer 透传

- [x] 2.1 `src/service/value/models/analysis_result.py`：`ValueAnalysisResult` 新增字段 `value_trap_alert: str | None = None`
- [x] 2.2 `src/service/value/analyzer.py`：`_analyze_stock()` 构造 `ValueAnalysisResult` 时传入 `agg.value_trap_alert`

## 3. CLI 报告渲染

- [x] 3.1 `src/apps/formatters.py`：`format_value_report()` 在 `名称`/`原型` 行之后、`评估`/`置信度` 行之前，若 `result.value_trap_alert` 非空则插入醒目区块（如以 `"⚠⚠⚠"` 分隔线包裹，独立于文末 `--- 警告 ---` 区块）
- [x] 3.2 确认 `as_json=True` 路径自动包含 `value_trap_alert`（`_to_json_serializable` 对 dataclass 字段的既有序列化逻辑无需改动，仅需新增字段自动被覆盖）

## 4. 单元测试

- [x] 4.1 `test/service/value/test_aggregator.py`：新增用例——`value_trap.details.overall_risk == "High"` 时，`AggregateResult.value_trap_alert` 非空且包含至少一个 High 维度名称；`confidence` 相比无此降级时低一级
- [x] 4.2 同文件新增用例——`overall_risk` 为 `"Medium"`/`"Low"`/`"Limited"` 时，`value_trap_alert` 为 `None`，`confidence` 不受影响（沿用既有计算结果）
- [x] 4.3 同文件新增用例——`confidence` 已经是 `"不可信"`（核心方法全 N/A 场景）时，即使 value_trap High，`confidence` 仍保持 `"不可信"`（降级映射表的边界情况）
- [x] 4.4 `test/service/value/test_analyzer.py`：新增用例验证 `ValueAnalysisResult.value_trap_alert` 从 `ValueAnalyzer.analyze()`/`analyze_offline()` 端到端透传（mock provider 注入 value_trap High 的 stub 数据）
- [x] 4.5 `test/apps/test_cli_report_value.py`（如已存在则扩展，否则新建对应用例文件）：验证 `format_value_report()` 在 `value_trap_alert` 非空时输出包含醒目区块文本，为空时不输出该区块；`as_json=True` 时输出 JSON 含 `value_trap_alert` 键
- [x] 4.6 回归验证：`test/service/dual_track/test_evidence_bucketer.py` 现有用例全部保持通过，不因本 change 改动而失败（证实 design.md Context 中"无需联动修改"的核查结论）

## 5. 端到端验证

- [x] 5.1 构造或复用一个已知会触发 `value_trap` High 的样本股（离线 fixture 或真实样本，如财务健康维度显著恶化的股票），运行 `python -m apps.cli report value <code>`，人工确认报告头部出现醒目警示区块，且区块内容列出的维度与 `value_trap` 方法明细一致
- [x] 5.2 运行 `python -m apps.cli report value <code> --json`，确认 JSON 输出含 `value_trap_alert` 字段且值与文本报告一致
- [ ] 5.3 运行 `pytest test/ -q -m "not network"`，确认全量测试通过，无回归

## 6. 文档更新

- [x] 6.1 更新 `docs/mrd/features/value-analysis.md` §8.1：将「`overall_risk=High` 时专项提示...尚未实现」更新为已实现状态说明
- [x] 6.2 更新 `docs/mrd/features/value-analysis.md` §14.1/§12：`value_trap High` 专项行状态更新
- [x] 6.3 更新 `docs/mrd/roadmap-todo.md` §4.1：T-2 行状态由 `[ ] 待建` 改为 `[x]`，并在变更记录追加一行

## 7. 归档

- [ ] 7.1 确认 tasks.md 全部任务完成
- [ ] 7.2 运行归档流程（`openspec archive add-value-trap-high-alert` 或对应 Skill），同步 delta 内容回 `docs/mrd/features/value-analysis.md`
