## Context

阶段 A/B 完成后，AKShare 不再是能力必要源，却仍可能出现在默认配置与硬门控中。Owner 目标态（D-7）：默认 `tushare(1)+baostock(2)`。本阶段做配置与测试隔离，保留源码作遗留。

## Goals / Non-Goals

**Goals:**

- 新 bootstrap / example 无 akshare
- 生产路径无 `AKShareFetcher()` 无参构造；默认单测不实例化 AKShare
- `sync market` 基于 Router 可用性，不硬编码 akshare
- S2 baseline 仍绿；`trial_cli_workflow` 在 tushare+baostock 下通过

**Non-Goals:**

- 从仓库删除 akshare 包目录
- 重写全部历史 OpenSpec 归档文案
- 保证与旧 AKShare 情绪/筹码数值一致

## Decisions

### D1. 保留源码 + legacy marker

- `@pytest.mark.akshare_legacy`；默认 CI 排除

### D2. 硬门控改为能力检查

- 「是否有任一支持情绪的源」而非「是否启用 akshare」

### D3. optional extra 可选

- 若 packaging 成本高，阶段 C 可仅改配置 + 文档，把 extra 列为 follow-up

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 文档/Agent 仍教人开 akshare | 批量改 user-guide / MRD；保留「紧急加回」一小节 |
| Tushare 全站故障无第三源 | 文档化手动启用 akshare 回滚 |

## Migration Plan

1. 改 example + bootstrap → 本地/Cloud 新环境验证  
2. 改 CLI 门控与文案  
3. 隔离 legacy 测试  
4. L5 trial + S2 baseline  
5. 回滚：在 app.yaml 加回 akshare enabled（文档步骤）

## Open Questions

- OQ-4：是否将 akshare 移出默认 `requirements.txt`
