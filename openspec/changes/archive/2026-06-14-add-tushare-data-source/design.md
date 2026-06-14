## Context

当前 V1 数据层已接入 AKShare（P1）与 Baostock（P2），具备多源 failover、来源维度 SQLite 落库与 E2E 字段覆盖验收。已知问题：AKShare 接口偶发空响应时，14 个 V1 必需字段处于 blocked 状态；Baostock 季频接口字段覆盖有限。

参考实现：
- `ref/daily_stock_analysis/data_provider/tushare_fetcher.py` — 流控、Pro API 调用模式
- `ref/valueinvest/valueinvest/data/fetcher/tushare.py` — A 股字段映射

用户已持有 Tushare Pro Token，需在 **不泄露 Token 到仓库** 的前提下完成接入与验证。

## Goals / Non-Goals

**Goals:**

- 实现符合 `BaseFetcher` 的 `TushareFetcher`，映射 V1 价值面关键字段到 `StockData` / `FetchResult`
- 配置驱动启用：`data_sources.enabled` 含 `tushare` 且 Token 有效时才实例化
- 验证样本清单（6 只）上 Tushare 数据能 **独立落库**（`source=tushare`）且读回字段非空（至少行情 + 一项基本面）
- 离线 mock 测试覆盖字段映射与错误路径；网络测试无 Token 时自动 skip

**Non-Goals:**

- 不调整 AKShare/Baostock 默认优先级策略的全局 failover 语义（Provider 仍逐源 fetch 并分别落库）
- 不实现 Tushare 实时行情熔断、积分计费管理 UI
- 不覆盖港股/美股 Tushare 接口（V1 仅 A 股）
- 不要求 Tushare 单独达成 V1 全字段并集（仍由跨源 E2E 聚合验收）

## Decisions

### D1：Token 提供方式（用户如何给你 / 给系统）

**决策**：双通道，优先级 `config/app.yaml` > 环境变量 `TUSHARE_TOKEN`。

```yaml
# config/app.yaml（本地文件，已在 .gitignore，勿提交）
data_sources:
  enabled:
    - name: akshare
      priority: 1
    - name: baostock
      priority: 2
    - name: tushare
      priority: 3
      token: "YOUR_TUSHARE_TOKEN_HERE"   # 从 tushare.pro 个人中心复制
```

环境变量备选（CI / 临时验证）：

```bash
# PowerShell
$env:TUSHARE_TOKEN = "your-token"

# Bash
export TUSHARE_TOKEN=your-token
```

**给 AI / 开发者**：不要在聊天、Issue 或 Git 中粘贴 Token。实施 `/opsx-apply` 时，用户自行编辑本地 `config/app.yaml` 或设置环境变量即可；网络测试读取本地配置，无需向 Agent 传递。

**无 Token 时**：`SourceManager` 若配置启用 tushare 但 token 为空，记录 warning 并跳过实例化（不阻断 AKShare/Baostock）；E2E 测试 `@pytest.mark.skipif(not has_tushare_token())`。

### D2：Fetcher 结构与参考来源

**决策**：新建 `src/data_provider/tushare/`，含 `fetcher.py` + `field_mapping.py`。

- 登录：`ts.set_token(token)` + `ts.pro_api()`，在 fetcher 实例化时完成
- 行情：`daily` / `daily_basic` 或等价接口 → `current_price`、`pe_ratio`、`pb_ratio`、`market_cap`、`shares_outstanding`
- 基本面：`fina_indicator`、`income`、`balancesheet`、`cashflow`、`dividend` 等 → eps、roe、revenue、total_assets 等
- 参考 daily_stock_analysis 的接口选择与重试；字段映射参考 valueinvest

**备选**：直接 import ref/ — **拒绝**（违反工程约定）。

### D3：默认优先级

**决策**：默认 `priority: 3`（token 源排在免 token 源之后），符合 MRD「无需 token > 有 token 但免费」。

Provider 仍对 **每个已启用 fetcher** 分别调用 `fetch_all` 并落库，因此 Tushare 即使优先级低也会写入独立 `source=tushare` 快照，供 E2E 跨源聚合与对比。

用户若积分充足，可在 `app.yaml` 将 tushare 设为 `priority: 1` 提高合并权重（非本 change 默认）。

### D4：验收标准（本 change 交付门槛）

1. **离线**：mock tushare pro_api 返回，断言 `FetchResult` 字段映射与 `missing_fields` 语义
2. **网络**（需 Token）：对 `value_data_validation_stocks.yaml` 全部 6 只代码：
   - 启用仅 tushare（或 tushare + 其他源）运行 fetch → upsert
   - DB 读回存在 `source='tushare'` 记录
   - 每条记录至少含 `current_price` 或 `eps` 等非空字段
3. **回归**：现有离线 pytest + ruff 通过；无 Token 时网络测试 skip 而非 fail

### D5：依赖版本

**决策**：`tushare>=1.4.0`（与 daily_stock_analysis requirements 对齐）。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| Tushare 积分/频率限制导致部分接口失败 | 记录 `FetchResult.error`；E2E 报告 blocked 字段；必要时分接口降级 |
| 不同接口 report_period 不一致 | `_infer_report_period` 沿用现有 DAO 逻辑；快照按 `(code, source, report_period)` 独立 |
| Token 误提交 | `app.yaml` gitignore；example 留空 token；CI 不配置 token |
| 字段与 AKShare 口径差异 | 不纳入 0.1% 一致性门槛（仅 AKShare vs valueinvest）；跨源差异由优先级合并 |

## Migration Plan

1. 合并代码后用户本地编辑 `config/app.yaml` 启用 tushare 并填 Token
2. 运行 `python scripts/fetch_value_data.py` 或 `pytest -m network test/e2e/test_tushare_pipeline.py`
3. 检查 `data/stock_copilot.db` 中 `source=tushare` 快照
4. 若无问题，可选在 E2E 全量测试中启用 tushare 提升字段覆盖率

回滚：从 `data_sources.enabled` 移除 tushare 即可，不影响已有 akshare/baostock 快照。

## Open Questions

1. 用户 Tushare 账号积分是否 ≥ 2000（部分 Pro 接口门槛）— 实施时网络测试会暴露；不足则在缺口报告标注
2. 是否在 `fetch_value_data.py` 增加 `--sources tushare` 过滤 — 可选增强，非阻塞
