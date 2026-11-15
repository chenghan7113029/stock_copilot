# 外部开源项目分析报告

本目录存放对 `ref/` 下参考项目的分析报告与**调研索引**，**不纳入 src**，仅供设计参考。**本目录进 git**（`ref/` 不进）。

## 索引（进 git 的唯一凭据）

| 文档 | 项目 / 主题 |
|------|------|
| [daily_stock_analysis-module-analysis.md](daily_stock_analysis-module-analysis.md) | daily_stock_analysis |
| [financetoolkit-module-analysis.md](financetoolkit-module-analysis.md) | FinanceToolkit |
| [valueinvest-module-analysis.md](valueinvest-module-analysis.md) | valueinvest |

## 波次调研索引（`<topic>-research.md`）

由 product-manager 在 T1 前置阶段产出，模板见 [`docs/agent-team/templates/reference-research.md`](../../agent-team/templates/reference-research.md)。

| 命名 | 内容 |
| --- | --- |
| `<topic>-module-analysis.md` | 单个参考项目的结构/模块分析（历史体例，可继续沿用） |
| `<topic>-research.md` | 一次波次的调研索引：调研问题 → REF 条目 → 借鉴点/不借鉴点 → 落地映射 → 已排除候选 → 合规风险 |

体例要求：

1. **先结论后细节**：结论摘要必须在最前，写清「借鉴什么、明确不借鉴什么、影响哪条需求」。
2. **REF-ID 稳定**：`REF-<topic>-<NN>`，一经写入不复用；作废条目保留行并标「作废」。
3. **每条 REF 必带**：来源 URL + commit SHA 或抓取日期 + 许可证 + 存放路径（`ref/research/<topic>/<slug>/`）+ 复现命令。
4. **必须闭环**：`proposal.md` 的 `## 外部参考` 与 `specs/` 里的 `参考依据：REF-xxx` 都能在本目录找到对应行。
5. **无参考也要写**：本波没有可借鉴实现时，写「无可借鉴」+ 排除理由，proposal 里写「本波无外部参考」。

## 相关规则

- `ref/` 是只读快照 + 调研资料区，**禁止 `import` / `pip install -e` / `sys.path`**（见 [engineering-conventions §5](../../dev/engineering-conventions.md)）。
- 需要 COPY 代码进 `src/` 时，文件头注释必须写：来源仓库、原路径、commit/日期、许可证；并补 `test/` 用例。
