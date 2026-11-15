# MRD 文档

市场需求文档（Market Requirements Document）：描述**做什么、为什么做、为谁做**。

## 文档索引

| 文档 | 说明 | 状态 |
|------|------|------|
| [product-overview.md](product-overview.md) | 产品总览、能力域、决策护航与验收标准 | **主文档** |
| [roadmap-todo.md](roadmap-todo.md) | **功能待办清单**（已交付 vs 待实现，便于自检） | 维护中 |
| [competitive-reference.md](competitive-reference.md) | **竞品参考**（GitHub 开源投资助手调研与可借鉴 Feature 映射） | 2026-08-29 |
| [tushare-permission-scan.md](tushare-permission-scan.md) | **Tushare 权限扫描**（2000 积分档已用/未用接口与 Roadmap 映射） | 2026-08-29 |
| [features/value-analysis.md](features/value-analysis.md) | 价值面分析模块需求细则 | 细则 v3 |
| [features/tech-analysis.md](features/tech-analysis.md) | 技术面分析模块需求细则 | 细则 v3 |
| [features/data-source-migration.md](features/data-source-migration.md) | **数据源架构迁移**（三阶段：架构统一 / Tushare 对齐 / AKShare 退役；含 §12 测试与基线方案） | 草案 |
| [../user_story.md](../user_story.md) | 原始用户故事与期望（素材） | 已纳入 product-overview |
| [mrd-v1.md](mrd-v1.md) | **流水线基线**（agent team 的 T1/T7 只认 `mrd-v{N}.md`；章节带 `MRD-x.y` 锚点） | 骨架，待 Owner 填真实内容 |

## 维护规则

- 新增功能需求：先经 OpenSpec `/opsx-propose` 产出 spec，归档后**合并到本目录**
- 每个 feature 可独立成文：`features/<feature-name>.md`
- 变更时在文档顶部「变更记录」追加一行，格式：`YYYY-MM-DD | change-name | 摘要`

## 与 OpenSpec 的关系

```
/opsx-propose → openspec/changes/<name>/specs/  (delta，临时)
/opsx-archive → 合并到 docs/mrd/               (持久，权威)
```

## 流水线基线（agent team）

`docs/agent-team/PLAYBOOK.md` 定义的波次流水线，起点与终点都是 **`mrd-v{N}.md`**：

- **`mrd-v{N}.md`** = 流水线读的基线文件；`proposal.md` 的每条需求必须标注它里面的锚点（形如 `MRD-3.2`），锚点须能在本目录查到。
- **`product-overview.md` 与 `features/*.md`** = 基线的细目与外延：`mrd-v{N}.md` 用「锚点 + 一句话结论」引用它们，不复制正文。
- **谁写**：初始版本由项目负责人（人工）填；后续版本由每波 `T7 改进点沉淀` 产出**建议稿**，Owner 确认后转正。agent 不得自行编写或定稿需求。
- **版本规则**：不覆盖旧版本；演进版只写相对上一版的 diff（新增 / 修改 / 删除），旧锚点编号保持不变，避免历史 proposal 引用失效。
- **锚点体例**：`### 3.2 标题（MRD-3.2）`；不存在的内容标 `TODO` 并登记到 §7 开放问题，不要编。
