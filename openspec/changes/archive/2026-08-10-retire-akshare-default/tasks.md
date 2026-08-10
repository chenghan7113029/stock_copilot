## 1. 默认配置与 Bootstrap

- [x] 1.1 Modify `config/app.example.yaml`：仅 tushare(1)+baostock(2)
- [x] 1.2 Modify `scripts/cloud_bootstrap.py`：生成配置无 akshare
- [x] 1.3 更新相关注释与 Cloud Agent 文档中的默认源描述

## 2. CLI 门控与文案

- [x] 2.1 Modify `src/apps/cli.py`：`sync market` 改为 Router 源可用性检查
- [x] 2.2 Modify 用户可见「依赖 AKShare」文案 →「依赖已配置数据源」
- [x] 2.3 Modify `test/apps/test_cli_sync_market.py`（或等价）匹配新门控

## 3. 测试隔离

- [x] 3.1 Modify `pytest.ini`（或 pyproject）：增加 `akshare_legacy` marker
- [x] 3.2 Modify `test/data_provider/test_akshare_*.py` 等：标记 legacy；默认 CI 排除
- [x] 3.3 调整默认 config test fixture：不含 akshare
- [x] 3.4 静态检查：`src/` 无 `AKShareFetcher()` 无参构造

## 4. 可选 packaging

- [x] 4.1 评估并将 `akshare` 移至 optional extra（若成本可接受；否则文档登记 OQ-4 延期）

## 5. 验收与文档

- [x] 5.1 `pytest -q -m "not network"` 全绿（无默认 AKShare 实例化）
- [x] 5.2 `python scripts/compare_migration_baseline.py` 通过
- [x] 5.3 `python scripts/trial_cli_workflow.py`（或等价）在 tushare+baostock 下 exit 0
- [x] 5.4 Modify `docs/mrd/features/data-source-migration.md`、`roadmap-todo.md`、`user-guide.md`、必要时 `product-overview.md`
- [x] 5.5 文档化「紧急手动加回 akshare」回滚步骤
- [x] 5.6 运行 `/opsx-archive retire-akshare-default`（用户确认后）
