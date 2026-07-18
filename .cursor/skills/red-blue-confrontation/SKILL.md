---
name: red-blue-confrontation
description: Generate Level-1 red-blue (bull vs bear) confrontation narrative from stock_copilot dual-track evidence buckets. Use when the user asks for 红蓝对抗、多空对抗、看多看空互驳、bull/bear confrontation, or wants opposing reports with mutual rebuttals for a stock code.
license: MIT
compatibility: Requires stock_copilot CLI (`python -m apps.cli report dual`) and local sync data.
metadata:
  author: stock_copilot
  version: "1.0"
---

# 红蓝对抗（Skill 版 Level 1）

基于 `report dual` 的**确定性证据分桶**，在当前 Cursor 会话中生成多方/空方论述与互相反驳。不调用应用内置 LLM API，不写数据库。

## 何时使用

用户提到：红蓝对抗、多空对抗、看多看空、互驳、bull/bear confrontation，或给出股票代码并要求对立报告时。

## 步骤

### 1. 解析股票代码

- 从用户消息提取 6 位 A 股代码（如 `600519`）。
- **若未提供代码**：先询问用户，**禁止臆测**。

### 2. 获取证据分桶（唯一事实来源）

在仓库根目录执行（Windows 可用 `py -m`）：

```bash
python -m apps.cli report dual <code> --json --quiet
```

若用户已提供现成 JSON 文件路径，直接读取该文件，无需再跑命令。

解析出：

- `bull_evidence[]`
- `bear_evidence[]`
- （可选）`analysis_summary`、`code`

**若命令退出码非 0**（如本地无快照）：将错误信息如实转达用户（例如「请先运行 sync」），**停止**，不生成叙事。

### 3. 生成 Level 1 互驳叙事

**硬约束（必须遵守）：**

1. 多方论述**仅**基于 `bull_evidence`；空方论述**仅**基于 `bear_evidence`。
2. 互驳必须**引用对方证据的具体条目**（用序号，如「针对空方证据 [2] …」），禁止泛泛而谈。
3. **禁止**引入证据列表之外的具体数值、财报事实或新闻；不确定时写「证据未覆盖，不作断言」。
4. 输出末尾**必须**固定包含免责声明：

   > 叙事由 AI 生成，仅供参考，请对照上方原始证据列表核实。

### 4. 输出结构（对话内呈现）

按以下结构直接回复（可先贴原始证据摘要）：

```markdown
## 原始证据

### 多方 (bull)
1. ...
2. ...

### 空方 (bear)
1. ...
2. ...

## 多方论述
...

## 空方论述
...

## 多方反驳空方
- 针对空方证据 [n]：...

## 空方反驳多方
- 针对多方证据 [n]：...

---
叙事由 AI 生成，仅供参考，请对照上方原始证据列表核实。
```

### 5. 可选落盘

若用户要求保存，或你判断值得留存：写入 `reports/<code>_confrontation.md`（目录不存在则创建）。**禁止**写入任何数据库表。

## 非目标

- 不实现多轮攻防（Level 2）
- 不调用 `common.llm.narrate` / 应用内 LLM API
- 不替用户做买卖决策结论；叙事止于证据对抗
