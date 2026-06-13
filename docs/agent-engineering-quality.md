# Agent 工程质量设计规范

> **文档类型**：工程规范
> **服务对象**：数仓 Code Agent 实现工程师（一线视角）
> **更新时间**：2026-06-10
> **关联文档**：
> - [dw_code_agent_mrd.md](dw_code_agent_mrd.md) — Code Agent 系统 MRD，定义 8 步流程和产出物
> - [standards/dw-adm/](standards/dw-adm/) — ADM 层规范，Agent 行为契约的具体实例

---

## 背景：三角矛盾

实现 Code Agent 时，工程师会同时面对三个质量要求，且三者天然存在张力：

| 要求 | 定义 | 典型矛盾点 |
|-----|------|---------|
| **鲁棒性** | 外界扰动（错输入、工具抖动、边缘数据）不导致崩溃或幻觉 | 处理扰动需要更多逻辑和重试，增加消耗 |
| **稳定性** | 环境不变时系统不发散、不漂移，同等价输入产出可预期 | 稳定性校验（self-check）需要额外 LLM 调用 |
| **消耗** | Token 用量和执行时间控制在可接受范围 | 省成本往往意味着减少校验，增加脆性 |

**优先级**：鲁棒性 > 稳定性 > 消耗。在三者冲突时，优先保鲁棒，其次保稳定，最后再考虑省成本。

---

## 一、核心框架：三层防御 + LLM 核最小化

```
┌─────────────────────────────────────────────────────────┐
│  用户输入 / 上游产出物                                      │
└───────────────────┬─────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  【输入卫兵】Input Guard                                   │
│  参数校验 / 术语标准化 / 超长截断 / Session 重置            │
│  实现方式：纯代码，零 token 消耗                             │
└───────────────────┬─────────────────────────────────────┘
                    ↓ 干净、标准化的输入
┌─────────────────────────────────────────────────────────┐
│  【LLM 核】LLM Core（最小化）                              │
│  只处理代码无法解决的任务：意图理解、口径推断、内容生成        │
│  强制输出结构化 JSON，不允许自由文本                         │
└───────────────────┬─────────────────────────────────────┘
                    ↓ 结构化 JSON
┌─────────────────────────────────────────────────────────┐
│  【输出卫兵】Output Guard                                  │
│  JSON schema 校验 / 幂等缓存 / 重试上限 / null 检测         │
│  实现方式：纯代码，零 token 消耗                             │
└───────────────────┬─────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  下一步 Agent 或人工介入                                    │
└─────────────────────────────────────────────────────────┘
```

**为什么这个框架能化解三角矛盾**：

- 鲁棒性由**代码层**保证，不靠 prompt 技巧——代码校验稳定、可测试、零额外消耗
- 输入标准化后 LLM 见到的输入方差缩小，**稳定性**自然提升
- LLM 只处理「代码处理不了」的部分，**消耗**随之降低
- 幂等缓存让等价输入的第二次调用成本为零，同时稳定性达到 100%

---

## 二、输入卫兵（Input Guard）

### 2.1 必填参数校验

**设计原则**：在进入 LLM 流程之前，用代码校验所有必填字段。缺失时立即拒绝并告知缺少什么，不让 LLM 去猜。

**必填字段定义方式**：每个 Agent 的入口都应有一个 JSON schema 或等价的 required 字段列表，与 MRD 中的「核心输入」对应。

```python
REQUIRED_FIELDS = ["target_table", "scenario", "requirements_doc"]

def validate_input(payload: dict) -> None:
    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        raise InputValidationError(f"缺少必填参数: {', '.join(missing)}")
```

✅ **Good Case**：需求理解 Agent 收到输入后，先用 schema 校验 `target_table`、`scenario`（新建表/新增字段/修改字段）、`requirements_doc` 三个必填字段。`scenario` 缺失时直接返回 `"缺少参数: scenario，请指定 新建表 / 新增字段 / 修改字段 之一"`，流程终止，不进入 LLM。

