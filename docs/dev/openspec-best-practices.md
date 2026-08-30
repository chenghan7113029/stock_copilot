# OpenSpec 最佳实践（stock_copilot）

> OpenSpec v1.3.1 · Cursor 已集成 · 2026-05-31

---

## 安装状态

本项目已完成初始化：

| 项 | 位置 |
|----|------|
| CLI | `openspec`（全局 npm，v1.3.1） |
| 变更目录 | `openspec/changes/` |
| 主 spec 库 | `openspec/specs/` |
| 项目配置 | `openspec/config.yaml` |
| Cursor 斜杠命令 | `.cursor/commands/opsx-*.md` |
| Cursor Skills | `.cursor/skills/openspec-*/` |

**首次使用前请重启 Cursor**，让斜杠命令生效。

---

## 核心流程（core profile，默认）

```
探索（可选）    提案              实现              归档
─────────  →  ─────────  →  ─────────  →  ─────────
/opsx-explore  /opsx-propose     /opsx-apply      /opsx-archive
```

### 1. 探索 — `/opsx-explore`

**何时用：** 需求不清晰、要调研代码库、比较多种方案。

**做什么：** 只思考、读代码、画图；**不写业务代码**。

**示例：**

```
/opsx-explore 价值面分析层应该放在哪个模块？
```

想清楚了再进入 propose：

```
/opsx-propose add-value-analysis-layer
```

---

### 2. 提案 — `/opsx-propose <change-name>`

**何时用：** 需求已明确，一次性生成全部规划产物。

**产出目录：** `openspec/changes/<change-name>/`

| 文件 | 含义 |
|------|------|
| `proposal.md` | 为什么做、做什么、影响范围 |
| `specs/` | 需求与场景（delta spec） |
| `design.md` | 技术方案、模块边界 |
| `tasks.md` | 可勾选实现清单 |

**示例：**

```
/opsx-propose add-value-analysis-layer
```

或直接用自然语言（Agent 会推导 kebab-case 名称）：

```
/opsx-propose 接入价值面分析层，与技术面并行输出
```

**你要做的：** 读一遍 proposal + specs + design，确认无误后再 apply。有偏差直接在对应 md 里改，或让 Agent 更新 artifact。

---

### 3. 实现 — `/opsx-apply [change-name]`

**何时用：** 规划产物齐全，`tasks.md` 已就绪。

**做什么：** 按 `tasks.md` 逐项实现，勾选 checkbox。

**示例：**

```
/opsx-apply add-value-analysis-layer
```

若只有一个 active change，可省略名称：

```
/opsx-apply
```

**最佳实践：**

- 实现前**清空或新开 chat**，减少上下文噪音（OpenSpec 官方建议）
- 遇到 plan 未覆盖的问题 → 先改 `design.md` / `tasks.md`，再继续
- 一次只推进一个 change（`openspec list` 查看当前变更）
- **测试门禁（硬约束）**：相关 pytest / 脚本未通过前，不得勾选完成、不得声称 apply 完成；禁止「既有无关失败」默认放行（除非 Owner 显式豁免并登记）

---

### 4. 归档 — `/opsx-archive [change-name]`

**何时用：** 代码写完、**验证门禁已通过**、准备合并。

**硬前置：** `openspec/config.yaml` 完成判定 — 默认须跑通本 change 相关测试 + `pytest -q -m "not network"`（及 tasks 声明的额外门禁）。测试失败时**不得**默认归档。

**做什么：**

- 将 delta spec 合并进 `openspec/specs/`
- 移动 change 到 `openspec/changes/archive/YYYY-MM-DD-<name>/`

**归档后必做 — 合并到 docs（项目规范）：**

| OpenSpec 产物 | 合并目标 |
|---------------|----------|
| `proposal.md`、`specs/` | `docs/mrd/`（更新或新增 `features/<name>.md`） |
| `design.md` | `docs/design/`（更新架构或专项设计文档） |
| 索引 | 更新 `docs/mrd/README.md`、`docs/design/README.md` 变更记录 |

详见 [docs/README.md](../README.md)。

**示例：**

```
/opsx-archive add-value-analysis-layer
```

---

## 目录结构速查

```
stock_copilot/
├── config/                      # 配置文件
├── docs/
│   ├── mrd/                     # 市场需求（权威）
│   ├── design/                  # 专项设计（权威）
│   └── dev/
│       └── engineering-conventions.md  # 工程约定与架构（唯一真源）
├── openspec/
│   ├── config.yaml
│   ├── specs/                   # 累积 spec（归档合并）
│   └── changes/                 # 进行中的变更 / archive/
├── ref/                         # 外部参考 clone（gitignore）
├── reports/                     # 分析报告产出（gitignore）
├── src/                         # 源代码（扁平：apps/, service/, …）
├── test/
├── scripts/
└── log/
```

