# AGENTS.md

本仓库 AI 协作与代码生成的规则真源：

- **[docs/dev/engineering-conventions.md](docs/dev/engineering-conventions.md)** — 工程约定与架构（目录、分层、依赖、编码约束）
- **[docs/agent-engineering-quality.md](docs/agent-engineering-quality.md)** — 确定性计算与 LLM 协作（三层防御详细规范）

动手前须阅读上述文档及相关的 `docs/mrd/` feature 文档。

## Cursor Cloud specific instructions

若你在 **Cursor Cloud Agent** 环境运行：**必须先阅读 [.cursor/CLOUD_AGENT.md](.cursor/CLOUD_AGENT.md)**，执行其中的会话启动自检，再读 engineering-conventions 与相关 MRD。

人类 Owner 的移动开发操作见 [docs/dev/cloud-agent.md](docs/dev/cloud-agent.md)。
