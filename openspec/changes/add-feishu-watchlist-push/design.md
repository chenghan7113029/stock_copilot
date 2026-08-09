## Context

用户需要在通勤时段通过飞书阅读常看股票报告，执行端固定为**家里 Windows PC**（暂无 NAS/云主机）。仓库已具备：`watchlist`、`sync --watchlist`、`report dashboard|summary|dual|value|tech`（含可选 `summary --narrate`）。红蓝 Level 1 互驳仅存在于 Cursor Skill，**不可被计划任务调度**；本 change 文档顶栏采用方案 A（综合叙事），不伪装红蓝互驳。

产品定案（explore）：交易日 09:00 / 13:00 / 17:00 纯推送；每票**新建**飞书文档；先生成本地 Markdown 再写入飞书；消息一票一条只带链接；指令对话后置。

## Goals / Non-Goals

**Goals:**
- 提供可被 Windows 计划任务调用的 CLI 管道：可选 sync → 组装本地 MD → 新建飞书文档 → 推送链接消息
- 本地 MD 为唯一可复现中间产物；飞书失败时可凭本地文件重试上传
- 单票章节失败时降级写入错误说明，不阻断同批次其他票
- 密钥与 chat 目标可配置；dry-run 不访问飞书 API

**Non-Goals:**
- 飞书入站指令 / 可对话（Phase A.2 / B）
- 覆盖更新同一文档 URL
- 无人值守红蓝 Level 1 叙事（Skill 或未来独立 LLM change）
- REST API / Web 看板
- 自动清理历史飞书文档
- 改造既有 `report *` 命令契约（只消费其文本/结构化输出）

## Decisions

### 决策 1：模块落点 — `service/feishu` + CLI 薄封装

**选择**：
- `src/service/feishu/composer.py` — 组装 Markdown
- `src/service/feishu/publisher.py` — tenant_access_token、建文档、发消息
- `src/service/feishu/pipeline.py` — 编排单票/watchlist 批次
- `src/apps/cli.py` — `feishu push` 入口
- HTTP 用标准库或已有 `httpx`/`requests`（以 `pyproject.toml` 现有依赖为准；若无则加 `httpx`，禁止为飞书引入重型 SDK 除非必要）

**理由**：符合 `apps → service → common`；飞书是外部系统适配，与 `data_provider` 类似但面向「写出」，放 `service/feishu` 比塞进 `report/` 更清晰。

**备选**：只写 `scripts/feishu_push.py` — 拒绝，难以测、难复用、违背 apps/service 分层。

### 决策 2：报告内容 — 进程内调 service / formatter，避免嵌套 CLI 子进程（默认）

**选择**：composer 优先复用已有 analyzer + `format_*` 函数生成各节文本；若某路径仅 CLI 可达，允许内部调用与 CLI 相同的 `run_report_*` 函数（同进程），**默认不** `subprocess` 再开一层 `python -m apps.cli`。

**理由**：计划任务已在 Python 进程内；子进程会重复加载、难传 config、错误码难聚合。

**备选**：全量子进程调 CLI — 可作 fallback，但不作为主路径。

### 决策 3：文档章节与叙事语义

**选择**：Markdown 固定顺序与标题：

1. `# 综合叙事` — 来自 summary；若配置/CLI 开启 narrate 则含 LLM 段；文首固定免责：「本节为综合叙事（summary），**不是**红蓝互驳 Level 1。」
2. `# 红蓝证据分桶` — dual
3. `# 多维看板` — dashboard
4. `# 价值面报告` — value
5. `# 技术面报告` — tech

文首 YAML/元信息块含：`code`、`generated_at`、`slot`（0900|1300|1700）、`narrate` 是否成功。

**理由**：用户已选方案 A；标题必须诚实，避免把 summary 写成「红蓝对抗叙事」。

### 决策 4：本地路径 — 每次运行独立目录（对齐「新建文档」）

**选择**：  
`reports/feishu/{YYYY-MM-DD}/{HHmm}/{code}.md`  
（`HHmm` 为本次运行槽，如 0900；同一分钟重跑可追加序号或秒，design 实现时选一种避免覆盖本地文件。）

**理由**：与「飞书每次新建」一致；gitignore 的 `reports/` 已覆盖。

### 决策 5：飞书集成 — 应用身份 + 云文档新建 + 会话发消息

