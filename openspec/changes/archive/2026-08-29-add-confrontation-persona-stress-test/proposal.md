## Why

红蓝对抗（PO-03）主要对抗 **确认偏差**（只听支持自己立场的一面）。竞品 `ai-hedge-fund` 的 Persona 机制对抗的是 **路径依赖 / 单框架思维**（只会一种投资哲学看票）。Owner 在 explore 中确认 **纳入 Persona**，与 CLI + API 主路径一致。

同一包 deterministic evidence 上，用 3 个固定 lens（价值质量 / 趋势动量 / 风控底线）生成只读解读，**不得引入 evidence 外事实**，且每条结论须引用 evidence `[n]`。

## What Changes

- 新增 CLI `report persona-stress <code> [--narrate] [--json] [--output]`：
  - Level 0：读取与 `report confront` 相同的 numbered evidence（可复用 confront 缓存记录或现场 `analyze_offline`）
  - Level 1（`--narrate`）：对 3 个固定 persona 分别调用 `narrate()`（独立 schema + grounded 校验 + 分 persona 缓存键）
- Persona 固定集合（V1）：
  - `value_quality` — 长期质量 / 现金流 / 安全边际 lens
  - `trend_momentum` — 趋势与动量 lens（显式列出被忽略的价值面证据）
  - `risk_governor` — 最坏情形 / 止损 / 价值陷阱 lens
- 输出写入 `PersonaStressRecord` 或 `ConfrontationRecord.persona_json`（design 二选一）；与 declare **独立**（persona 是压力测试，不是买卖建议）
- 可选 `--confrontation-id`：挂载到同一次分析会话

**不包含：**
- 19 个 investor persona（ai-hedge-fund 规模）
- Persona 输出自动写入 Checklist 或触发交易
- 多轮 persona 辩论（V1 仅并行三 lens）

## Capabilities

### New Capabilities
- `confrontation-persona-stress-test`：三 persona prompt 模板、schema、grounded 规则
- `cli-report-persona-stress`：`report persona-stress` 子命令

### Modified Capabilities
- `confrontation-narrate-api`：共享 numbered evidence 契约与 narrator 基础设施（若本 change 后于 narrate-api 实现）

## Impact

- **新增**：`src/service/guard/persona_stress_narrator.py`、formatter、测试
- **依赖**：`add-confrontation-narrate-api`（evidence 编号 + narrate 管道）
- **文档**：`competitive-reference.md` §4.1 Persona 映射；`roadmap-todo.md` 新增 PO-03b
