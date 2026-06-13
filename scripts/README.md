# 脚本目录

存放项目运维、开发辅助脚本（Shell / Bash / PowerShell）。

## 约定

- 脚本应可独立运行，或在 README 中说明依赖
- 敏感参数从环境变量或 `config/app.yaml` 读取，勿硬编码
- 文件名使用 kebab-case，如 `setup-dev-env.sh`

## 计划脚本（待补充）

| 脚本 | 用途 |
|------|------|
| `setup-dev-env.sh` | 创建 venv、安装依赖 |
| `run-dev.sh` | 启动开发服务 |
