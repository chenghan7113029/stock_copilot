## Context

用户通勤只读红蓝证据分桶。执行端仍是家里 Windows PC + 计划任务。仓库已有 `watchlist`、`sync --watchlist`、`report dual`（本地 `{code}_dual.md`）。

上一版（已回退）问题：五节拼装过重；自研 Open API（tenant token + 素材上传 + 导入任务轮询）太重。本版改为消费 dual.md，飞书操作全部走官方 `lark-cli`。

## Goals / Non-Goals

**Goals:**
- 计划任务可调用的管道：可选 sync → 生成/定位 dual.md → `lark-cli` 新建文档 → 立刻发一条「标题 + 链接」消息
- 本地 dual.md 可复现；飞书失败时可凭本地文件重试
- 单票失败不阻断同批次其他票
- dry-run 不调用 `lark-cli` 的创建文档 / 发消息命令

**Non-Goals:**
- 自研飞书 Open API / SDK
- 五节报告、summary narrate、红蓝 Level 1 Skill
- 覆盖更新同一文档 URL
- 飞书入站指令 / 可对话
- PC 常开/防休眠的工程方案（仅文档提示）
- REST API / Web 看板
- 自动清理历史飞书文档

## Decisions

### 决策 1：内容只推 dual

**选择**：管道只消费与 `python -m apps.cli report dual` 同源的 Markdown。不拼 summary / dashboard / value / tech。

**理由**：通勤可读；与用户定案一致。

### 决策 2：本地产物沿用 dual 文件约定

**选择**：先跑（或复用）`report dual`，得到 `{code}_dual.md`。推荐落点：

`reports/feishu/{YYYY-MM-DD}/{slot}/{code}_dual.md`

（与现有 `--watchlist -o 目录` 的 `{code}_dual.md` 命名一致，外加日期目录避免隔日覆盖。）

**理由**：不再做五节 composer；「每个 dual.md 变成一个飞书文档」字面落地。

### 决策 3：飞书操作只通过 lark-cli

**选择**：Python 用 `subprocess` 调用本机 `lark-cli`（路径可配置），不直接打 `open.feishu.cn`。

预期命令（apply 时以当时 CLI 帮助为准，钉进 design 备注）：

```text
lark-cli docs +create --format json --doc-format markdown --title "<标题>" --content "<dual.md 正文>" [--folder-token ...]
lark-cli im +messages-send --format json --chat-id "<chat_id>" --text "<标题>\n<doc_url>"
```

本机 apply 时 PATH 上无 `lark-cli`；以上摘自官方 README（https://github.com/larksuite/cli）。成功响应信封为 `{"ok": true, "data": {...}}`，从 data 中解析 `doc_url` / `url`。

**认证**：依赖用户事先 `lark-cli auth login`；计划任务以**同一 Windows 用户**运行，以便复用已登录会话。本 change 不实现 app_id/app_secret HTTP。

**缺 lark-cli / 未登录**：非 dry-run 明确失败并提示安装与 `auth login`，不假装发送成功。

**理由**：用户明确拒绝自研 API；官方 CLI 已覆盖建文档与发消息。

**备选（拒绝）**：自研 urllib Open API（上一版）。

### 决策 4：消息形态

**选择**：每成功新建一篇文档，立即发恰好一条消息。

- 标题：`今日研报_{股票名称}_{日期}_{HHmm}`
  - 名称为 watchlist 中的 `name`；缺失时回退为股票代码
  - 日期：本地日历日 `YYYY-MM-DD`；时间为本次 slot（`0900` / `1300` / `1700` 或 `--slot`）
- 正文：仅飞书文档 URL（第一行标题、第二行链接）
- 一条消息只对应一只股票；**生成一篇推送一篇**

文档标题与消息标题使用同一字符串。

### 决策 5：调度 — Windows 计划任务三段时刻

**选择**：09:00 / 13:00 / 17:00 由任务计划程序各调一次（`--slot 0900` 等）。标题含时间，不会撞名。PC 常开问题后置。CLI 非常驻。交易日门闩 V1：工作日 + 可配置休市日。

### 决策 6：sync 默认

**选择**：`sync_before_push` 默认 true（推 dual 前先 `sync --watchlist`，可选 `--realtime`）。无 narrate。

### 决策 7：失败策略

**选择**：单票 dual 生成失败 → 该票不建文档、不发「成功链接」；可选发失败消息（若 lark-cli 消息通道可用）或仅 stderr。建文档失败同样不发伪造链接。整批部分失败退出码非 0，已成功票保留。

### 决策 8：模块落点

**选择**：
- `src/service/feishu/publisher.py` — 封装 `lark-cli` 调用（可注入命令执行器便于测试）
- `src/service/feishu/pipeline.py` — sync → dual.md → create+send
- `src/apps/cli.py` — `feishu push`
- 测试 mock 子进程，不打真实飞书

## Risks / Trade-offs

- **[风险] 计划任务用户与 `lark-cli auth login` 会话不一致** → **缓解**：user-guide 写明「以登录用户运行」；apply 时 spike `lark-cli` 凭证存放位置
- **[风险] lark-cli 子命令参数随版本变化** → **缓解**：publisher 集中一处；任务含 spike 记录实际命令行
- **[风险] 每次新建云盘膨胀** → **接受**（用户选择每次新建）；不自动删
- **[风险] 家里 PC 休眠漏推** → **接受后置**；user-guide 仅提示防休眠
- **[风险] 股票无中文名** → **缓解**：标题回退代码

## Migration Plan

- 无 DB schema 变更
- 依赖本机 `lark-cli`；dry-run 可不装
- 回滚：移除 `service/feishu`、CLI 子命令与配置示例

## Open Questions

- `lark-cli docs +create` 是否支持 `--file`——本机未装 CLI；按官方 README 使用 `--doc-format markdown --content` + `--title`
- 消息发到群 `chat_id` 还是发给自己 `user-id`——配置项，默认 chat_id
