# MRD 文档

市场需求文档（Market Requirements Document）：描述**做什么、为什么做、为谁做**。

## 文档索引

| 文档 | 说明 | 状态 |
|------|------|------|
| [product-overview.md](product-overview.md) | 产品总览、能力域、决策护航与验收标准 | **主文档** |
| [roadmap-todo.md](roadmap-todo.md) | **功能待办清单**（已交付 vs 待实现，便于自检） | 维护中 |
| [features/value-analysis.md](features/value-analysis.md) | 价值面分析模块需求细则 | 细则 v3 |
| [features/tech-analysis.md](features/tech-analysis.md) | 技术面分析模块需求细则 | 细则 v3 |
| [features/data-source-migration.md](features/data-source-migration.md) | **数据源架构迁移**（三阶段：架构统一 / Tushare 对齐 / AKShare 退役；含 §12 测试与基线方案） | 草案 |
| [../user_story.md](../user_story.md) | 原始用户故事与期望（素材） | 已纳入 product-overview |

## 维护规则

- 新增功能需求：先经 OpenSpec `/opsx-propose` 产出 spec，归档后**合并到本目录**
- 每个 feature 可独立成文：`features/<feature-name>.md`
- 变更时在文档顶部「变更记录」追加一行，格式：`YYYY-MM-DD | change-name | 摘要`

## 与 OpenSpec 的关系

```
/opsx-propose → openspec/changes/<name>/specs/  (delta，临时)
/opsx-archive → 合并到 docs/mrd/               (持久，权威)
```
