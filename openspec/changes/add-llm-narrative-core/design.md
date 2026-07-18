## Context

`docs/agent-engineering-quality.md` 定义了「三层防御 + LLM 核最小化」框架（输入卫兵 → LLM 核 → 输出卫兵），原文档以数仓 Code Agent 为例，但原则是通用的，本 change 是该框架在 stock_copilot 中的第一次落地。

现状：仓库内 0 处 LLM SDK / client / prompt 基建。`config/app.yaml` 已有 Tushare token 的配置模式（`data_sources.enabled` + env var fallback + gitignore）可直接复用于 LLM key 管理。

下游消费者（尚未实现，属于后续 change）：
- `add-red-blue-confrontation`：红蓝对抗叙事生成
- 未来 PO-02（LLM 综合报告）：双轨报告叙事化

两者都需要「给定一组确定性证据 → 生成结构化、不编造新事实的叙事」这一能力，因此抽象为通用 `narrate()`。

## Goals / Non-Goals

**Goals:**
- 提供 provider 无关（OpenAI 兼容协议）的 LLM client 封装
- 提供 `narrate(evidence, schema, instruction) -> NarrateResult`，实现三层防御的完整链路：Input Guard → LLM 核（强制结构化输出）→ Output Guard（schema 校验 + grounded 校验 + 置信度 + 重试）
- 提供幂等缓存（相同 evidence hash 不重复调用）
- 完全独立于具体业务语义（不感知"红蓝对抗"或"综合报告"的 prompt 内容）

**Non-Goals:**
- 不实现任何具体业务 prompt/schema（属于消费方 change）
- 不实现多轮对话式 Agent（`narrate()` 是单次调用，不维护会话状态）
- 不做 Web UI 或 API 层暴露
- 不解决"由谁来触发联网调用"的产品语义（属于消费方 change，如 CLI 的 `--narrate` flag）

## Decisions

### 决策 1：Provider 抽象为 OpenAI 兼容协议，不做多 SDK 适配层

**选择**：`LLMClient` 直接基于 `openai` Python SDK（`base_url` 可配置指向任意 OpenAI 兼容端点：DeepSeek、Qwen/DashScope、Kimi、Zhipu 等均已支持该协议），不引入 LangChain 等重量级抽象框架。

**理由**：
- 个人项目/V1 规模下，多 provider SDK 适配是过度设计；OpenAI 兼容协议已覆盖国内主流 LLM 服务
- 减少依赖面，降低维护成本
- 若未来需要接入不兼容 OpenAI 协议的 provider，可在 `LLMClient` 内部加 adapter，不影响上层 `narrate()` 接口

**备选方案**：LangChain/LiteLLM 统一多 provider —— 拒绝，因为引入了不必要的抽象层和依赖体积，且这些框架的"智能重试/自动降级"逻辑与本项目"确定性优先、LLM 只做叙事"的哲学冲突（详见 `agent-engineering-quality.md` 反模式 #7）。

### 决策 2：Grounded 校验的实现方式——数字锚定而非语义校验

**选择**：Output Guard 的 grounded 校验采用**数字/关键实体字符串匹配**：从 LLM 输出文本中提取所有数值 token（正则），检查每个数值是否能在输入 `evidence`（序列化后的字符串）中找到（允许合理的格式差异，如千分位、单位换算前后各一次尝试匹配）。若发现输出中存在 evidence 里找不到的数值，判定为 grounded 校验失败。

**理由**：
- 语义级别的"事实核查"（如调用另一个 LLM 做验证）成本高、本身也可能出错，且违反"LLM 核最小化"原则
- 数值锚定是廉价、确定性、可测试的代码逻辑，能拦截最危险的一类幻觉（编造不存在的财务数字/百分比）
- 不追求 100% 拦截所有幻觉（如编造的定性描述无法被数字锚定发现），但优先处理数值幻觉这个最高风险场景

