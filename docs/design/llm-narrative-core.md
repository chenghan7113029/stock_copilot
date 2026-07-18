# LLM 叙事基建（llm-narrative-core）

> 对应 OpenSpec change：`add-llm-narrative-core`  
> 详细规范：`openspec/specs/llm-narrative-core/`（归档后）与 `docs/agent-engineering-quality.md`

## 职责

提供通用 `narrate(evidence, schema, instruction) -> NarrateResult`，将**确定性证据**包装为结构化 JSON 叙事。不绑定具体业务（红蓝对抗、综合报告由消费方提供 prompt/schema）。

## 模块路径

| 路径 | 说明 |
|------|------|
| `src/common/llm/client.py` | OpenAI 兼容 `LLMClient`（重试、JSON mode fallback） |
| `src/common/llm/narrator.py` | `narrate()` + Input/Output Guard |
| `src/common/llm/grounding.py` | 数值锚定 grounded 校验 |
| `src/common/llm/models.py` | `NarrateResult` / `ChatResult` |
| `src/dao/llm_narrate_cache_repo.py` | SQLite 幂等缓存（实现 `NarrateCache` Protocol） |
| `common.config_loader.resolve_llm_config` | `llm:` 配置 / `LLM_API_KEY` |

## 配置

```yaml
llm:
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  api_key: ""          # 或环境变量 LLM_API_KEY
  max_evidence_chars: 24000
```

未配置时 `narrate()` 返回 `ok=False, error="LLM 未配置"`，不抛异常。

## 依赖方向

`service/*` → `common.llm.narrate`；缓存可选注入 `LLMNarrateCacheRepo`。`common/llm` **不** import `dao` / `service`。
