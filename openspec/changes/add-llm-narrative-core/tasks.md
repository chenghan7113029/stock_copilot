## 1. 配置与依赖

- [x] 1.1 `requirements.txt` 新增 `openai>=1.0`（OpenAI 兼容 SDK，支持自定义 `base_url`）
- [x] 1.2 `config/app.example.yaml` 新增 `llm:` 段占位说明（`base_url` / `model` / `api_key` 注释，标注环境变量 `LLM_API_KEY` fallback，勿提交真实 key）
- [x] 1.3 `src/common/config_loader.py`（或等价位置）确认/新增 `resolve_llm_config(config) -> LLMConfig | None`（无配置且无环境变量时返回 None，参考现有 `resolve_tushare_token` 模式）

## 2. LLMClient 封装

- [x] 2.1 新建 `src/common/llm/client.py`：`LLMClient` 类，基于 `openai` SDK 的 `chat.completions.create`，构造函数接受 `base_url`/`model`/`api_key`
- [x] 2.2 实现指数退避重试（超时/429/5xx，最多 2 次），失败时返回明确错误而非抛未捕获异常
- [x] 2.3 实现 JSON mode 优先 + fallback 到 prompt 指令 + markdown code fence 剥离解析
- [x] 2.4 单测 `test/common/llm/test_client.py`：mock `openai` client，覆盖重试成功/重试耗尽/JSON mode 不支持时 fallback

## 3. narrate() Input Guard

- [x] 3.1 新建 `src/common/llm/narrator.py`：`narrate(evidence, schema, instruction, force_refresh=False) -> NarrateResult`
- [x] 3.2 实现 evidence 非空校验（空 evidence 直接返回 `ok=False`，不调用 LLM）
- [x] 3.3 实现 evidence 序列化超长截断/摘要逻辑（阈值可配置，默认约 8000 token 估算）
- [x] 3.4 单测覆盖：空 evidence 拒绝、超长 evidence 触发截断

## 4. narrate() Output Guard — Schema 校验

- [x] 4.1 新建 `src/common/llm/models.py`：`NarrateResult`（`ok`, `data`, `confidence`, `low_confidence_warning`, `error`, `grounded`）
- [x] 4.2 集成 `jsonschema` 校验 LLM 输出；校验失败时构造纠错 prompt 重试（最多 2 次）
- [x] 4.3 重试耗尽后返回 `ok=False` 携带最后一次校验错误
- [x] 4.4 单测覆盖：首次失败重试成功、重试耗尽失败

## 5. narrate() Output Guard — Grounded 数值锚定校验

- [x] 5.1 实现数值 token 提取（正则，覆盖阿拉伯数字 + 常见单位 亿/万/%/倍）
- [x] 5.2 实现 evidence 序列化文本中的数值提取（同一提取逻辑复用）
- [x] 5.3 实现锚定比对：输出数值必须能在 evidence 数值集合中找到（含单位换算的宽松匹配）
- [x] 5.4 grounded 校验失败时触发与 schema 校验失败相同的重试/终止流程
- [x] 5.5 单测覆盖：数值均可锚定通过、含编造数值判定失败并触发重试

## 6. narrate() 置信度处理

- [x] 6.1 要求 LLM 输出 schema 含 `confidence` 字段
- [x] 6.2 实现分级逻辑：`<0.6` → `ok=False`；`0.6~0.8` → `ok=True, low_confidence_warning=True`；`>=0.8` → 正常
- [x] 6.3 单测覆盖三档分级

## 7. narrate() 幂等缓存

- [x] 7.1 `src/dao/models.py` 新增 `LLMNarrateCache` ORM（`cache_key`, `result_json`, `created_at`）
- [x] 7.2 `src/dao/engine.py` 的 `ensure_sqlite_schema()` 补充建表逻辑（同现有列补丁模式）
- [x] 7.3 新建 `src/dao/llm_narrate_cache_repo.py`：`get(cache_key)` / `set(cache_key, result)`
- [x] 7.4 `narrate()` 集成缓存查询/写入；`cache_key = sha256(instruction + schema + 规范化 evidence JSON)`
- [x] 7.5 实现 `force_refresh=True` 绕过缓存逻辑
- [x] 7.6 单测覆盖：相同输入命中缓存（不触发第二次 LLM 调用）、`force_refresh` 绕过缓存

## 8. LLM 未配置降级路径

- [x] 8.1 `narrate()` 顶层检查 `LLMClient` 是否可用（`resolve_llm_config` 返回 None 时不实例化）
- [x] 8.2 未配置时 `narrate()` 直接返回 `ok=False, error="LLM 未配置"`，不发起任何调用
- [x] 8.3 单测覆盖：无配置无环境变量时的降级行为

## 9. 集成测试与文档

- [x] 9.1 编写端到端集成测试脚本（mock LLM 响应，走完整 Input Guard → LLM 核 → Output Guard 链路），验证不依赖真实网络
- [x] 9.2 `docs/dev/engineering-conventions.md` 补充 `src/common/llm/` 目录说明与依赖方向（`common/llm` 不依赖 `service/`，被 `service/` 消费）
- [x] 9.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 10. 归档

- [x] 10.1 确认 `tasks.md` 全部任务完成
- [x] 10.2 合并本 change 的设计要点到 `docs/design/`（如有必要新建 `docs/design/llm-narrative-core.md`，或判断内容量级后决定是否需要独立文档）
- [ ] 10.3 运行 `/opsx-archive add-llm-narrative-core` 归档，同步 specs 到 `openspec/specs/llm-narrative-core/`（**已解冻**：消费方为 `add-llm-comprehensive-report`；可与本 change 一并或随后归档）
