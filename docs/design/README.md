# 设计文档

技术设计：描述**怎么做、模块如何划分、接口如何定义**。

## 文档索引

| 文档 | 说明 |
|------|------|
| [../dev/engineering-conventions.md](../dev/engineering-conventions.md) | **工程约定与架构（唯一真源）** |
| [architecture.md](architecture.md) | 已合并至 engineering-conventions（跳转桩） |
| [value-analysis-integration.md](value-analysis-integration.md) | 价值面分析层接入方案 |
| [references/](references/) | 外部开源项目分析报告 |

## 维护规则

- OpenSpec 变更的 `design.md` 归档后合并到本目录
- **架构/目录/依赖变更须更新 [engineering-conventions.md](../dev/engineering-conventions.md)**，勿在 architecture.md 维护

## 代码模块映射

| 设计概念 | 源码路径 |
|----------|----------|
| 交互界面 | `src/apps/` |
| API 接口 | `src/controller/` |
| 业务服务 | `src/service/` |
| 外部数据 | `src/data_provider/` |
| 数据库 | `src/dao/` |
| 通用工具 | `src/common/` |
