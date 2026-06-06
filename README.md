# stock_copilot

股票分析编排层：整合技术面（daily_stock_analysis）、价值面（valueinvest / FinanceToolkit）与 LLM 综合决策。

## 本地依赖（独立 git 仓库）

以下目录为开源项目 clone，**不纳入本仓库**，需单独维护：

| 目录 | 上游 |
|------|------|
| `FinanceToolkit/` | https://github.com/JerBouma/FinanceToolkit |
| `valueinvest/` | https://github.com/wangzhe3224/valueinvest |
| `daily_stock_analysis/` | https://github.com/ZhuLinsen/daily_stock_analysis |

```bash
git clone https://github.com/JerBouma/FinanceToolkit FinanceToolkit
git clone https://github.com/wangzhe3224/valueinvest valueinvest
git clone https://github.com/ZhuLinsen/daily_stock_analysis daily_stock_analysis
```

## 开发流程

Spec-driven 开发使用 [OpenSpec](https://github.com/Fission-AI/OpenSpec)，详见 [docs/openspec-best-practices.md](docs/openspec-best-practices.md)。

```text
/opsx-explore → /opsx-propose → /opsx-apply → /opsx-archive
```

## 文档

- [价值面分析层接入方案](stock_copilot-价值面分析层接入方案.md)
- [OpenSpec 最佳实践](docs/openspec-best-practices.md)
