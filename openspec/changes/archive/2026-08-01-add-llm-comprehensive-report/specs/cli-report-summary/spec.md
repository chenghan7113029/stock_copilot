## ADDED Requirements

### Requirement: CLI `report summary` 命令——默认离线摘要，显式 flag 才联网叙事
系统 SHALL 提供 `python -m apps.cli report summary <code> [--json] [--output] [--narrate]`。不传 `--narrate` 时命令 SHALL 严格离线，仅输出确定性摘要（`combined_signal`/`value_rating`/红蓝证据条数）；传入 `--narrate` 时命令 SHALL 额外调用 `narrate_comprehensive_report()`，SHALL NOT 修改 `report dual` 的既有契约与行为。

#### Scenario: 默认离线摘要
- **WHEN** 运行 `report summary 600519`（未传 `--narrate`）
- **THEN** SHALL 输出确定性摘要文本，不发起任何网络请求

#### Scenario: --narrate 触发联网叙事
- **WHEN** 运行 `report summary 600519 --narrate` 且 LLM 已配置
- **THEN** SHALL 在确定性摘要基础上追加 LLM 生成的 `summary`/`key_points`/`risks` 段落

#### Scenario: --narrate 失败时优雅降级
- **WHEN** 运行 `report summary 600519 --narrate` 但 `narrate_comprehensive_report()` 返回 `ok=False`
- **THEN** SHALL 仍输出确定性摘要，并附加提示「LLM 叙事生成失败：<原因>」，退出码 SHALL 为 0（不视为命令失败）

#### Scenario: 无本地数据时明确报错
- **WHEN** 运行 `report summary <code>` 但本地无该代码的价值快照与 K 线缓存
- **THEN** SHALL 输出 `[error] 未找到 <code> 的本地数据，请先运行 sync`，退出码非 0，SHALL NOT 调用 LLM