---

## 常用 CLI 命令

在 Agent 对话外，终端也可管理变更：

```bash
openspec list                    # 查看 active changes
openspec status --change <name>  # 查看 artifact 进度
openspec new change <name>       # 手动创建 change（通常用 /opsx-propose 即可）
openspec update                  # 升级后刷新 .cursor/ 里的 skills/commands
```

---

## 命名规范

change 名称用 **kebab-case**，见名知意：

| 推荐 | 避免 |
|------|------|
| `add-value-analysis-layer` | `feature-1` |
| `fix-fundamental-adapter-null` | `update` |
| `integrate-financetoolkit-ratios` | `wip` |

---

## 10 条最佳实践

1. **先 spec 后代码** — 没有 `tasks.md` 就不要 `/opsx-apply`
2. **小 change 快迭代** — 大功能拆多个 change（如「数据层」「分析层」「报告层」分开）
3. **善用 explore** — brownfield 项目（如本仓库）先 explore 再 propose
4. **读 config 上下文** — `openspec/config.yaml` 已注入本项目架构约束，改项目惯例时同步更新
5. **实现前清上下文** — 新开 chat + 附上 change 路径，避免旧对话干扰
6. **tasks 要可验证** — 每步写清文件路径和测试方式
7. **需求变更走 artifact** — 改 specs/design/tasks，不要 silent fix 代码
8. **归档/完成前跑测试** — Agent 勾选 tasks ≠ 完成；相关测试未通过不得默认算 apply/archive 完成（见 `openspec/config.yaml` 完成判定硬约束）；要求贴出 pytest/门禁命令输出
9. **并行 change 要显式指定名** — `/opsx-apply <name>`，避免搞混
10. **定期 `openspec update`** — CLI 升级后刷新 Cursor 集成

---

## 三种典型模式

### 快速功能（最常用）

```
/opsx-propose add-xxx  →  审阅产物  →  /opsx-apply  →  测试  →  /opsx-archive
```

适合：边界清晰的小功能、bug fix。

### 探索驱动

```
/opsx-explore  →  /opsx-propose  →  /opsx-apply  →  /opsx-archive
```

适合：价值面接入、架构选型等不确定需求。

### 并行中断

```
Change A: /opsx-apply（进行中，被 urgent bug 打断）
Change B: /opsx-propose fix-xxx  →  /opsx-apply  →  /opsx-archive
Change A: /opsx-apply add-value-analysis-layer   # 显式指定名称继续
```

---

## 扩展工作流（可选）

当前项目使用 **core profile**（4 个命令）。若需要更细粒度控制，可启用扩展命令：

```bash
openspec config profile    # 交互选择 new / continue / ff / verify 等
openspec update
```

| 扩展命令 | 作用 |
|----------|------|
| `/opsx-new` | 只建 change 脚手架 |
| `/opsx-continue` | 逐步生成下一个 artifact |
| `/opsx-ff` | 一次性生成全部 artifact |
| `/opsx-verify` | 实现 vs spec 三方验证 |
| `/opsx-sync` | 手动合并 delta spec |
| `/opsx-onboard` | 交互式教程（约 15–30 分钟） |

首次学习可跑：

```
/opsx-onboard
```

---

## 与本项目第一个 change 的建议

已有方案文档 `stock_copilot-价值面分析层接入方案.md`，建议作为 brownfield 参考，**不要直接当 OpenSpec artifact**。推荐起手：

```
/opsx-explore 阅读 stock_copilot-价值面分析层接入方案.md，
确认 valueinvest 与 FinanceToolkit 的集成边界

/opsx-propose add-value-analysis-layer
```

审阅生成的 `proposal.md` / `design.md` 时，对照原方案查漏补缺，再 `/opsx-apply`。

---

## 故障排查

| 问题 | 处理 |
|------|------|
| 斜杠命令不识别 | 重启 Cursor；运行 `openspec update` |
| `Change not found` | `openspec list` 查名称；命令里显式带 `<name>` |
| 产物质量差 | 丰富 `openspec/config.yaml` 的 context/rules |
| CLI 版本过旧 | `npm install -g @fission-ai/openspec@latest` 然后 `openspec update` |

---

## 相关链接

- [OpenSpec GitHub](https://github.com/Fission-AI/OpenSpec)
- [Workflows 文档](https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md)
- [Commands 参考](https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md)
