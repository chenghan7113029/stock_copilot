## ADDED Requirements

### Requirement: ChecklistRecord 数据模型
系统 SHALL 提供 `ChecklistRecord` 持久化模型，字段覆盖 `code`/`action`/`value_reasons`（≥0 条，校验层负责条数门槛）/`tech_alignment`/`sentiment_position`/`stop_loss_price`/`take_profit_price`/`passed`/`rejection_reasons`/`created_at`。

#### Scenario: 保存一条完整提交
- **WHEN** 调用 `ChecklistRepo.save()` 传入包含全部字段的提交
- **THEN** SHALL 持久化成功，`list_by_code(code)` SHALL 能读回该记录且字段值一致

### Requirement: 价值理由条数与有效性校验
系统 SHALL 提供 `ChecklistValidator.validate(submission) -> ChecklistValidationResult`（纯规则，零 LLM）。价值理由少于 2 条 SHALL 判定 `passed=False`；理由条目命中「可得性单一来源」启发式规则（过短或命中可得性关键词且未命中价值面关键词）且导致有效理由不足 2 条时 SHALL 判定 `passed=False`。

#### Scenario: 价值理由仅 1 条
- **WHEN** 提交的 `value_reasons` 长度为 1
- **THEN** `passed` SHALL 为 `False`，`rejection_reasons` SHALL 包含「价值理由不足 2 条」相关提示

#### Scenario: 两条理由均为新闻感觉式单一来源
- **WHEN** 提交的 `value_reasons` 为 `["昨晚看新闻说要涨", "群里有人说不错"]`
- **THEN** `passed` SHALL 为 `False`，`rejection_reasons` SHALL 包含「疑似可得性单一来源」相关提示

#### Scenario: 两条理由均引用价值面输出
- **WHEN** 提交的 `value_reasons` 为 `["PE 处于历史低分位，安全边际充足", "现金流稳健，ROE 持续高于行业均值"]`，且技术面配合、情绪位置、止损止盈字段均已填写
- **THEN** `passed` SHALL 为 `True`，`rejection_reasons` SHALL 为空数组

### Requirement: 必填字段完整性校验
系统 SHALL 校验 `tech_alignment`/`sentiment_position`/`stop_loss_price`/`take_profit_price` 均非空；任一缺失 SHALL 判定 `passed=False` 并在 `rejection_reasons` 中指出具体缺失字段。

#### Scenario: 缺失止损点
- **WHEN** 提交未填写 `stop_loss_price`
- **THEN** `passed` SHALL 为 `False`，`rejection_reasons` SHALL 包含「止损点未填写」
