# Superpowers 执行 OpenSpec 风格开发 — 最佳实践

> **已安装官方 OpenSpec。** 请优先阅读 [OpenSpec 最佳实践](../openspec-best-practices.md)。  
> 下文为不依赖 OpenSpec CLI 的 Superpowers 替代方案，供参考。

> 不安装 OpenSpec CLI，用现有 Superpowers skill 链实现「先 spec、后代码、可归档」的 spec-driven 开发。

---

## 核心理念对照

| OpenSpec 原则 | Superpowers 对应 |
|---------------|------------------|
| 先对齐再写代码 | `brainstorming` 的 HARD-GATE：未批准 design 禁止实现 |
| 持久化 spec（不在聊天里） | 写入 `docs/superpowers/specs/` 和 `plans/` |
| 一次变更一个文件夹 | 每个 feature 一对 spec + plan 文件 |
| propose → apply → archive | brainstorming → writing-plans → executing-plans → finishing |

---

## 标准工作流（4 阶段）

```
探索/提案          写计划              实现                收尾
─────────    →    ─────────    →    ─────────    →    ─────────
brainstorming     writing-plans     executing-plans     finishing-a-development-branch
(/opsx:explore)   (/opsx:propose)   (/opsx:apply)       (/opsx:archive)
```

### 阶段 0：准备（可选但推荐）

**Skill:** `using-git-worktrees`

- 新功能在独立 worktree / 分支上开发，避免污染 main
- 对话开头说：「用 using-git-worktrees 为 `<feature>` 建隔离工作区」

### 阶段 1：探索 & 提案 — `/opsx:explore` + `/opsx:propose`

**Skill:** `brainstorming`

**你对 Agent 说：**

```
用 brainstorming skill，帮我设计「<功能描述>」。
先探索项目上下文，逐项确认需求，给出 2-3 种方案，等我批准后再写 spec 文件。
```

**Agent 应产出：**

```
docs/superpowers/specs/YYYY-MM-DD-<feature>-design.md
```

**你要做的：**

- [ ] 读完 spec，确认范围、边界、成功标准
- [ ] 有歧义就继续改 spec，**不要**说「先做着看」
- [ ] 明确回复「spec 批准，进入计划阶段」

> **HARD-GATE：** 此阶段禁止写业务代码。简单改动也要走（可以很短，但不能跳过）。

### 阶段 2：写实现计划 — `/opsx:propose` 的 tasks.md

**Skill:** `writing-plans`

**你对 Agent 说：**

```
spec 已批准。用 writing-plans skill 基于
docs/superpowers/specs/YYYY-MM-DD-<feature>-design.md
写实现计划。
```

**Agent 应产出：**

```
docs/superpowers/plans/YYYY-MM-DD-<feature>.md
```

**计划质量检查（你快速扫一眼）：**

- [ ] 每个 task 有明确文件路径（Create / Modify / Test）
- [ ] 步骤粒度 2–5 分钟（写测试 → 跑失败 → 实现 → 跑通过）
- [ ] 复杂功能已拆成独立 task（适合 subagent 并行）

### 阶段 3：实现 — `/opsx:apply`

**Skill 选择：**

| 场景 | 用哪个 skill |
|------|-------------|
| 当前会话、task 相对独立 | `subagent-driven-development`（推荐，Cursor 支持 subagent） |
| 另开新会话执行 | `executing-plans` |
| 小改动、单文件 | 直接按计划逐步做，但仍引用 plan 文件 |

**你对 Agent 说：**

```
用 subagent-driven-development skill，按计划执行：
docs/superpowers/plans/YYYY-MM-DD-<feature>.md
```

**实现期间：**

- Agent 按 plan 勾选 checkbox，不应跳过验证步骤
- 遇到 plan 未覆盖的 blocker → 停下来，更新 spec/plan 再继续
- 发现 spec 有误 → 回到阶段 1 改 spec，**不要** silent fix

### 阶段 4：验证 & 收尾 — `/opsx:verify` + `/opsx:archive`

**Skills:** `verification-before-completion` → `finishing-a-development-branch`

**你对 Agent 说：**

```
实现完成。先跑完整测试验证，再用 finishing-a-development-branch 收尾。
```

