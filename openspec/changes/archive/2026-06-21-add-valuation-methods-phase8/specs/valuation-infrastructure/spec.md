## MODIFIED Requirements

### Requirement: ValuationEngine 注册并批量运行方法
系统 SHALL 提供 `ValuationEngine`，支持按名称注册估值方法、单独运行（`run_single`）
或批量运行（`run_all`）。`run_all` SHALL 在单个方法抛出异常时不中断，
将异常包装为 `ValuationResult(error=str(exc))`。

`default_engine()` SHALL 预注册 Phase 0–8 全部 method_key（共 23 个）：
graham_number、graham_formula、ncav、pb、residual_income、ddm、two_stage_ddm、epv、
owner_earnings、dcf、reverse_dcf、altman_z、piotroski_f、beneish_m、
peg、garp、rule_of_40、ev_ebitda、magic_formula、pe_relative、pb_relative、
value_trap、sbc。

评分类方法（altman_z、piotroski_f、beneish_m、rule_of_40、value_trap、sbc）SHALL 在 `details` 中设置
`output_type = "score"`，供下游聚合层排除公允价输入。

#### Scenario: 注册并单独运行方法
- **WHEN** `engine.register("graham_number", GrahamNumber())` 后调用 `engine.run_single("graham_number", stock_data)`
- **THEN** 返回 `ValuationResult`，`method == "Graham Number"`

#### Scenario: 批量运行某方法内部抛异常不中断
- **WHEN** `run_all` 中某方法 `calculate()` 抛出 `RuntimeError`
- **THEN** 该方法对应结果的 `error` 非空，其余方法结果正常返回，整体 `run_all` 不抛出异常

#### Scenario: default_engine 包含 Phase 0-8 全部 method_key
- **WHEN** 调用 `default_engine()` 并检查注册表
- **THEN** 包含全部 23 个 key，含 value_trap 和 sbc
