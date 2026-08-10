# llm-narrative-core Specification

## Purpose
TBD - created by archiving change add-llm-narrative-core. Update Purpose after archive.
## Requirements
### Requirement: LLMClient 走 OpenAI 兼容协议且 Token 不入库
系统 SHALL 提供 `LLMClient`，通过 OpenAI 兼容的 `chat.completions` 接口调用任意兼容 provider（如 DeepSeek、Qwen、Kimi、自部署网关）。配置项 `base_url`、`model`、`api_key` SHALL 从 `config/app.yaml` 的 `llm:` 段读取，`api_key` 缺省时 SHALL fallback 到环境变量 `LLM_API_KEY`。API key MUST NOT 写入 Git 跟踪文件或日志明文。

#### Scenario: 从 app.yaml 读取配置初始化 client
- **WHEN** `config/app.yaml` 的 `llm.api_key` 非空
- **THEN** `LLMClient` SHALL 使用该 key 初始化，且不打印明文 key 到日志

#### Scenario: 从环境变量 fallback
- **WHEN** `app.yaml` 未配置 `llm.api_key` 但设置了环境变量 `LLM_API_KEY`
- **THEN** `LLMClient` SHALL 使用环境变量的值初始化

#### Scenario: LLM 未配置时不可用
- **WHEN** `app.yaml` 无 `llm:` 段且环境变量 `LLM_API_KEY` 未设置
- **THEN** 系统 SHALL 不实例化 `LLMClient`，任何调用方尝试 `narrate()` SHALL 收到 `ok=False, error="LLM 未配置"`，不抛出未捕获异常

### Requirement: narrate() 输入卫兵（Input Guard）
`narrate(evidence: dict, schema: dict, instruction: str) -> NarrateResult` SHALL 在调用 LLM 前校验 `evidence` 非空；`evidence` 序列化后超过配置阈值（默认 8000 token 估算）时 SHALL 截断或摘要，不将超长内容原样发送。

#### Scenario: evidence 为空时拒绝调用
- **WHEN** `narrate(evidence={}, ...)` 被调用
- **THEN** SHALL 返回 `ok=False, error="evidence 为空"`，不发起 LLM API 调用

#### Scenario: 超长 evidence 触发截断
- **WHEN** `evidence` 序列化后超过阈值
- **THEN** SHALL 对非关键字段截断/摘要后再发起调用，且日志记录截断发生

### Requirement: narrate() 强制结构化 JSON 输出
`narrate()` 的 LLM 调用 SHALL 要求模型输出符合传入 `schema` 的 JSON；实现 SHALL 优先使用 provider 的结构化输出模式（如 `response_format={"type":"json_object"}`），不支持时 SHALL fallback 到「prompt 显式要求 JSON + 剥离 markdown code fence 后解析」，两种路径的输出都 MUST 经过下述 Output Guard 的 schema 校验。

#### Scenario: provider 支持 JSON mode
- **WHEN** provider 接受 `response_format` 参数
- **THEN** SHALL 使用该参数请求结构化输出

#### Scenario: provider 不支持 JSON mode 时 fallback 解析
- **WHEN** provider 返回错误表明不支持 `response_format`
- **THEN** SHALL 改用纯 prompt 指令要求 JSON，并对响应做 markdown code fence 剥离后再 `json.loads`

### Requirement: narrate() 输出卫兵——Schema 校验与重试
`narrate()` 的 LLM 输出 SHALL 经过 JSON Schema 校验；校验失败时 SHALL 重试，重试时 SHALL 将校验错误反馈给 LLM 作为纠错上下文，最多重试 2 次；超过重试上限 SHALL 返回 `ok=False` 并携带最后一次校验错误，不将不合格输出传递给调用方。

#### Scenario: 首次输出不合格，重试后成功
- **WHEN** 第一次 LLM 输出缺少 schema 要求的必填字段
- **THEN** SHALL 自动构造纠错 prompt 重新调用，若第二次通过校验则返回该结果

#### Scenario: 重试上限耗尽仍不合格
- **WHEN** 连续 3 次（初次 + 2 次重试）输出均不通过 schema 校验
- **THEN** SHALL 返回 `ok=False, error` 携带 schema 校验错误详情，终止流程

### Requirement: narrate() 输出卫兵——Grounded 数值锚定校验
`narrate()` SHALL 对 LLM 输出文本中的数值 token（阿拉伯数字，含常见单位如 亿/万/%/倍）做锚定校验：每个数值 MUST 能在输入 `evidence` 的序列化文本中找到对应或可换算匹配的数值；若发现输出含 evidence 中不存在的数值，SHALL 判定为 grounded 校验失败。

#### Scenario: 输出数值均可在 evidence 中找到
- **WHEN** LLM 输出提到 "PE 5.5 倍" 且 evidence 中含 `pe_ratio: 5.5`
- **THEN** grounded 校验 SHALL 通过

#### Scenario: 输出含 evidence 之外的编造数值
- **WHEN** LLM 输出提到 "净利润增长 40%" 但 evidence 中没有任何数值可映射到 40%
- **THEN** grounded 校验 SHALL 判定失败，触发与 schema 校验失败相同的重试/终止流程

### Requirement: narrate() 置信度暴露与分级处理
`NarrateResult` SHALL 包含 `confidence: float`（0-1）。`confidence < 0.6` 时 `narrate()` SHALL 返回 `ok=False`；`0.6 <= confidence < 0.8` 时 SHALL 返回 `ok=True` 但附加 `low_confidence_warning=True`；`confidence >= 0.8` 时正常返回。

#### Scenario: 低置信度判定失败
- **WHEN** LLM 输出的 `confidence=0.5`
- **THEN** `narrate()` SHALL 返回 `ok=False`

#### Scenario: 中等置信度附加警告
- **WHEN** LLM 输出的 `confidence=0.7`
- **THEN** `narrate()` SHALL 返回 `ok=True, low_confidence_warning=True`

### Requirement: narrate() 幂等缓存
`narrate()` SHALL 对相同的 `(instruction, schema, evidence)` 组合（规范化序列化后取 hash）使用缓存结果，不重复调用 LLM API；缓存存储于 SQLite 表 `llm_narrate_cache`。调用方 MAY 传入 `force_refresh=True` 绕过缓存。

#### Scenario: 相同输入命中缓存
- **WHEN** 对同一 `evidence` 第二次调用 `narrate()`（其他参数不变，`force_refresh` 未传）
- **THEN** SHALL 直接返回缓存结果，不发起新的 LLM API 调用

#### Scenario: force_refresh 绕过缓存
- **WHEN** 调用 `narrate(..., force_refresh=True)`
- **THEN** SHALL 忽略已有缓存，重新调用 LLM API 并更新缓存

### Requirement: narrate() 调用失败的鲁棒处理
`narrate()` 对 LLM API 的超时、限流（429）、5xx 错误 SHALL 在代码层实现指数退避重试（最多 2 次），超过重试上限 SHALL 返回 `ok=False, error` 携带可诊断信息，不抛出未捕获异常。

#### Scenario: 限流后重试成功
- **WHEN** 第一次调用返回 429，第二次重试成功
- **THEN** `narrate()` SHALL 返回成功结果，日志记录发生过重试

#### Scenario: 重试耗尽后明确失败
- **WHEN** 连续 3 次调用均超时
- **THEN** `narrate()` SHALL 返回 `ok=False, error="LLM 调用超时，已重试 2 次"`，不抛异常

