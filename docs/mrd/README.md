# MRD 文档

市场需求文档（Market Requirements Document）：描述**做什么、为什么做、为谁做**。

## 文档索引

| 文档 | 说明 | 状态 |
|------|------|------|
| [product-overview.md](product-overview.md) | 产品总览、能力域、决策护航与验收标准 | **主文档** |
| [features/value-analysis.md](features/value-analysis.md) | 价值面分析模块需求细则 | 细则 v1（待 propose） |
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
