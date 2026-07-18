## ADDED Requirements

### Requirement: CLI `report dual` 命令——Level 0 默认离线，Level 1 显式联网
系统 SHALL 提供 `python -m apps.cli report dual <code> [--narrate] [--json] [--output]`。不加 `--narrate` 时 SHALL 严格离线，仅输出证据分桶结果（含兜底内容）；加 `--narrate` 时 SHALL 额外联网调用 `ConfrontationGenerator` 生成 Level 1 报告，命令帮助文本与运行时输出 SHALL 明确提示该步骤联网。`--narrate` 失败时 SHALL 降级为 Level 0 输出并打印 warning，不中断命令（退出码仍为 0）。命令内部 SHALL 复用 `run_report_tech`/`run_report_value` 已有的 analyzer 装配逻辑，不重新实现。

#### Scenario: 默认离线输出证据分桶
- **WHEN** 运行 `report dual 600519`（本地已有快照）
- **THEN** SHALL 输出 bull/bear 证据列表，不发起任何网络请求

#### Scenario: --narrate 联网生成 Level 1
- **WHEN** 运行 `report dual 600519 --narrate`（LLM 已配置）
- **THEN** SHALL 输出 Level 1 互相反驳报告，且底部含"叙事由 AI 生成，仅供参考"免责声明

#### Scenario: --narrate 失败时降级不中断
- **WHEN** 运行 `report dual 600519 --narrate` 但 LLM 未配置或调用失败
- **THEN** SHALL 打印 warning 后仍输出 Level 0 证据分桶结果，退出码为 0

#### Scenario: 无本地快照时明确报错
- **WHEN** 运行 `report dual <code>` 但本地无该代码的价值快照与 K 线缓存
- **THEN** SHALL 输出 `[error] 未找到 <code> 的本地数据，请先运行 sync`，退出码非 0

#### Scenario: --json 与 --output 行为对齐既有 report 命令
- **WHEN** 运行 `report dual 600519 --json` 或 `--output <path>`
- **THEN** 行为 SHALL 与 `report tech`/`report value` 的对应 flag 语义一致（JSON 序列化 / 写入文件而非打印到 stdout）
