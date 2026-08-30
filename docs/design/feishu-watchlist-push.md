# 飞书 dual 推送

> 最后更新：2026-08-15  
> OpenSpec：`add-feishu-watchlist-push`

## 管道

```text
可选 sync → report dual → reports/feishu/{日期}/{slot}/{code}_dual.md
         → lark-cli docs +create → 立刻 lark-cli im +messages-send
```

消息标题（同时作文档标题）：`今日研报_{名称}_{YYYY-MM-DD}_{HHmm}`  
消息正文：文档 URL。

## lark-cli（spike）

本机 apply 时 PATH 无 `lark-cli`。按官方 README：

```text
npx @larksuite/cli@latest install
lark-cli config init
lark-cli auth login --recommend
```

写命令：

```text
lark-cli docs +create --format json --doc-format markdown --title "..." --content "..."
lark-cli im +messages-send --format json --chat-id oc_xxx --msg-type text --content "{\"text\":\"标题\\nURL\"}"
```

> Windows 注意：经 Python `subprocess` 传真实换行给 `--text` / `--content` 会被 CreateProcess 截断。
> 发消息须用 JSON `--content` 转义 `\n`；建文档须用 `--content @相对路径.md`（禁止把整篇 markdown 直接塞进 argv）。

成功信封：`{"ok": true, "data": {...}}`。计划任务须以完成 `auth login` 的同一 Windows 用户运行。不自研 Open API。

## 调度

Windows 计划任务 09:00 / 13:00 / 17:00，分别 `--slot 0900|1300|1700`。交易日 V1：工作日 + `feishu.holidays`。PC 常开后置。
