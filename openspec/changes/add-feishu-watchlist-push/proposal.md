## Why

通勤路上需要稳定拿到常看股票报告，但不想通过飞书改代码，也不想依赖 Cursor Cloud Agent（开发场景、seed DB，不适合日更报告）。当前能力停在本机 CLI（`sync` / `report dashboard|summary|dual|value|tech` + `watchlist`），没有「定时产出 → 飞书可读」的交付通道。

已对齐的产品定案：家里 PC 常开为 runner；交易日 **09:00 / 13:00 / 17:00** 纯推送；每票**新建**一篇飞书文档（先生成本地 Markdown 再写入）；消息一票一条只带链接；文档顶栏用 `report summary [--narrate]` 综合叙事（方案 A，**不伪装红蓝互驳**）；真·无人值守红蓝叙事与飞书指令对话明确后置。

## What Changes

- 新增「飞书常看推送」管道：对 `watchlist` 每只股票组装一份本地 Markdown，章节顺序固定为：
  1. 综合叙事（`summary`，可选 `--narrate`）
  2. 红蓝证据分桶（`dual`）
  3. 多维看板（`dashboard`）
  4. 价值面（`value`）
  5. 技术面（`tech`）
- 将本地 Markdown **新建**为飞书云文档（不覆盖写同一 URL）；每票向飞书发送一条消息（标题 + 文档链接 + 生成时刻/成败摘要）
- 新增 CLI 入口（如 `python -m apps.cli feishu push --watchlist`），供 Windows 计划任务在交易日三段时刻调用；支持 dry-run（只写本地 MD、不调飞书）
- 新增 `config/app.yaml` 的 `feishu:` 配置段（app_id/app_secret/chat 或 webhook、文档文件夹、是否 narrate 等）；密钥走环境变量，示例写入 `config/app.example.yaml`
- 文档化家里 PC 计划任务安装步骤（交易日判断、防休眠建议）；**本 change 不实现**飞书入站指令、可对话、REST API、无人值守红蓝 Level 1 叙事

**不包含（明确推迟）：**
- 飞书「少量指令 / 可对话」（Phase A.2 / B）
- 覆盖更新同一飞书文档 URL（本 change 固定**每次新建**）
- Cursor Skill 红蓝互驳进管道（无会话则不可调度）
- 自动清理历史飞书文档（保留策略后议，design 中记录即可）

## Capabilities

### New Capabilities
- `feishu-report-composer`：按固定章节把既有 report 输出组装为本地 Markdown（含路径约定与失败降级）
- `feishu-publisher`：飞书开放平台适配——用本地 MD 新建云文档，并向指定会话推送「一票一消息」链接
- `cli-feishu-push`：`feishu push` CLI（`--watchlist` / 单票、可选 sync、可选 narrate、dry-run）及交易日调度说明

### Modified Capabilities
（无——不修改既有 `cli-report-*` / `llm-comprehensive-report` / `red-blue-confrontation` 的需求契约；本 change 只消费其输出）

## Impact

- **新增（预期）**：
  - `src/service/feishu/`（或 `src/service/report/feishu_*`）：composer + publisher
  - `src/apps/cli.py`：`feishu push` 子命令
  - `src/common/config_loader`：解析 `feishu:`
  - `config/app.example.yaml`：`feishu:` 示例
  - `test/service/feishu/`、`test/apps/test_cli_feishu_push.py`（HTTP mock）
  - `docs/user-guide.md`：通勤推送用法；可选 `docs/design/feishu-watchlist-push.md`
  - `docs/mrd/product-overview.md` / `roadmap-todo.md`：交付通道条目
- **依赖**：复用现有 sync/report/watchlist/summary narrate；新增飞书开放平台 HTTP 客户端依赖（具体包在 design 选定）
- **运行环境**：Owner 家里 Windows PC + 计划任务；不引入 NAS/云主机要求
- **架构**：若新增 `service/feishu` 目录，归档后回写 `docs/dev/engineering-conventions.md` 目录表
