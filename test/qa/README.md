# test/qa — QA 盲测补充用例

本目录是 **QA 角色专属**的补充测试，与 `test/` 下 engineer 的 TDD 单测并存、互不越界。

## 目录约定：按被测模块镜像

QA 用例 **按被测模块镜像到 `test/qa/<module>/`**，与 `src/<module>/` 同构（避免扁平目录膨胀，便于按模块并行与定位）：

| 被测模块 | QA 用例目录 |
| --- | --- |
| `src/service/backtest/` | `test/qa/backtest/` |

当前只有回测模块（`test/qa/backtest/`）；其他模块引入时按同一规则建 `test/qa/<module>/`。

- 文件名形如 `test_<topic>.py`（回测模块清单见 `openspec/changes/add-backtest-engine/test-design.md` §1.1）。
- 模块专属 fixture / session 级门闩放该子目录的 `conftest.py`，只作用于本模块用例。
- 该约定与 `openspec/changes/add-backtest-engine/design.md` §6.7 一致（由 captain 裁定）。

## 所有权

| 角色 | 可写 | 禁写 |
| --- | --- | --- |
| `qa` | `test/qa/`、`openspec/changes/<change>/verification.md` | `src/`、`test/`（engineer 的）、`design.md`、`openspec/specs/` |
| `engineer` | `src/`、`test/`、`config/`、`pyproject.toml`、`openspec/changes/<change>/tasks.md`（仅勾选） | `test/qa/`、`design.md`、`openspec/specs/` |

QA 用例写错（断言 bug）时，engineer 不得私自修改，报 captain → QA 自己修。

## 设计纪律：盲测

写用例时只读：specs delta、`proposal.md` 的成功/失败标准、`design.md`、`docs/mrd/` 锚点。
**不读** engineer 的实现与 `test/`——避免被实现带偏（测试从实现派生 = 失败定义）。

## 用例要求

- 可执行 pytest，每条对应一个 `#### Scenario` 或 proposal 的一条成功/失败标准，可溯源到锚点。
- 必含负向 / 边界 / 对抗用例（空输入、字段缺失、越界、篡改、依赖不可用）。
- 不写「口头测试点」。

## 运行

```bash
# 仅 QA 套件（子目录 test/qa/<module>/ 自动收集，无需改 pyproject）
python -m pytest -q test/qa

# 只跑某一模块
python -m pytest -q test/qa/backtest

# 全量（engineer + QA）
python -m pytest -q

# 离线（排除标 network 的用例）
python -m pytest -q -m "not network"
```

pytest 配置见 `pyproject.toml`（`testpaths = ["test"]`、`--import-mode=importlib`、默认排除 `akshare_legacy`）。
