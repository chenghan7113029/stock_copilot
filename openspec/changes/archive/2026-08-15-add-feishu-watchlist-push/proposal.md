## Why

通勤路上需要稳定拿到常看股票的红蓝证据分桶（`report dual`），但不想在飞书里改代码，也不想依赖 Cursor Cloud Agent。上一版实现过重：五节拼装 + 自研开放平台 HTTP（token / 素材上传 / 异步导入 / 轮询），与「把已有 dual.md 送进飞书」的真实需求不匹配，已回退代码。

本 change 重新对焦为：**只推 dual**；每份本地 `*_dual.md` **新建**一篇飞书文档；生成成功后立刻发一条消息；飞书侧用官方 **`lark-cli`**，不自研 Open API 客户端。触发仍用家里 Windows 计划任务；PC 常开/休眠问题后置。

## What Changes

- 复用既有 `report dual`（单票或 `--watchlist`）产出本地 `{code}_dual.md`，**不再**组装 summary / dashboard / value / tech，也不做综合叙事或红蓝 Level 1 伪装
- 每份 dual.md 调用 `lark-cli` **新建**一篇云文档
- 每新建成功一篇，立即发一条飞书消息：
  - 标题：`今日研报_{股票名称}_{日期}_{HHmm}`（日期当天 `YYYY-MM-DD`，时间为推送槽如 `0900`）
  - 正文：该飞书文档链接（一条消息只对应一只股票）
- CLI 入口（如 `python -m apps.cli feishu push --watchlist`）供 Windows 计划任务调用；`--dry-run` 只写/确认本地 dual.md，不调用 `lark-cli` 写接口
- 配置记录 `lark-cli` 路径、目标会话（chat/user）、可选文档文件夹；**认证交给 `lark-cli auth login`**，本仓库不实现 tenant_access_token / 自研 HTTP
- 文档化计划任务安装；**本 change 不实现**飞书入站指令、覆盖同一文档、PC 常开方案、无人值守红蓝 Level 1

**不包含（明确推迟）：**
- 飞书「少量指令 / 可对话」
- 覆盖更新同一飞书文档 URL（仍每次新建）
- 自研飞书 Open API（token、导入任务轮询等）
- Cursor Skill 红蓝互驳进管道
- 自动清理历史飞书文档
- 家里 PC 休眠/未登录的可靠补推（仅文档提示）

## Capabilities

### New Capabilities
- `feishu-report-composer`：确保每票有一份与 `report dual` 同源的本地 `*_dual.md`（路径约定与单票失败不阻断批次）
- `feishu-publisher`：通过 **`lark-cli`** 将 dual.md 新建为云文档，并发送「标题 + 仅链接」消息
- `cli-feishu-push`：`feishu push` CLI（`--watchlist` / 单票、可选 sync、dry-run）及 Windows 计划任务说明

### Modified Capabilities
（无——不修改既有 `cli-report-dual` 契约；本 change 只消费其 Markdown 输出）

## Impact

- **新增（预期）**：薄封装调用 `report dual` + `lark-cli`；CLI `feishu push`；配置示例；user-guide 计划任务；测试以 mock `lark-cli` 子进程为主
- **依赖**：本机已安装并可登录的 [lark-cli](https://github.com/larksuite/cli)；现有 `sync` / `report dual` / `watchlist`
- **运行环境**：Owner 家里 Windows PC + 计划任务
- **架构**：若新增 `service/feishu`，归档后回写 engineering-conventions 目录表