**选择**：
- 使用飞书企业自建应用：`app_id` + `app_secret` → `tenant_access_token`
- **新建**云文档：将 Markdown 转为飞书文档块（实现可选：Docs API 导入 Markdown，或先建空文档再分块写入；优先官方 Markdown/导入能力，失败则降级为「发文件」或消息附截断预览 + 提示本地路径）
- 消息：向配置的 `chat_id`（或 webhook，若仅消息可用）发送「【{code} {name}】{slot} 报告」+ 文档 URL
- 配置示例：

```yaml
feishu:
  app_id: ""
  app_secret: ""          # 或 FEISHU_APP_SECRET
  chat_id: ""             # 接收推送的群/会话
  folder_token: ""        # 新建文档所在文件夹（可选）
  narrate: false          # 默认关；计划任务可 --narrate 覆盖
  sync_before_push: true
  trading_days_only: true
```

**备选**：仅 Webhook 发长文本 — 拒绝，无法解决长度与排版；Webhook 可作为「消息通道」补充，但不能替代建文档。

### 决策 6：交易日与调度 — 代码判交易日 + OS 计划任务触发

**选择**：
- CLI `feishu push` 在 `trading_days_only: true` 时：若非 A 股交易日则退出 0 并打印 skip（避免节假日空跑刷屏）
- 交易日日历 V1：使用可测的简单策略——优先复用项目内已有交易日历（若有）；否则「周一至周五且不在 `config/feishu_holidays.yaml`（或配置列表）休市日」；精确交易所日历可后续替换而不改 CLI 契约
- 09:00 / 13:00 / 17:00 由 **Windows 任务计划程序** 调用同一命令三次（不同参数或环境变量 `FEISHU_SLOT=0900`）；仓库提供 `docs/user-guide` 或 `scripts/windows/` 安装说明，**不**在 Python 内常驻 daemon

**理由**：家里 PC 无云；常驻进程增加睡眠/登录复杂度；计划任务是 Windows 原生。

### 决策 7：sync 与 narrate 默认值

**选择**：`sync_before_push` 默认 true（三段推送都先 sync watchlist，13:00 可带 realtime 若 CLI 暴露 `--realtime`）；`narrate` 默认 false（省时省钱，配置或 `--narrate` 打开）。

**理由**：通勤要「有数」；LLM 为可选增强，失败不阻断文档其余章节。

### 决策 8：批次失败与消息

**选择**：单票：某章节失败 → 该节写入错误块，其余节继续；建文档或发消息失败 → 向飞书发一条失败通知（若消息通道可用）或仅 stderr + 非 0 汇总码。整批：部分成功部分失败时退出码非 0，但已成功票的文档/消息保留。

## Risks / Trade-offs

- **[风险] 家里 PC 休眠/未登录导致计划任务未跑** → **缓解**：user-guide 写明「唤醒、电源选项、使用最高权限/是否仅当用户登录」；失败无自动补推（A.2 指令可后补「补推今日」）
- **[风险] 飞书 Docs API 对 Markdown 支持不完善** → **缓解**：composer 与 publisher 解耦；publisher 可降级为上传 `.md` 文件到云空间并链到消息；本地 MD 始终保留
- **[风险] 每次新建导致云盘膨胀** → **接受**（用户选择）；Open Question 记保留策略；不在 V1 自动删
- **[风险] 交易日误判（调休）** → **缓解**：可配置假期列表；错推一日可接受，漏推用手动 `feishu push` 补
- **[风险] watchlist 较大时 09:00 超时（sync+多报告+narrate）** → **缓解**：默认 narrate=false；并行度 V1 串行保稳定；超时票记失败节
- **[风险] 把 summary 放在「叙事」位可能被误读为红蓝** → **缓解**：固定免责声明标题（决策 3）

## Migration Plan

- 无 DB schema 变更
- 新增配置段与依赖；未配置 `feishu` 时 `feishu push` 明确报错（dry-run 仍可只写 MD）
- 回滚：移除 `service/feishu`、CLI 子命令与配置示例即可
- 归档后：合并 design 要点到 `docs/design/`，更新 MRD「交付通道」、engineering-conventions 目录表

## Open Questions

- 飞书文档 API 最终选用「Markdown 导入」还是「分块写入」——apply 时 spike 一次官方文档后钉死，不影响 composer 契约
- 消息通道用 IM `chat_id` 还是自定义机器人 Webhook——推荐 IM（与应用同一身份）；若 Owner 只有 Webhook，可允许 `message_mode: webhook` 仅发链接（文档仍由应用创建）
- A 股交易日历是否已有可复用模块——apply 时检索 `src/`；若无则用「工作日 + 假期表」V1
