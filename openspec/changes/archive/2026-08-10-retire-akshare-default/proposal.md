## Why

阶段 B 已使 `tushare+baostock` 可跑核心链路后，默认配置与 CLI 仍可能暗示或硬编码依赖 AKShare，导致 Cloud/新环境继续踩不稳定源。阶段 C 将**默认产品路径**完全脱离 AKShare，代码可保留为可选遗留以便回滚或对比测试。

权威需求：[docs/mrd/features/data-source-migration.md](../../../docs/mrd/features/data-source-migration.md) §5.C / §12.4。**依赖**：`align-tushare-coverage` 已验收。

## What Changes

- 默认 `config/app.example.yaml` 与 `cloud_bootstrap` 模板：**仅** `tushare(1) + baostock(2)`，无 akshare 条目
- `sync market` 等 CLI：按 Router 源可用性检查，移除「必须启用 akshare」硬错误
- 用户可见文案由「依赖 AKShare」改为「依赖已配置数据源」
- 测试：默认 fixture 不含 akshare；`AKShareFetcher()` 无参构造在生产路径为 0；AKShare 网络测标 `akshare_legacy`，默认 CI 不跑
- **可选**：`akshare` 移至 packaging extra
- **不**物理删除 `src/data_provider/akshare/`（可保留 1–2 个版本）
- 离线 migration baseline **仍须通过**

## Capabilities

### New Capabilities

- `akshare-default-retirement`：默认配置/bootstrap/CI 隔离与遗留测试标记；生产路径零默认 AKShare 实例化

### Modified Capabilities

- `cli-sync`：`sync market`（及同类）不再硬编码要求 akshare enabled
- `value-data-provider`：默认选源叙述与示例对齐 tushare+baostock（规范层）

## Impact

- **代码/配置**：`config/app.example.yaml`、`scripts/cloud_bootstrap.py`、`src/apps/cli.py`、相关文案
- **测试**：`pytest.ini` marker、`test_akshare_*` 隔离、默认 config fixture
- **文档**：MRD 阶段 C 勾选、`roadmap-todo.md`、`product-overview` 数据源描述、`user-guide`
- **回滚**：文档说明如何手动把 akshare 加回 `app.yaml`