❌ **Bad Case**：把残缺的输入直接送给 LLM，在 prompt 里写 `"如果 scenario 字段缺失，请根据上下文自行推断"`。LLM 会安静地猜一个合理值，产出物看起来完整，但下游模型设计 Agent 会基于一个错误的场景类型运行，错误会在步骤 7 才暴露。

---

### 2.2 业务术语标准化

**设计原则**：用户输入不标准（同义词、错别字、大小写）时，在进入 LLM 之前用词典统一。不要依赖 LLM 识别同义词，LLM 识别结果不稳定。

**实现方式**：维护一份业务术语映射表，覆盖数仓领域高频同义词。

```python
TERM_NORMALIZATION = {
    "adm层": "ADM", "adm 层": "ADM", "聚合层": "ADM",
    "cdm层": "CDM", "主题宽表": "CDM",
    "新增": "新增字段", "加字段": "新增字段", "add column": "新增字段",
    "改口径": "修改字段", "修改口径": "修改字段",
}

def normalize_terms(text: str) -> str:
    for raw, standard in TERM_NORMALIZATION.items():
        text = text.replace(raw, standard)
    return text
```

✅ **Good Case**：用户输入 `"改一下这张 adm 层的表，加个字段"` → 标准化后变为 `"改一下这张 ADM 的表，新增字段"` → LLM 接收到的是规范术语，输出 `scenario: "新增字段"` 是确定的。

❌ **Bad Case**：把原始输入直接送给 LLM，期望 LLM 理解 `"加个字段"` 等于 `"新增字段"` 场景。在标准 prompt 下 LLM 大概率能理解，但在 prompt 被截断或上下文混杂时会失效，且行为不可预期。

---

### 2.3 超长输入处理

**设计原则**：超过 context 安全阈值的输入必须在进入 LLM 前截断或摘要。不要指望 LLM 自己处理超长输入，超长会导致截断位置不可控、关键信息丢失。

**阈值参考**：需求文档 > 8000 token 时触发压缩；对话历史 > 20 轮时截断最早轮次，保留 system prompt + 最近 10 轮。

```python
MAX_REQUIREMENTS_TOKENS = 8000

def compress_if_needed(doc: str, tokenizer) -> str:
    if tokenizer.count(doc) <= MAX_REQUIREMENTS_TOKENS:
        return doc
    # 保留头部（背景）+ 尾部（具体需求），中间摘要
    head = doc[:2000]
    tail = doc[-2000:]
    middle_summary = summarize_middle(doc[2000:-2000])  # 用小模型摘要
    return f"{head}\n\n[中间部分摘要]\n{middle_summary}\n\n{tail}"
```

✅ **Good Case**：需求文档很长时，用 Haiku 先做一次摘要（成本极低），再把摘要版本送给 Sonnet 做正式处理。总 token 消耗反而更低，且关键信息不丢失。

❌ **Bad Case**：不做任何截断，把 20000 token 的文档原文送给 LLM。表面上 LLM 接受了，但注意力机制对超长文档中间部分的处理质量显著下降，关键字段可能被忽略，且成本极高。

---

### 2.4 Session 污染防御

**设计原则**：每次触发 Agent 时，通过 system prompt 重置身份和上下文边界。不要依赖历史对话记忆来维持状态——历史对话是污染源，不是可信上下文。

**实现方式**：关键参数（target_table、scenario、当前步骤）通过 system prompt 显式注入，不从对话历史中读取。

```python
SYSTEM_PROMPT_TEMPLATE = """
你是数仓 Code Agent 的需求理解子 Agent。
当前任务上下文（以下参数以此为准，不参考历史对话中可能出现的其他值）：
- 目标表：{target_table}
- 场景：{scenario}
- 触发步骤：步骤 1（需求理解）
"""

def build_system_prompt(context: AgentContext) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(**context.to_dict())
```

✅ **Good Case**：上一次对话讨论的是 `dw_adm_order_daily` 表，本次触发的是 `dw_adm_user_profile` 表。system prompt 显式注入新的 `target_table`，LLM 不会把上次的表名带入本次产出物。

