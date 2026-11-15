# 共享纪律（所有角色通用）

> `executionPrompt` = 本文件 + `roles/<角色>.md`。每一步都会重发，故只写约束、不写理由（理由见 RATIONALE.md）。

## 硬约束（违反即打回）

1. 不手改 `openspec/specs/`；主规格只能由 integrator 经 `openspec archive` 更新。
2. 不为过闸门放宽 acceptance、改测试断言、删用例。证据必须由命令输出粘贴（命令 + 退出码 + 输出），禁手写或凭记忆；自检链须含 `git rev-parse HEAD`。
3. 需求不确定时查 `docs/mrd/mrd-v{N}.md` 锚点；查不到就停下报告，不发明范围。触及 `OPEN-x` 只声明「未在本波解决」。
4. 只在当前 `feature/<change>` 分支工作；任何角色不得直接向 `main` 提交。
5. **知识不可发明且只能问人**：条目只能来自 ① 人工答复（经 captain 转交）② 仓库一手材料原文。禁止自动抓取、禁止凭库内容推断。
6. **撞到流程疏漏必报**：用 `agent_teams_send_message` 报 captain，不闷头绕过。
7. **提交身份**：`git -c user.name='chenghan7113029' -c user.email='chenghan7113029@users.noreply.github.com' commit`；提交后 `git log -1 --format='%ae'` 自检。
8. **git 串行**：同一时刻只准一个成员做 git 写；禁 `-a`/`-am`，只 `git add <具体路径>`，提交后 `git show --name-only` 核对；禁 `checkout --`/`reset` 还原他人文件。

## 知识线（K1/K2/K3）

- 采集入口只有：人工答复、仓库一手材料（`docs/mrd/`、`docs/design/`、`config/*.yaml`、`openspec/specs/`、现有代码与 `test/`，只读）。
- 提问经 captain 转交，表单式一次问清；问题里不得塞表名/字段名/模块名等实现假设。
- 置信度：人工明确答复 = `确定`；一手材料原文 = `确定`；推断 = `假设`；无来源不入库（记 `config/knowledge/known_unknowns.yaml`）。
- captain 发出问题后 1 小时无答复 → 该知识标「未解决」，缺口记进 `docs/improvements/IMPROVEMENTS.md`，不脑补。

## 通用约定

- 环境事实以 `ENV.md` 为准：`python`（**本机无 `python3`**）/ pytest 9.0.3 / ruff 0.15.17；`openspec` 必须写成 `openspec.cmd`；matplotlib 未安装；不新增未登记依赖。
- 结论须附命令 + 退出码 + 输出；无证据的「通过」按未完成处理。
- 正文 zh-CN；`SHALL` / `#### Scenario` 等结构标记保留英文。
- 只写自己权责边界内的文件。完成后 `git add <具体路径>` + commit（信息含 change 名 + 任务号），不 push。
- `ref/` 只读：禁止 `import`；借鉴走「COPY 进 `src/` + 文件头注释（来源/路径/commit/许可证）+ 补 `test/`」。
- 分层见 `docs/architecture/STRUCTURE.md`：代码 `src/<module>/`、测试 `test/`、QA 用例 `test/qa/`、脚本 `scripts/`、配置 `config/`、知识 `config/knowledge/`。

## 预算纪律

- 本文件 ≤3200 字节、单角色 ≤8000 字节（P1 项）；**新增一条规则必须同时删掉一条等量旧规则**。
- 判据：一句话要么能判「做/不做」，要么能 grep；解释进 RATIONALE.md，不进 prompt。
