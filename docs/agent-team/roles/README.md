# 角色 Instruction 目录

> 每个角色的完整 instruction（MetaGPT 颗粒度），起波时拼进成员的 `executionPrompt`。

## 结构

```text
docs/agent-team/roles/
├── README.md               # 本文件
├── _shared.md              # 共享纪律（= MetaGPT 的 ROLE_INSTRUCTION），所有角色通用
├── product-manager.md      # 产品经理：case 牵引 + 拆解 + 需求澄清 + 规格 + 闭环两端（T1/T7）
├── architect.md            # 方案架构 + 拆任务（T2）
├── knowledge-architect.md  # 知识架构师：知识缺口识别 + 分层分级（K1，口径问人）
├── engineer.md             # 实现（T3）
├── knowledge-engineer.md   # 知识工程师：知识采集（K2，人工咨询 + 仓库一手材料）
├── qa.md                   # QA：测试设计（T4）+ 执行报告（T5）+ case 回归验证（K3）
├── reviewer.md             # 评审（T6）
└── integrator.md           # 归档 + 合并回 main（T8）
```

## 用法

```text
executionPrompt = [ _shared.md 全文 ] + "\n\n" + [ roles/<角色>.md 全文 ]
```

共享纪律（不手改 specs、附证据、走 feature 分支、环境约束…）+ 角色专属 SOP（身份/工作流/产出契约/完成定义/边界/失败定义）。

```powershell
$shared = Get-Content docs/agent-team/roles/_shared.md -Raw -Encoding UTF8
$role   = Get-Content docs/agent-team/roles/engineer.md -Raw -Encoding UTF8
$prompt = $shared + "`n`n" + $role
```

## 体量预算

- `_shared.md` ≤3200 字节，单个角色文件 ≤8000 字节；用 `python -c "print(len(open(r'<路径>','rb').read()))"` 实测。
- **新增一条规则必须同时删掉一条等量旧规则**；解释、举例、事故复盘一律进 `docs/agent-team/RATIONALE.md`，本目录只留能判「做/不做」或能 grep 的一句。
- 字节只是代理指标：真正的载荷是「需要同时 hold 的判断分支数」。边界情况宁可写进 `templates/` 的机械清单，也不写进角色 prompt。

## 本项目的校准

1. **`captain` 没有独立 instruction 文件**：captain 是起波编排者（DSH 会话本身），职责/边界/失败定义见 `docs/agent-team/PLAYBOOK.md` §5。
2. **skill 按本机实际安装校准**（2026-11-15 逐个确认）：
   - **已安装并使用**：`ponytail-review`（reviewer 主方法）、`requirements-analysis`（PM/KA/KE）、`architecting-solutions` 与 `system-architect`（architect/KA，仅信息架构）。
   - **用现有替代**：`business-analyst` 未装，由 `grillme` + `requirements-analysis` + `brainstorming` 承担。
   - **本波不装（不适用）**：`ai-mlops` / `senior-ml-engineer` / `monitoring-observability`（无模型训练与在线服务）。
   - 安装方式：`npx skills add <owner/repo@skill> -g -y` → 用户级 `~/.agents/skills`（不入本仓库）。方法论要点仍内联在对应角色文件，外部 skill 讲解与内联冲突时以角色文件为准。
3. **知识线不走飞书机器人**：本项目没有可蒸馏的飞书机器人或飞书号。知识采集只有两个入口——① 人工咨询答复（经 captain 转交）；② 仓库内一手材料（只读）。口径见 `qa.md` 的 K3 条款。

## 与 PLAYBOOK 的关系

- `docs/agent-team/PLAYBOOK.md` §5 是**人读的索引表**（一眼看全 8 名成员 / 11 个任务的职责与边界）。
- 本目录是**给成员读的完整 instruction**（机器塞进 executionPrompt 的那份）。
- 两者必须保持一致：改角色职责时，两边同步改。

## 维护

- 角色指令是「流程代码」，随流程演进 git 版本化、可 diff。
- 为什么某条规则长这样（事故经过、被否方案）查 `docs/agent-team/RATIONALE.md` 对应小节；本目录只保留可执行的那一句。
- 试跑暴露的问题（如 integrator 的 git 提交范围、reviewer 的「部分覆盖」分档）已并入对应角色文件的产出契约/失败定义。
- 改完按本仓库约定的写法自查一遍（命令、路径、目录名必须与 `ENV.md` / `STRUCTURE.md` 一致），再进下一波。
