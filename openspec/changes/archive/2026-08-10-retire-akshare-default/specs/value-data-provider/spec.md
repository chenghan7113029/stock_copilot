## ADDED Requirements

### Requirement: 默认选源叙述对齐 Tushare + Baostock
规范层对「默认启用哪些源」的描述 SHALL 与产品目标态一致：默认启用 `tushare`（有 token 时）与 `baostock`；AKShare 为可选遗留源，MUST 显式配置才启用。免 token 优先的历史默认叙述（默认仅 AKShare/Baostock）在本 change 后不再作为运行默认。

#### Scenario: 文档与 example 一致
- **WHEN** 阅读 `app.example.yaml` 与 value-data-provider 相关说明
- **THEN** 默认示例为 tushare priority=1、baostock priority=2，akshare 不在默认 enabled 中
