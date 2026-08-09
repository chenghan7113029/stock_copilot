## ADDED Requirements

### Requirement: 用本地 Markdown 新建飞书云文档
系统 SHALL 读取 composer 产出的本地 Markdown，调用飞书开放平台以应用身份**新建**一篇云文档（MUST NOT 覆盖更新既有文档 URL 作为默认行为）。新建成功后 SHALL 返回可分享的文档链接。

#### Scenario: 新建成功
- **WHEN** 飞书凭证有效且 Markdown 文件存在
- **THEN** 系统 SHALL 创建新文档并返回文档 URL，且该 URL SHALL 对应当次新建资源

#### Scenario: 凭证缺失
- **WHEN** 未配置 `app_id`/`app_secret`（或等效环境变量）且非 dry-run
- **THEN** 系统 SHALL 失败并给出可操作的配置提示，SHALL NOT 假装发送成功

### Requirement: 一票一条推送消息
系统 SHALL 向配置的接收会话发送一条消息，内容 MUST 包含股票代码（及可得时的名称）、推送时段/生成时刻，以及新建文档的链接。一条消息 MUST 只对应一只股票。

#### Scenario: 单票消息
- **WHEN** `600519` 的文档新建成功
- **THEN** 系统 SHALL 发送恰好一条面向该股票的消息，且消息中 SHALL 含文档链接

#### Scenario: 建文档失败时的通知
- **WHEN** 文档创建失败但消息通道可用
- **THEN** 系统 SHALL 发送失败通知（含代码与错误摘要），SHALL NOT 发送伪造的成功链接

### Requirement: dry-run 不调用飞书写接口
当启用 dry-run 时，系统 SHALL 仍可完成本地 Markdown 组装，SHALL NOT 调用飞书创建文档或发送消息的写接口。

#### Scenario: dry-run
- **WHEN** 以 dry-run 模式执行推送管道
- **THEN** 本地 Markdown SHALL 可被生成，且 SHALL NOT 产生新的飞书云文档
