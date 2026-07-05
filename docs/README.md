# 文档中心

本目录存放项目的**权威文档**。OpenSpec 变更归档后，须将需求与设计内容**合并回此处**，保证 `mrd/` 与 `design/` 始终反映项目全貌。

## 目录说明

| 目录 | 用途 |
|------|------|
| [mrd/](mrd/) | 市场需求文档（MRD）：做什么、为谁做、成功标准 |
| [design/](design/) | 设计文档：架构、模块边界、接口、技术方案 |
| [dev/](dev/) | 开发流程、工程约定与架构（[engineering-conventions.md](dev/engineering-conventions.md)）、[Cloud Agent 移动开发](dev/cloud-agent.md) |
| [superpowers/](superpowers/) | Superpowers 替代工作流（参考） |

## OpenSpec 归档后的文档合并

每次 `/opsx-archive` 完成后，执行以下合并（可由 Agent 或人工完成）：

1. **MRD 合并** — 从 `openspec/changes/archive/<date>-<change>/` 提取需求：
   - `proposal.md` → 更新或追加 `docs/mrd/` 中对应章节
   - `specs/` → 合并需求场景到 MRD 或 `docs/mrd/features/<feature>.md`

2. **Design 合并** — 提取技术设计：
   - `design.md` → 更新 `docs/design/` 中对应方案
   - 新模块/接口 → 更新 [docs/dev/engineering-conventions.md](dev/engineering-conventions.md)

3. **索引维护** — 更新 `docs/mrd/index.md` 和 `docs/design/index.md` 的链接与变更记录

4. **不要**只留在 `openspec/changes/archive/` — archive 是历史快照，**docs/ 才是长期 source of truth**

## 外部参考

本地 clone 的开源项目（不纳入 git）的分析报告见 [design/references/](design/references/)。
