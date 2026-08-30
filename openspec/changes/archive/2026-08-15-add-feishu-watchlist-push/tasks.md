## 1. 前置与配置

- [x] 1.1 Spike：本机 PATH 无 `lark-cli`；按官方 README 记录 `docs +create --doc-format markdown --content` 与 `im +messages-send --text`；写入 `docs/design/feishu-watchlist-push.md`
- [x] 1.2 在 `config/app.example.yaml` 增加 `feishu:` 示例（`lark_cli` 路径、`chat_id`、可选 `folder_token`、`sync_before_push`、`trading_days_only`、`holidays`）；**不要**把自研 Open API 的 app_secret 作为主路径
- [x] 1.3 Modify `src/common/config_loader.py`：解析上述 `feishu:`
- [x] 1.4 Create 交易日判断 V1（工作日 + 可配置休市日）及单元测试

## 2. 本地 dual.md

- [x] 2.1 管道调用既有 `report dual`（同进程 `run_report_dual` 或等价），写入 `reports/feishu/{date}/{slot}/{code}_dual.md`
- [x] 2.2 Create 测试：路径含日期与 `_dual`；单票失败不阻断批次

## 3. lark-cli publisher

- [x] 3.1 Create publisher：可注入的命令执行器；dry-run 不调用；缺二进制/未登录明确失败
- [x] 3.2 新建文档后立即发消息；标题 `今日研报_{名称}_{YYYY-MM-DD}_{HHmm}`；正文含文档链接
- [x] 3.3 Create 测试：mock 子进程（create 成功、cli 缺失、dry-run 不写、create 失败不发成功链接）

## 4. Pipeline 与 CLI

- [x] 4.1 Create pipeline：可选 sync → dual.md → create+send；部分失败汇总
- [x] 4.2 Modify `src/apps/cli.py`：`feishu push`（单票/`--watchlist`、`--dry-run`、sync 开关）
- [x] 4.3 Create CLI 测试：dry-run、非交易日 skip、lark-cli 不可用非 0 退出

## 5. 文档

- [x] 5.1 Modify `docs/user-guide.md`：`lark-cli` 安装与 `auth login`、`feishu push --dry-run`、Windows 计划任务 09:00/13:00/17:00、须与登录用户一致、防休眠仅作提示
- [x] 5.2 Create `docs/design/feishu-watchlist-push.md`
- [x] 5.3 Modify product-overview / roadmap-todo：登记飞书 dual 推送
- [x] 5.4 若新增 `src/service/feishu/`：Modify engineering-conventions 目录表

## 6. 验收

- [x] 6.1 本地 dry-run 写出 `reports/feishu/2026-08-14/1700/600519_dual.md`
- [x] 6.2 （可选）非 dry-run 单票：确认新建文档 + 消息标题/链接 — 已用 lark-cli 建文档并向 `user_id` 自聊发送，用户确认已收到
- [x] 6.3 相关 pytest 全部通过

## 7. 归档

- [x] 7.1 确认实现与文档任务已完成（归档见 7.2）
- [x] 7.2 `/opsx-archive add-feishu-watchlist-push`，同步 specs，合并文档要点
