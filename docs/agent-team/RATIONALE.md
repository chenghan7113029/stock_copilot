# 流程决策记录（RATIONALE）

> 角色 instruction 与 PLAYBOOK 只保留「能判做/不做、能 grep」的那一句；**理由、事故经过、被否方案写在这里**。
> 改规则前读对应小节；执行时不必读本文件。

## 1. 知识蒸馏为什么改成「全部人工咨询」（2026-11-14 用户裁决）

- **决策**：删除手册原有的飞书蒸馏通道（`lark-cli`、答疑群会话、`reference/lark-wiki` 统一版快照、`reference/vac-ba-agent` 的 catalog、`reference/ttd-agent-hub` 的语义层），K1 的「口径确认」与 K2 的「采集」统一改为**问人**：成员整理问题清单 → `agent_teams_send_message` 报 captain → captain 转交 Owner / 业务方 → 答复回填并标来源。
- **理由**：当前客户端**找不到可蒸馏的飞书机器人或飞书号**，那条链路的每一个信源在本机都不存在。保留它只会让 K1/K2 写出「按优先级查信源」的指令，然后成员照着指令去找一个不存在的信源，最后要么空转、要么去猜。
- **代价**：口径类知识从「自动拉取」变成「等人答复」，波次可能带未解决的知识缺口。**这个代价是必须显性化的**，所以设了三条出口：1 小时无答复 → 标「未解决」；缺口进 `docs/improvements/IMPROVEMENTS.md`；`known_unknowns.yaml` 记「待谁确认」。
- **被否方案**：
  1. **保留飞书链路但标「可选」**——被否：可选通道 = 没人走，且指令里留着的路径会让成员反复尝试。
  2. **干脆砍掉知识线（只要 6 角色）**——被否：知识与代码生命周期不同（知识跨波存活），砍掉后「口径从哪来」重新变成隐性知识，回到流程要解决的原问题。
  3. **让 K2 直接读 `ref/` 第三方工程当权威**——被否：`ref/` 是别人项目的快照，不是本业务方的确认；标成「确定」就是把假设洗成事实。

## 2. 为什么只装 4 个机检脚本

- **装**：`agent_team_models.py`（模型 name → id）、`agent_team_preflight.py`（本机环境）、`agent_team_plan.py`（29 条起跑断言 + 收口 R0–R5）、`check_knowledge_source.py`（无来源知识 = 0）。
- **不装**：`verify_traces.py`（判 `artifacts/` run 目录与 idata `query_id` 真实存在——本仓库没有 artifacts 体系、没有 idata）、`check_knowledge_schema.py`（判 `knowledge-design` ↔ yaml ↔ `loader.py` 三处一致——本仓库没有知识 loader）、`scan_prohibitions.py`（判 spec 禁令指向的符号是否还在——本仓库没有「禁令 ↔ 符号」约定）。
- **理由**：这三个脚本的价值在于「断言能红」。给它们造一套假产物（空的 `artifacts/`、假的 loader）会让它们**永远绿**，比不装更危险——假绿是本套流程里最贵的失效形态（见 PLAYBOOK §11 第 13 条）。
- **纪律**：没装的脚本**不许出现在任何闸门或 verify 里**。将来真有了对应产物再装，装了才加门槛。

## 3. 模型分级：pro 只给 2 个角色

- `architect`（方案错则整波返工）与 `reviewer`（漏拦则缺陷进主干）用 `DeepSeek-V4-Pro`；其余 6 个角色用 `DeepSeek-V4.1-Flash`。
- effort：判断与写作质量敏感的角色（PM / K1 / architect / engineer / reviewer）用 `high`；模式化、步骤确定的（K2 采集落库 / qa 设计执行 / integrator 归档）用 `low`。
- **为什么没有 medium**：本机 `deepseek-flash` 的 reasoningEfforts 只有 `off / low / high / max`，没有 `medium` 档。硬写 `medium` 会解析失败；所以手册的 medium 一律落到 low。
- **为什么写 name 不写 id**：`name` 稳定（`DeepSeek-V4-Pro`），`id` 随环境变（`deepseek-v4-pro`）。换机器只需重跑 `scripts/agent_team_models.py`，不改任何文件。
- **踩过的坑**：`list_subagent_models` 只列出 `coding_plan` 子集（本机只返回 `deepseek-flash`），拿它当成员模型权威来源会漏掉 pro 档。

## 4. 编制为什么是 8 角色 / 11 任务

- **T1 与 T7 同一人**：回到 MRD 的动作必须由当初切需求的人做，换人会让「改进点」变成「新需求」。
- **T4 与 T3 并行、QA 不看实现**：先看到代码再写测试，测的就是「代码做了什么」而不是「需求要求什么」。
- **K3 归 QA**：自己采自己验 = 利益冲突，与「QA 盲测不读实现」同理。
- **知识线不并入 implementation / review / repair 闸门**：那些闸门面向代码，套在知识上会路由出 **engineer 的代码 repair**——修错对象（见 §5 第 1 条）。

## 5. 最容易判错的三处

1. **知识 yaml 里值冲突 → `pass`** + captain 立即建 K2 同波整改任务。判 `needs_revision` 会让框架自动生成 engineer 的**代码** repair，而问题在知识文件里——修错对象，还白占一次 repair 轮次。
2. **同一知识硬编码多处且值不一致 → `needs_revision`**。这不是 DRY 问题，是两份口径已经冲突、系统会产出不一致结果。
3. **`medium` / `low` 一律 `pass`**。只有 `blocker` / `high` 触发 `needs_revision`；唯一例外：命中 proposal 的成功 / 失败标准可升 `high`。

## 6. 本次升级遗留的事实（下次换机器/换代时先对账）

- `deepseek-v4-pro` 只在 app 内置 catalog 里实测到，**成员能否真拿到尚未验证**（本会话 `list_subagent_models` 不暴露它）。首次起队若报 `UNKNOWN_MODEL`，按 ENV.md 的回退方案执行并如实记账。
- `openspec` 只能通过 `.cmd` shim 调用（PowerShell 执行策略禁止 `.ps1`）；`agent_team_plan.py` 的 V3 断言会拦忘写 `.cmd` 的 verify。
- 工作区曾因 NTFS 权限缺 `WRITE_OWNER` 导致沙箱无法执行任何命令，修复备份留在 `.acl-recovery/`（可删，但保留着能回滚）。
