## ADDED Requirements

### Requirement: Skill 输入契约——读取 `report dual --json` 的证据分桶结果
`.cursor/skills/red-blue-confrontation/SKILL.md` SHALL 声明：Skill 触发后 SHALL 执行 `python -m apps.cli report dual <code> --json`（`<code>` 从用户输入解析）获取证据分桶结果，或在用户已提供现成 JSON 文件路径时直接读取该文件；解析出的 `bull_evidence[]`/`bear_evidence[]` 是后续叙事生成的唯一事实来源，Skill MUST NOT 另行编造或从其他渠道补充个股具体数据。

#### Scenario: 命令未提供代码时提示用户
- **WHEN** 用户触发红蓝对抗 Skill 但未指明股票代码
- **THEN** Skill SHALL 先向用户询问代码，不 SHALL 臆测

#### Scenario: `report dual` 报错时如实转达
- **WHEN** `report dual <code> --json` 返回非 0 退出码（如本地无快照）
- **THEN** Skill SHALL 将错误信息（如"请先运行 sync"）转达用户，不 SHALL 继续生成叙事

### Requirement: Skill 生成约束——锚定证据、禁止编造、固定免责声明
Skill 生成 Level 1 互驳叙事时 SHALL 遵循：多方论述仅基于 `bull_evidence`，空方论述仅基于 `bear_evidence`；互驳部分 SHALL 引用对方证据列表中的具体条目；输出 MUST NOT 包含证据列表之外的具体数值或事实断言；输出末尾 MUST 固定包含免责声明"叙事由 AI 生成，仅供参考，请对照上方原始证据列表核实"。

#### Scenario: 输出结构完整
- **WHEN** Skill 基于非空的 `bull_evidence`/`bear_evidence` 生成叙事
- **THEN** 输出 SHALL 包含多方论述、空方论述、多方对空方的反驳、空方对多方的反驳，以及固定免责声明

#### Scenario: 反驳引用具体证据条目
- **WHEN** 生成互驳内容
- **THEN** 每条反驳 SHALL 可追溯到对方证据列表中的某一具体条目，不 SHALL 是泛泛而谈的空话

### Requirement: Skill 输出呈现——对话内交付，可选落盘为 Markdown
Skill SHALL 在当前 Cursor 对话中直接呈现生成的互驳叙事。Skill MAY 额外将完整报告（含原始证据分桶与叙事）写入 `reports/<code>_confrontation.md`（目录不存在时创建），但 SHALL NOT 写入任何数据库表。

#### Scenario: 对话内呈现
- **WHEN** Skill 生成完成
- **THEN** SHALL 在对话回复中完整展示多空论述与互驳内容

#### Scenario: 可选落盘不落库
- **WHEN** Skill 将报告另存为文件
- **THEN** SHALL 写入 `reports/<code>_confrontation.md`，不 SHALL 调用任何数据库写入操作