❌ **Bad Case**：不重置 system prompt，在对话框中连续触发两个不同表的需求理解。LLM 的注意力可能在两个表之间混淆，尤其是当用户用了模糊指代（`"这张表"`）时，产出物中的表名可能是错的。

---

### 2.5 工具调用失败处理

**设计原则**：工具超时、限流（429）、500 错误的重试逻辑必须在**代码层**实现（指数退避），不在 LLM prompt 里描述重试策略。

```python
import time

def call_tool_with_retry(tool_fn, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = tool_fn(*args)
            if result is None or result == {}:
                raise EmptyResponseError("工具返回空结果")
            return result
        except (TimeoutError, RateLimitError, ServerError) as e:
            if attempt == max_retries - 1:
                raise ToolFailureError(f"工具调用失败，已重试 {max_retries} 次: {e}")
            wait = 2 ** attempt  # 指数退避：1s, 2s, 4s
            time.sleep(wait)
```

✅ **Good Case**：查询元数据平台接口返回 429 时，自动等待后重试，最多 3 次。超过后抛出明确异常，Agent 终止并告知用户，不继续执行。

❌ **Bad Case**：在 prompt 里写 `"如果工具调用失败，请重试或跳过这一步继续生成"`。LLM 无法控制实际的工具调用，这句话只会让 LLM 在工具失败时生成一个「假装成功」的虚假产出物，带着幻觉的字段 Mapping 往下走。

---

### 2.6 歧义和隐含意图处理

**设计原则**：当输入存在多种合理解读时，必须触发对话式澄清，不让 LLM 静默选择一种解读并继续。静默猜测是最危险的鲁棒性问题。

**触发条件**：LLM 核在 JSON 输出中附带 `ambiguity_detected` 字段，代码层检测到该字段为 true 时暂停流程，向用户输出澄清问题。

```json
{
  "scenario": "新增字段",
  "confidence": 0.6,
  "ambiguity_detected": true,
  "ambiguity_description": "需求描述中同时出现「新增指标」和「修改口径」，无法确定场景",
  "clarification_options": [
    "A. 新增字段（新增一个指标字段，不修改现有字段）",
    "B. 修改字段（修改现有字段的计算口径）"
  ]
}
```

✅ **Good Case**：需求文档写 `"把 GMV 口径改一下，同时加一个净 GMV 字段"`。LLM 识别到两个操作混在一起，输出 `ambiguity_detected: true`，Agent 暂停并问用户：`"本次需求同时包含「修改字段」和「新增字段」两个操作，是分两次触发 Agent，还是合并处理？"`

❌ **Bad Case**：LLM 自行选择 `"新增字段"` 场景继续，生成了 demand-understanding.md，但遗漏了口径修改部分。用户在步骤 7 发现时，前 6 步的产出物全部作废。

---

## 三、LLM 核最小化（LLM Core）

### 3.1 只做代码做不了的事

**设计原则**：以下任务应该用代码实现，不应该给 LLM。

| 任务类型 | 正确实现 | 错误做法 |
|---------|---------|---------|
| 字段命名规范校验 | 正则表达式 | 让 LLM 判断字段名是否合规 |
| 参数完整性检查 | required 字段列表 | 让 LLM 判断输入是否完整 |
| 版本号格式校验 | regex `^\d+\.\d+\.\d+$` | 让 LLM 验证版本号格式 |
| JSON 解析 | json.loads() | 让 LLM 从自由文本中提取 JSON |
| 文档模板填充（固定结构）| 字符串模板 | 让 LLM 生成固定格式文档 |
| 数字计算（字段数量、字符数）| 直接计算 | 让 LLM 数字段数量 |

✅ **LLM 应该做**：从用户的需求描述中推断业务事实（这张表的粒度是什么？）、生成字段口径说明（用自然语言解释业务含义）、识别潜在的口径冲突（这两个字段定义是否矛盾？）。

❌ **LLM 不应该做**：校验字段名是否符合 `dw_{layer}_{domain}_{topic}` 格式（用正则）、检查必填字段是否都填了（用 required 校验）、计算有多少个字段需要回归测试（用代码数）。