**收尾选项（由 skill 引导）：**

- 合并到 main / 开 PR / 保留分支继续迭代
- 确认测试、lint 有实际输出证据（不能只听 Agent 说「通过了」）

**手动归档（OpenSpec archive 等价）：**

- 在 spec 文件顶部加 `status: done` 和完成日期
- 或将 `specs/` + `plans/` 移入 `docs/superpowers/archive/YYYY-MM-DD-<feature>/`

---

## 推荐目录结构

```
docs/superpowers/
├── specs/                          # 设计 & 需求（= OpenSpec specs + design）
│   └── 2026-05-31-价值面分析-design.md
├── plans/                          # 实现任务清单（= OpenSpec tasks.md）
│   └── 2026-05-31-价值面分析.md
└── archive/                        # 已完成变更（= OpenSpec archive/）
    └── 2026-05-31-价值面分析/
        ├── design.md
        └── plan.md
```

---

## 对话模板（复制即用）

### 开新功能

```
我要做：<一句话描述>

请严格按 Superpowers OpenSpec 流程：
1. brainstorming → 写 spec 到 docs/superpowers/specs/，等我批准
2. writing-plans → 写 plan 到 docs/superpowers/plans/
3. 我确认后再 subagent-driven-development 实现
```

### 中途改需求（delta spec）

```
需求变更：<具体变化>

请先更新 docs/superpowers/specs/<file>.md 的「变更记录」章节，
我确认后再更新 plan 和代码。不要直接改代码。
```

### 续做未完成的功能

```
继续实现 docs/superpowers/plans/<file>.md，
从第 N 个 task 开始，用 executing-plans skill。
```

---

## 10 条最佳实践

1. **Spec 是 source of truth** — 聊天说了不算，文件写了才算
2. **一次只做一个 change** — 不要在一个会话里混多个 feature 的 spec/plan
3. **批准门槛** — spec 和 plan 各需一次明确批准，再进入下一阶段
4. **先 worktree 后代码** — Brownfield 项目（如 stock_copilot）尤其重要
5. **Plan 要够细** — 模糊 plan = Agent 猜，猜 = 返工
6. **改需求走 spec** — 禁止「口头加功能」；在 spec 里写 delta，再改 plan
7. **验证要有证据** — 测试/lint 必须跑完并贴结果，参见 `verification-before-completion`
8. **大功能拆 plan** — 多子系统各自独立 plan，每个都能单独交付
9. **会话 hygiene** — 实现阶段开新 chat 时，第一条消息附上 spec + plan 文件路径
10. **归档别省** — 完成的 spec/plan 移入 archive，方便日后 onboarding 和复盘

---

## 与官方 OpenSpec 的差异

| 项目 | Superpowers 方案 | 官方 OpenSpec |
|------|-----------------|---------------|
| 安装 | 已有 skill，零依赖 | `npm i -g @fission-ai/openspec` |
| 命令 | 对话中点名 skill | `/opsx-propose` 等斜杠命令 |
| 目录 | `docs/superpowers/` | `openspec/changes/` |
| Delta spec | 手动在 spec 里加「变更记录」 | CLI 自动管理 delta |
| 验证命令 | 项目自带 pytest 等 | `/opsx-verify` |

**何时改用官方 OpenSpec：** 需要 CLI 校验、团队统一斜杠命令、或 delta spec 自动 sync 时。

---

## 快速参考：Skill 触发词

| 意图 | 说法 |
|------|------|
| 探索想法 | 「用 brainstorming 探索…」 |
| 写 spec | 「用 brainstorming，最后写 design doc」 |
| 写 plan | 「用 writing-plans 基于 spec 写计划」 |
| 实现 | 「用 subagent-driven-development 执行 plan」 |
| 隔离分支 | 「用 using-git-worktrees」 |
| 声称完成前 | 「用 verification-before-completion 验证」 |
| 合并/PR | 「用 finishing-a-development-branch 收尾」 |

---

## 第一次试跑建议

选一个**小、边界清晰**的任务（例如：给某个模块加一个配置项），完整走一遍四阶段，熟悉节奏后再用于「价值面分析层接入」这类大改动。

预计耗时：小功能 1–2 小时（含 spec 讨论），大功能拆成多个 change 分别走。
