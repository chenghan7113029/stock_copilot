# 验证报告：<change-name>

- 变更：`openspec/changes/<change-name>/`
- 波次：<wave-id>
- 验证人：qa
- 验证时间：<YYYY-MM-DD HH:mm>
- 代码基线：<commit sha>（`git rev-parse HEAD` 的输出，手抄即违规）
- 环境：<OS / Python 版本 / 关键依赖版本；pytest 命令与 deselect 数>

> **证据纪律（本仓库）**：这里没有独立的运行产物目录，也没有查询 id —— 每条证据写成
> **「命令 + 退出码 + 关键输出 + `文件:行` / 测试节点 id」**，例如
> `python -m pytest -q test/qa/test_fundflow.py::test_divergence` → exit 0 → `1 passed` →
> 断言 `src/service/fundflow_analyzer.py:88`。数字、sha、`文件:行` 一律复制自命令输出，
> 不得凭记忆重写。本模板共 **9 章节**，编号固定，缺一节即视为报告不合格。

## 1. 结论

<!-- 三选一，必须明确：通过 / 有条件通过 / 不通过 -->
**结论**：<通过 | 有条件通过 | 不通过>

**依据**：<一句话说明关键证据；有条件通过时列出附带条件>

## 2. 验收标准逐条核对

### 2.1 T3 acceptance（任务契约原文）

<!-- 每条一行；criterion 必须与 T3 任务契约里的 acceptance 原文一致 -->
| # | 验收标准 | 命令 | 退出码 | 关键输出 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | <acceptance 原文> | `<command>` | 0 | <截取关键行> | 通过 |

### 2.2 proposal 成功标准 / 失败标准

<!-- 逐条核对 proposal 的 ## 成功标准 与 ## 失败标准/反目标；缺一不可，漏验即失败 -->
| # | 标准（成功 / 失败 / 反目标） | 是否达成 | 证据（命令 + 退出码 + 关键输出，或 `文件:行` / 测试节点 id） |
| --- | --- | --- | --- |
| 1 | <成功标准原文> | 达成 / 未达成 | |

## 3. 测试执行

<!-- 两套测试分列：engineer 的 test/ = 标准 spec 单测；QA 的 test/qa/ = 验收/负向/对抗用例（盲测设计） -->
| 套件 | 命令 | 结果 | 备注 |
| --- | --- | --- | --- |
| engineer `test/` | `python -m pytest -q test --ignore=test/qa` | x passed / y failed | 标准 spec（SHALL/Scenario） |
| QA `test/qa/` | `python -m pytest -q test/qa` | | 验收 / 负向 / 对抗 |
| 全量 | `python -m pytest -q` | | 两套一起；默认 deselect 32 个 `akshare_legacy`，写明 deselect 数 |
| 静态检查 | `python -m ruff check .` | exit 0 | line-length 120，规则 `E,F,I,W` |
| 语法检查 | `python -m compileall -q src test` | exit 0 | 两套测试都要能编译 |

> 用过 `-m` 过滤联网用例时把**完整命令**写进「命令」列：`-m` 会覆盖 `pyproject.toml` 的 addopts，
> 想同时排除两类得写 `-m "not network and not akshare_legacy"`，否则会把 32 个 `akshare_legacy` 重新收进来。
> 「engineer `test/`」行的 `--ignore=test/qa` 只用于把两套套件分列显示，**门禁以「全量」行为准**；
> 任务 verify 里不许出现 `--deselect` / `-k not` / `|| true` / `--ignore=`（那是放宽验收，不是分列）。

## 4. 负向与边界用例

<!-- 必填。只测 happy path 的报告视为不合格 -->
| # | 场景 | 输入 | 期望 | 实际（含证据） | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | 空输入 / 字段缺失 | | 明确报错 | | |
| 2 | 超大输入 / 边界值 | | | | |
| 3 | 依赖不可用（数据源超时 / 缺库） | | 降级或报错 | | |
| 4 | 数字捏造 | | 被确定性计算拦截，LLM 输出不覆盖数值 | | |
| 5 | 过滤条件不生效 | | 被证伪（结果集与条件一致） | | |

## 5. 规格一致性

<!-- 规格里的每个 Scenario 是否都被覆盖，并标出覆盖它的测试属于哪套套件 -->
| Requirement | Scenario | 覆盖测试（`test/` 或 `test/qa/`，写到测试节点 id） | 结论 |
| --- | --- | --- | --- |
| | | `test/qa/test_x.py::test_y` | |

## 6. 未覆盖项与风险

<!-- 如实写。没覆盖就说没覆盖，不要含糊 -->
- <未覆盖项>：原因 / 影响 / 建议

## 7. 失败项记录（结构化 finding）

<!-- 每条失败必须有可执行 requiredFix，禁止「测试失败请修复」这类废话 -->
| finding id | 严重度 | 问题 | 要求修复（requiredFix） | 位置（`文件:行` 或 测试节点 id） | 阻塞归档 |
| --- | --- | --- | --- | --- | --- |
| F1 | blocker / high / medium / low | | 改哪里、改什么、怎么验证 | | 是 / 否 |

## 8. 复现说明

```bash
# 任何人从干净环境重跑本报告全部命令的最小步骤
git rev-parse HEAD
python -m pytest -q
python -m pytest -q test/qa
python -m ruff check .
python -m compileall -q src test
openspec.cmd validate <change> --strict
```

## 9. Case 复现核对 + 记 trace

<!-- 对照 proposal「Case 复现锚点」逐条核对；结论 append 进 docs/cases/<case>/traces.yaml，不手写「复现进度」表 -->
| 结论编号 | 环（提问 / 取数 / 计算 / 结论 / 呈现） | proposal 锚点（X→Y） | 实际 | verdict | trace id | 卡点（功能 / 知识 / 数据源） |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | 计算 | <本波声明从 X→Y> | | pass / partial / fail | `20261114-<change>-01` | |

**记录规则**：

1. 每条结论 / 环的复现结论 **append 一条记录**进 `docs/cases/<case>/traces.yaml`，字段见
   `docs/cases/_template-traces.yaml`（`id / date / kind / conclusion / layer / verdict / evidence / note`）；
   本表与 trace 用同一个 `trace id` 对齐，**能引用的一律不转述**（数字、verdict 照抄输出，不重写）。
2. K3 已 append 的 `layer: knowledge` 记录直接引用 trace id，不在本报告重复抄数字；知识层与功能层
   结论冲突时以「卡点」列写清归属（功能 / 知识 / 数据源）。
3. 未达锚点时 `verdict=partial|fail`，并在「卡点」列写清是功能没做到、知识不对、还是数据源缺失——
   不许用「基本达成」这类修饰词。
4. **不回写「复现进度」表**：它是 traces.yaml 的派生视图，手写等于造第二份真源。