---

### 3.2 强制结构化输出

**设计原则**：LLM 的所有输出必须是预定义的 JSON schema，禁止接受自由文本作为最终产出。自由文本不可靠解析，是「非预期输出/解析脆弱」问题的根源。

**实现方式**：使用 structured outputs 或 tool-calling 模式，在 API 层强制输出格式。

```python
DEMAND_UNDERSTANDING_SCHEMA = {
    "type": "object",
    "required": ["feasibility", "grain", "upstream_candidates", "consumer_list", "confidence"],
    "properties": {
        "feasibility": {"type": "string", "enum": ["可行", "有条件可行", "不可行"]},
        "grain": {"type": "string", "description": "表的粒度描述"},
        "upstream_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["table_name", "layer", "availability"],
                "properties": {
                    "table_name": {"type": "string"},
                    "layer": {"type": "string"},
                    "availability": {"type": "string", "enum": ["当前可用", "上游优化后可用"]}
                }
            }
        },
        "consumer_list": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
    }
}
```

✅ **Good Case**：使用 Anthropic API 的 `tool_choice: "auto"` + tool 定义强制 LLM 以 JSON 格式输出。即使 LLM 想在前面加几句话解释，tool-calling 模式也会截断，只保留结构化部分。

❌ **Bad Case**：prompt 末尾写 `"请以 JSON 格式输出，格式如下：{...}"`，然后用 `json.loads(response.content)` 解析。LLM 有时会在 JSON 外面加 markdown 代码块（` ```json `），或者加一句 `"以下是输出："` 前缀，导致解析崩溃。

---

### 3.3 置信度暴露

**设计原则**：LLM 输出的 JSON 中必须包含 `confidence` 字段（0-1 浮点数）。低置信度触发人工介入或对话式澄清，不允许带着低置信度的推断继续往下走。

**置信度阈值**：
- `≥ 0.8`：直接继续，记录日志
- `0.6 ~ 0.8`：在产出物中标注「⚠️ 以下内容置信度较低，建议人工复核」
- `< 0.6`：暂停流程，触发对话式澄清

```python
def handle_llm_output(output: dict) -> None:
    confidence = output.get("confidence", 0)
    if confidence < 0.6:
        raise LowConfidenceError(
            f"LLM 输出置信度过低（{confidence:.2f}），"
            f"原因：{output.get('ambiguity_description', '未知')}"
        )
    elif confidence < 0.8:
        output["_warnings"] = ["置信度低于 0.8，建议人工复核以下字段"]
```

✅ **Good Case**：需求文档里的粒度描述非常模糊，LLM 推断 `grain` 字段时输出 `confidence: 0.55`。Agent 暂停，向用户输出：`"当前需求描述无法确定粒度，以下是候选粒度，请确认：A. 按天/用户 B. 按天/订单"`。

❌ **Bad Case**：LLM 用 0.4 的置信度推断出一个粒度，继续生成 model-design.md，TL 评审时发现粒度错误，步骤 2 的产出物全部驳回重来。

---

## 四、输出卫兵（Output Guard）

### 4.1 JSON Schema 校验 + 重试策略

**设计原则**：LLM 输出的 JSON 必须过 schema 校验。校验失败时触发重试，最多 2 次。超过重试上限后终止流程，不允许把不合格的输出传递给下一步。

```python
import jsonschema

def validate_and_retry(llm_fn, schema, max_retries=2):
    last_error = None
    for attempt in range(max_retries + 1):
        output = llm_fn()
        try:
            jsonschema.validate(output, schema)
            return output
        except jsonschema.ValidationError as e:
            last_error = e
            if attempt < max_retries:
                # 把校验错误反馈给 LLM，让它修正
                llm_fn = add_correction_context(llm_fn, str(e))
    raise OutputValidationError(
        f"LLM 输出经 {max_retries + 1} 次尝试仍不符合 schema: {last_error}"
    )
