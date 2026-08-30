## ADDED Requirements

### Requirement: 用 lark-cli 将 dual.md 新建为飞书云文档
系统 SHALL 读取本地 `{code}_dual.md`，通过本机 **`lark-cli`**（MUST NOT 自研飞书 Open API HTTP 客户端作为默认路径）**新建**一篇云文档。新建成功后 SHALL 得到可打开的文档链接。默认行为 MUST NOT 覆盖更新既有文档 URL。

#### Scenario: 新建成功
- **WHEN** `lark-cli` 已安装且已登录，且 dual.md 存在
- **THEN** 系统 SHALL 创建新文档并得到文档 URL，且该 URL SHALL 对应当次新建资源

#### Scenario: lark-cli 缺失或未登录
- **WHEN** 找不到 `lark-cli` 可执行文件，或命令因未授权失败，且非 dry-run
- **THEN** 系统 SHALL 失败并给出安装 / `lark-cli auth login` 提示，SHALL NOT 假装发送成功

### Requirement: 生成一篇立即推送一条消息
每只股票在文档新建成功后，系统 SHALL **立即**向配置的接收目标发送恰好一条消息。接收目标 MUST 为 `feishu.user_id`（自聊 open_id）或 `feishu.chat_id`（群会话）之一；二者同时配置时 MUST 优先 `user_id`。消息标题 MUST 为 `今日研报_{股票名称}_{日期}_{HHmm}`（名称为 watchlist 名称，缺失时用股票代码；日期为当天 `YYYY-MM-DD`；`HHmm` 为本次推送槽）。消息正文 MUST 包含该新建文档的链接，且 MUST NOT 再附带 dual 全文。一条消息 MUST 只对应一只股票。

#### Scenario: 单票消息
- **WHEN** `600519`（名称「贵州茅台」）在 `2026-08-18` 的 `1700` 槽文档新建成功
- **THEN** 系统 SHALL 立即发送恰好一条消息，标题 SHALL 为 `今日研报_贵州茅台_2026-08-18_1700`，且消息中 SHALL 含文档链接

#### Scenario: 自聊优先 user_id
- **WHEN** 配置了 `feishu.user_id`（可同时有 `chat_id`）且文档新建成功
- **THEN** 系统 SHALL 使用 `lark-cli im +messages-send --user-id` 发送，SHALL NOT 同时传 `--chat-id`

#### Scenario: 建文档失败不发成功链接
- **WHEN** 文档创建失败
- **THEN** 系统 SHALL NOT 发送带伪造成功链接的消息

### Requirement: dry-run 不调用 lark-cli 写命令
当启用 dry-run 时，系统 SHALL 仍可完成本地 dual.md 生成，SHALL NOT 调用 `lark-cli docs +create` 或 `lark-cli im +messages-send`（或等价写命令）。

#### Scenario: dry-run
- **WHEN** 以 dry-run 模式执行推送管道
- **THEN** 本地 dual.md SHALL 可被生成，且 SHALL NOT 产生新的飞书云文档