**备选方案**：
- 用第二次 LLM 调用做"自我核查"——拒绝，违反 LLM 核最小化，且二次调用本身也可能幻觉
- 不做 grounded 校验，仅依赖 prompt 里"不要编造数据"的指令——拒绝，`agent-engineering-quality.md` §2.5 明确指出 prompt 指令对 LLM 行为的约束不可靠，必须代码层校验

**已知局限**：正则数值提取无法覆盖所有表达形式（如中文大写数字"三点五亿"），V1 先处理阿拉伯数字 + 常见单位（亿/万/%），已知局限记录在 Risks 一节。

### 决策 3：幂等缓存 key 与存储介质

**选择**：cache key = `sha256(narrate 调用的 instruction + schema + evidence 规范化 JSON)`；存储介质复用现有 SQLite（新增轻量表 `llm_narrate_cache`，而非引入 Redis）。

**理由**：
- 项目当前无 Redis 依赖，个人项目规模下引入新基础设施成本大于收益
- SQLite 已是项目标准持久化介质（`dao/engine.py`），复用降低复杂度
- Cache TTL 可选（V1 不设 TTL，因为 evidence 内容变化时 hash 自然变化，不存在"陈旧缓存"问题——只有 evidence 不变但业务想要新叙事的场景才需要 TTL/强制刷新，V1 暂不支持强制刷新，属已知局限）

### 决策 4：Confidence 阈值复用 agent-engineering-quality.md 既定值

**选择**：`confidence >= 0.8` 直接返回；`0.6~0.8` 返回结果但标注 `low_confidence_warning`；`< 0.6` 整体判定 `narrate()` 失败（返回 `ok=False`），调用方需自行降级（如展示纯证据列表）。

**理由**：直接复用文档已给出的行业阈值参考，不重新发明。

## Risks / Trade-offs

- **[风险] OpenAI 兼容协议在不同 provider 下的 JSON mode 支持程度不一**（有的 provider 支持 `response_format={"type":"json_object"}`，有的仅支持 prompt 指令）→ **缓解**：`LLMClient` 内部先尝试 `response_format`，捕获不支持时的 API 错误后 fallback 到"prompt 显式要求 JSON + 宽松解析（剥离 markdown code fence）"，两种路径都要经过 Output Guard 的 schema 校验，不因为解析方式不同而降低校验标准。
- **[风险] 数值锚定 grounded 校验存在漏报**（定性幻觉、非数字实体编造无法拦截）→ **缓解**：V1 明确该局限，文档标注「grounded 校验覆盖数值类幻觉，不覆盖语义类幻觉」；后续如需更强保障可在消费方 change 补充业务级校验（如红蓝对抗要求反驳内容必须引用证据 ID，而非仅自然语言）。
- **[风险] 缓存无 TTL/强制刷新机制，若业务需要"同一证据重新生成一次不同表达"会被缓存拦住** → **缓解**：`narrate()` 预留 `force_refresh: bool = False` 参数，V1 默认关闭，消费方如有需要可显式传入绕过缓存（不实现自动过期策略）。
- **[风险] LLM API 调用失败（超时/限流/鉴权错误）** → **缓解**：复用 `agent-engineering-quality.md` §2.5 的重试模式（指数退避，最多 2 次），超过重试上限后 `narrate()` 返回 `ok=False` 并携带明确错误原因，不抛出未捕获异常导致调用方崩溃。

## Migration Plan

- 纯新增，无迁移；`config/app.yaml` 若未配置 `llm:` 段，`LLMClient` 不实例化，`narrate()` 调用方需自行处理"LLM 未配置"场景（返回 `ok=False, error="LLM 未配置"`），不影响现有任何功能。
- 回滚：删除 `src/common/llm/` 目录 + 移除 `llm_narrate_cache` 表即可，无其他模块依赖本 change（本 change 不修改任何既有 capability）。

## Open Questions

- Prompt caching（Anthropic/OpenAI 的 prefix caching）是否在 V1 就接入？—— 暂不接入，成本优化留到用量上升后再做（YAGNI），但 `LLMClient` 的消息构造方式（system prompt 与 user content 分离）预留了未来接入的空间。