```

✅ **Good Case**：LLM 第一次输出时遗漏了 `grain` 字段（required），校验失败。代码自动构造一个纠错 prompt（`"上次输出缺少 grain 字段，请补充"`），触发第二次调用。第二次输出通过校验，继续流程。整个过程对用户透明。

❌ **Bad Case 1（无限重试）**：没有重试上限，在 LLM 持续输出不合格结果时无限循环，直到 token 耗尽或超时。

❌ **Bad Case 2（静默跳过）**：校验失败时，把缺字段的 JSON 直接传给下一步，在 `etl-design.md` 生成时因为 `grain` 缺失而产出错误的 Mapping 草稿。

---

### 4.2 幂等 Hash 缓存

**设计原则**：对于相同的输入，LLM 应该返回缓存结果，而不是重新调用。这同时解决了稳定性（同输入同输出）和消耗（零 token）两个问题。

**缓存 key**：输入的确定性 hash（prompt + 关键参数），不包含时间戳和随机 seed。

```python
import hashlib, json

def compute_cache_key(agent_name: str, inputs: dict) -> str:
    # 排序保证 key 与 dict 顺序无关
    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return f"{agent_name}:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"

def call_with_cache(agent_name: str, inputs: dict, llm_fn):
    key = compute_cache_key(agent_name, inputs)
    cached = cache_store.get(key)
    if cached:
        return cached
    result = llm_fn(inputs)
    cache_store.set(key, result, ttl=3600)  # 1 小时 TTL
    return result
```

✅ **Good Case**：开发人员在步骤 1 完成后，修了一个 typo 重新触发步骤 1。输入 hash 未变，直接返回缓存的 demand-understanding，跳过 LLM 调用。既省 token，也保证两次结果完全一致。

❌ **Bad Case**：没有缓存，每次重跑步骤 1 都重新调用 LLM。由于 LLM 的随机性，两次产出的 `upstream_candidates` 顺序或措辞略有不同，TL 评审时困惑「昨天和今天结论不一样」，信任度下降。

---

### 4.3 关键字段 Null 检测

**设计原则**：关键字段（会影响后续步骤的字段）一旦为 null 或空，必须立即终止并报错，不允许带着 null 值往下走。宁可让流程失败，不要让幻觉静默传播。

**关键字段定义**（各 Agent 的核心产出）：

| Agent | 不允许为 null 的字段 |
|-------|-------------------|
| 需求理解 | `grain`, `feasibility`, `upstream_candidates` |
| 模型设计 | `table_name`, `fields`, `tl_review_conclusion` |
| ETL 方案设计 | `upstream_table`, `field_mappings` |
| 测试方案设计 | `test_cases` |
| 上线发布 | `release_conclusion` |

```python
CRITICAL_FIELDS = {
    "demand_understanding": ["grain", "feasibility", "upstream_candidates"],
    "model_design": ["table_name", "fields", "tl_review_conclusion"],
}

def check_critical_fields(agent_name: str, output: dict) -> None:
    for field in CRITICAL_FIELDS.get(agent_name, []):
        if output.get(field) is None or output.get(field) == []:
            raise CriticalFieldNullError(
                f"Agent [{agent_name}] 关键字段 [{field}] 为空，"
                f"流程终止，请检查输入或人工补充"
            )
```

✅ **Good Case**：模型设计 Agent 产出中 `tl_review_conclusion` 为 null（TL 还没评审），步骤 3 的 ETL 方案设计 Agent 启动时检测到该字段为 null，输出 `"前置人工项未完成：model-design.md §三 TL 评审结论 尚未填写"` 并拒绝继续，符合 MRD 中的门控要求。

❌ **Bad Case**：`tl_review_conclusion` 为 null 时，ETL Agent 继续执行，基于一个未评审的模型设计生成了 Mapping 草稿，开发人员照着实现，TL 后来驳回模型设计，所有产出物作废。

---

## 五、稳定性专项

### 5.1 执行终止保证

任何 Agent 都必须有明确的终止条件，防止无限循环或递归。

| 参数 | 建议值 | 说明 |
|-----|------|-----|
| `max_retry` | 2 | 单次工具调用或 LLM 调用的最大重试次数 |
| `max_plan_depth` | 5 | Agent 自主规划的最大步骤深度 |
| `max_turns` | 20 | 单次 Agent 执行的最大对话轮次 |
| `timeout_seconds` | 120 | 单次 Agent 执行的超时时间 |

```python
class AgentExecutor:
    def __init__(self, max_turns=20, timeout_seconds=120):
        self.max_turns = max_turns
        self.timeout = timeout_seconds
        self.turn_count = 0

    def run(self, task):
        with TimeoutContext(self.timeout):
            while self.turn_count < self.max_turns:
                result = self.step(task)
                self.turn_count += 1
                if result.is_terminal:
                    return result
            raise MaxTurnsExceeded(f"Agent 超过最大轮次 {self.max_turns}，强制终止")
