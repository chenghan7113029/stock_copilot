# stock_copilot

股票分析编排层：整合技术面、价值面与 LLM 综合决策。

## 项目结构

```text
stock_copilot/
├── config/              # 配置文件（见 app.example.yaml）
├── docs/
│   ├── mrd/             # 市场需求文档（权威）
│   ├── design/          # 专项设计文档
│   └── dev/
│       └── engineering-conventions.md  # 工程约定与架构（唯一真源）
├── log/                 # 运行日志
├── reports/             # 分析报告产出（gitignore）
├── ref/                 # 外部参考 clone（gitignore，只读）
├── openspec/            # OpenSpec 变更管理
├── scripts/             # Shell / Bash 脚本
├── src/                 # 源代码（扁平）
│   ├── apps/            # CLI / 交互入口
│   ├── controller/      # API 接口层
│   ├── service/         # 业务服务
│   ├── data_provider/   # 外部数据 API
│   ├── dao/             # 数据库访问
│   └── common/          # 通用模块
└── test/                # 测试代码
```

## 快速开始

```bash
# 开发环境（Linux / macOS / Git Bash）
bash scripts/setup-dev-env.sh
source .venv/bin/activate

# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 运行测试
pytest
```

配置：复制 `config/app.example.yaml` → `config/app.yaml` 后修改。

## 外部参考（ref/，不纳入 git）

以下目录放在 `ref/` 下，**仅作阅读参考**，禁止 import；需要逻辑时拷贝进 `src/`：

| 目录 | 上游 |
|------|------|
| `ref/FinanceToolkit/` | https://github.com/JerBouma/FinanceToolkit |
| `ref/valueinvest/` | https://github.com/wangzhe3224/valueinvest |
| `ref/daily_stock_analysis/` | https://github.com/ZhuLinsen/daily_stock_analysis |

```bash
mkdir -p ref
git clone https://github.com/JerBouma/FinanceToolkit ref/FinanceToolkit
git clone https://github.com/wangzhe3224/valueinvest ref/valueinvest
git clone https://github.com/ZhuLinsen/daily_stock_analysis ref/daily_stock_analysis
```

## 文档

| 类型 | 路径 |
|------|------|
| 工程约定与架构 | [docs/dev/engineering-conventions.md](docs/dev/engineering-conventions.md) |
| MRD | [docs/mrd/](docs/mrd/) |
| 专项设计 | [docs/design/](docs/design/) |
| OpenSpec | [docs/dev/openspec-best-practices.md](docs/dev/openspec-best-practices.md) |
| AI 协作 | [AGENTS.md](AGENTS.md) |

OpenSpec 变更归档后，须将需求/设计**合并回 docs/mrd 与 docs/design**，详见 [docs/README.md](docs/README.md)。

## 开发流程

```text
/opsx-explore → /opsx-propose → /opsx-apply → /opsx-archive → 合并 docs
```
