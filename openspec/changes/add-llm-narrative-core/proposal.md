## Why

产品路线图（PO-02 LLM 综合报告、PO-03 红蓝军对抗）都需要「确定性计算结果 → 可读叙事」的能力，但仓库目前**零 LLM 接入基建**：无 client 封装、无 provider 配置、无结构化输出校验、无防幻觉护栏。直接在某个具体功能里现写一套，会导致 PO-02 与 PO-03 各自实现一份不一致、未经校验的 LLM 调用逻辑，违反 `docs/agent-engineering-quality.md` 的三层防御原则（确定性数值不可由 LLM 改写/编造）。

本 change 先把可复用的 LLM 叙事基建建好，作为 PO-02/PO-03 的共同地基。

## What Changes

- 新增 `LLMClient`：走 OpenAI 兼容 `chat.completions` 协议，`base_url`/`model`/`api_key` 通过 `config/app.yaml` 的 `llm:` 段配置（同 Tushare token 模式：不入库，支持环境变量 `LLM_API_KEY` fallback）
- 新增 `narrate(evidence, schema, instruction) -> NarrateResult` 核心方法：
  - **Input Guard**：evidence 非空校验、超长截断/摘要
  - **LLM 核**：仅做叙事包装，禁止输出 evidence 之外的新数字/新结论；强制结构化 JSON 输出
  - **Output Guard**：JSON schema 校验 + 重试上限 2 次；**grounded 校验**（输出中的关键数字/实体必须能映射回 evidence，否则判失败）；`confidence` 字段暴露，`< 0.6` 时整体判定为叙事失败
  - **幂等缓存**：evidence 内容 hash 作为 cache key，同一证据集合不重复调用
- 新增 `config/app.yaml` 的 `llm:` 配置段与 `config/app.example.yaml` 占位说明
- 新增依赖：`requirements.txt` 增加 OpenAI 兼容 SDK（`openai>=1.0`，兼容第三方 base_url）

**不包含**（留给下游 change）：
- 不包含任何具体业务叙事内容（红蓝对抗、综合报告的 prompt 与 schema 属于各自 change）
- 不包含 Web/CLI 对外入口

## Capabilities

### New Capabilities
- `llm-narrative-core`：LLM Client 封装、`narrate()` 结构化叙事生成、Input/Output Guard、grounded 校验、幂等缓存

### Modified Capabilities
（无——本 change 不修改现有 capability 的既有需求）

## Impact

- **新增文件**：
  - `src/common/llm/client.py`（`LLMClient` 封装）
  - `src/common/llm/narrator.py`（`narrate()` + Input/Output Guard + grounded 校验 + 缓存）
  - `src/common/llm/models.py`（`NarrateResult`、`NarrateRequest` 等数据结构）
  - `config/app.example.yaml`：新增 `llm:` 段占位说明
  - `test/common/llm/`：单元测试（mock LLM 响应，覆盖 schema 校验失败重试、grounded 校验失败降级、幂等缓存命中）
- **不影响**：`src/service/`、`src/data_provider/`、`src/dao/` 现有模块零改动
- **文档**：`docs/dev/engineering-conventions.md` 补充 `src/common/llm/` 目录说明；无需改 `docs/mrd/`（本 change 不含产品行为，仅基建）