```

✅ **Good Case**：步骤 1 的需求理解 Agent 与用户来回澄清歧义，第 20 轮时触发 `MaxTurnsExceeded`，输出 `"需求澄清轮次超限，请检查需求文档是否存在根本性歧义，建议人工与消费方直接沟通后重新触发"` 并终止。

❌ **Bad Case**：Agent 进入「请确认 → 好的，继续 → 再请确认」的死循环，因为没有轮次上限，一直运行到 token 耗尽，费用飙升且无任何产出。

---

### 5.2 行为漂移检测

**设计原则**：等价输入应该产出等价结果。上线前和定期回归时，对每个 Agent 做等价输入测试。

**测试方法**：为每个 Agent 准备 3 种等价表达的相同需求，运行后对核心字段做 diff 比对。

```python
EQUIVALENT_INPUTS = [
    "新建一张 ADM 层的订单日汇总表，粒度是天+渠道",
    "需要在 ADM 层建一个表，按天和渠道汇总订单数据",
    "adm层建表，日级渠道维度的订单汇总",
]

def test_behavior_stability(agent, inputs: list[str]) -> StabilityReport:
    results = [agent.run(i) for i in inputs]
    diff = compare_core_fields(results)
    return StabilityReport(
        passed=all(d.is_equivalent for d in diff),
        divergent_fields=[d.field for d in diff if not d.is_equivalent]
    )
```

**核心字段等价标准**（不要求措辞一致，要求语义一致）：
- `grain`：粒度描述语义相同
- `scenario`：场景类型完全一致（枚举值）
- `upstream_candidates`：候选上游表集合相同（允许顺序不同）
- `feasibility`：可行性结论一致

✅ **Good Case**：三种输入都产出 `scenario: "新建表"`，`grain` 描述略有措辞差异但语义一致（「天+渠道维度」vs「按天按渠道」），判定为稳定。

❌ **Bad Case**：输入 1 产出 `feasibility: "可行"`，输入 2 产出 `feasibility: "有条件可行"`。两种等价输入得到不同的可行性结论，说明 LLM 在临界情况下行为不稳定，需要检查 prompt 设计或添加更明确的判断规则。

---

### 5.3 Token 斜率监控

**设计原则**：对每次 Agent 执行记录 token 消耗，设置告警阈值。Token 斜率异常（单步消耗比历史 p50 高 3 倍以上）时自动中断。

```python
TOKEN_BUDGET = {
    "demand_understanding": 8000,   # 输入 + 输出总 token 上限
    "model_design": 6000,
    "etl_design": 10000,
    "test_design": 8000,
    "development": 12000,
}

def check_token_budget(agent_name: str, input_tokens: int) -> None:
    budget = TOKEN_BUDGET.get(agent_name)
    if budget and input_tokens > budget * 0.8:
        logger.warning(f"[{agent_name}] 输入 token 已达预算 80%（{input_tokens}/{budget}），触发输入压缩")
```

✅ **Good Case**：ETL 方案设计 Agent 的输入 token 达到 8000（预算 80%），自动触发需求文档压缩，将 demand-understanding.md 中的非关键段落替换为摘要，把输入压到 6000 以内后再调用 LLM。

❌ **Bad Case**：不做任何 token 监控，某次因为需求文档特别长，单步消耗 35000 token，成本是正常的 4 倍，且因为超过模型最大 context 导致截断出现幻觉字段。

---

### 5.4 状态一致性保护

**设计原则**：关键参数（`target_table`、`scenario`、`step`）在 Agent 执行全程必须不可变。一旦这些参数在中途被覆盖，后续所有产出物的前提都错了。

**实现方式**：关键参数在 session 开始时锁定，存入只读配置对象，不允许通过对话历史更新。

```python
from dataclasses import dataclass, field
from typing import ClassVar

@dataclass(frozen=True)  # frozen=True 保证不可变
class SessionContext:
    target_table: str
    scenario: str  # "新建表" | "新增字段" | "修改字段"
    step: int
    triggered_at: str

# 使用示例
ctx = SessionContext(
    target_table="dw_adm_order_daily",
    scenario="新建表",
    step=1,
    triggered_at="2026-06-10T10:00:00"
)
# ctx.target_table = "other_table"  # 这行会抛出 FrozenInstanceError
```

✅ **Good Case**：用户在步骤 1 进行到一半时，发了一条 `"顺便说一下，另一张表 dw_adm_user 也要建"`。因为 `target_table` 是不可变的，Agent 识别到这是对话干扰，回应 `"检测到对另一张表的需求，当前流程仅处理 dw_adm_order_daily，dw_adm_user 请新开一次 Agent 触发"`。

❌ **Bad Case**：Agent 把对话中提到的第二张表名写入了当前 session 的 `target_table`，后续步骤全部在处理 `dw_adm_user`，但文件名和血缘记录仍然是 `dw_adm_order_daily`，造成混乱。

---

## 六、消耗优化

### 6.1 可固化为代码的任务识别

在设计每个 Agent 步骤时，首先问：**这个任务能用代码完成吗？** 能用代码完成的，一律不给 LLM。

| 任务 | 应该用代码 | 不该用 LLM |
|-----|-----------|-----------|
| 字段命名规范校验（`dw_adm_xxx` 格式）| ✅ 正则 | ❌ 让 LLM 判断 |
| 计算字段数量 / 测试用例数量 | ✅ `len()` | ❌ 让 LLM 数 |
| 文档模板填充（已知结构的占位符替换）| ✅ Jinja2 模板 | ❌ 让 LLM 生成全文 |
| 判断表是否存在于元数据平台 | ✅ API 调用 | ❌ 让 LLM 推断 |
| 检查 DDL 语法合法性 | ✅ SQL Parser | ❌ 让 LLM 审查 |
| 生成 ALTER TABLE 语句（结构固定）| ✅ 字符串模板 | ❌ 让 LLM 生成 |
| 从已有字段口径推断指标业务含义 | ❌ 代码做不了 | ✅ 给 LLM |
| 识别需求描述中的粒度变更信号 | ❌ 代码做不了 | ✅ 给 LLM |

---

### 6.2 分级调用策略

不是每个步骤都需要最强的模型。按任务复杂度选择模型，可以在不损失质量的前提下大幅降低成本。

| 复杂度 | 适用任务 | 推荐模型 | 相对成本 |
|-------|---------|---------|---------|
| 低 | 格式转换、简单摘要、术语标准化 | Haiku 4.5 | ~0.05× |
| 中 | 结构化信息提取、模板填充 | Sonnet 4.6 | ~1× |
| 高 | 复杂推理、口径判断、冲突识别 | Sonnet 4.6 / Opus 4.8 | ~1× / ~5× |

**数仓 Code Agent 各步骤建议**：

| Agent 步骤 | 复杂度 | 推荐模型 |
|-----------|-------|---------|
| 步骤 1 需求理解（信息提取 + 粒度变更识别）| 高 | Sonnet 4.6 |
| 步骤 2 模型设计 | 高 | Sonnet 4.6 |
| 步骤 3 ETL 方案（字段 Mapping 生成）| 中 | Sonnet 4.6 |
| 步骤 4 测试方案（SQL 生成，结构固定）| 中 | Sonnet 4.6 |
| 步骤 5 开发实现（SQL 代码生成）| 中 | Sonnet 4.6 |
| 步骤 6 数据测试（执行结果解读）| 中 | Sonnet 4.6 |
| 步骤 7 上线发布（规则判断，大部分可固化）| 低-中 | Haiku 4.5 |
| 步骤 8 运维（异常摘要、归因）| 中 | Sonnet 4.6 |
| 输入摘要压缩（辅助）| 低 | Haiku 4.5 |

---

### 6.3 Prompt 模板缓存（Prefix Caching）

**设计原则**：所有 Agent 的 system prompt 和规范文档内容应该固定在对话前缀，利用 Anthropic API 的 prompt caching 机制，重复调用时这部分不计费。

```python
# system prompt 中的规范文档内容 > 1024 token，满足 prefix caching 触发条件
# 每次调用新需求时，只有 user message 部分是新 token，system prompt 命中缓存
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": ADM_STANDARDS_CONTENT,  # 规范文档，约 3000 token
                "cache_control": {"type": "ephemeral"}  # 标记为可缓存
            },
            {
                "type": "text",
                "text": user_requirements  # 每次不同的需求输入
            }
        ]
    }
]
```

✅ **Good Case**：ADM 层规范文档（约 3000 token）作为 prompt 前缀固定，每个 Agent 步骤都需要引用。通过 prefix caching，这 3000 token 在第二次调用起缓存命中，实际新增费用约为 10% 的缓存读取成本，而非 100% 的输入 token 成本。

---

## 七、三角权衡决策矩阵

遇到具体取舍场景时，参照此表决策：

| 场景 | 推荐决策 | 理由 |
|-----|---------|-----|
| 增加输入校验但 latency +50ms | ✅ 加，鲁棒优先 | 一次幻觉传播的修复成本远超 50ms latency |
| 增加幂等缓存但需要额外 Redis | ✅ 加，双赢 | 缓存降消耗、提稳定，边际存储成本极低 |
| 用 LLM 做参数校验（省开发时间）| ❌ 不加，用代码 | LLM 校验本身不稳定，且引入额外消耗 |
| 不做行为漂移测试（赶进度）| ❌ 不跳过 | 漂移是隐性 bug，发现时成本最高 |
| 超过重试上限后静默跳过继续 | ❌ 不允许 | 带脏数据继续比终止危害更大 |
| 为所有步骤用最强模型（保质量）| ❌ 按复杂度分级 | 低复杂度步骤用强模型是浪费，不提升质量 |
| Token 超预算时继续执行（省时间）| ❌ 先压缩再执行 | 超预算继续执行会触发截断，产出幻觉 |
| 置信度 0.65 时继续执行（避免打扰用户）| ❌ 标注警告或澄清 | 低置信度推断传播到后续步骤代价极高 |

---

## 八、常见反模式速查

| # | 反模式 | 正确做法 |
|---|-------|---------|
| 1 | 让 LLM 校验必填参数 | 代码层 required 字段列表校验，不进入 LLM |
| 2 | 在 prompt 里描述重试策略 | 重试逻辑在代码层（指数退避 + 次数上限） |
| 3 | 接受 LLM 的自由文本输出并正则解析 | tool-calling / structured output 强制 JSON |
| 4 | 无限重试直到成功 | max_retries=2，超限后终止并告知用户 |
| 5 | 把低置信度输出静默往下传 | confidence < 0.6 触发澄清，< 0.8 标注警告 |
| 6 | session 中关键参数可被对话覆盖 | frozen 数据结构，关键参数锁定不可变 |
| 7 | 所有步骤用同一个最强模型 | 按复杂度分级，低复杂度用 Haiku |
| 8 | 规范文档每次重新发送给 LLM | prefix caching 标记为可缓存 |
| 9 | 不做等价输入稳定性测试 | 每个 Agent 上线前跑 3 种等价输入对比 |
| 10 | 校验失败时静默使用残缺输出继续 | 校验失败必须终止或重试，绝不静默传播 |
