# confrontation-declaration Specification

## Purpose

结构化用户立场声明，必须引用 confrontation evidence 序号，满足 PO-03 审计留痕。

## Requirements

### Requirement: Declaration JSON schema

系统 SHALL 定义 `ConfrontationDeclaration` schema（见 design D1），包含 stance、adopted/rejected sides、evidence refs、rejection_rationale、confidence。

#### Scenario: 非法 stance
- **WHEN** stance 不在允许枚举内
- **THEN** validator SHALL 拒绝并返回明确原因

### Requirement: Evidence ref validation

`ConfrontationDeclarationValidator` SHALL 纯规则校验所有 refs 落在对应 side 的 index 范围内。

#### Scenario: 越界 ref
- **WHEN** `rejected_evidence_refs.bear` 含 `[99]` 但 bear 仅 3 条
- **THEN** SHALL 拒绝 declare

#### Scenario: 拒绝无 rationale
- **WHEN** rejected refs 非空但 rejection_rationale 为空
- **THEN** SHALL 拒绝 declare

### Requirement: Single successful declare per confrontation

每个 `confrontation_id` SHALL 最多一条 `declare_status=ok` 记录（V1 不可覆盖）。

#### Scenario: 重复 declare
- **WHEN** 对已 declare 成功的 id 再次 submit
- **THEN** SHALL 拒绝并提示已有声明

### Requirement: Persistence

成功 declare SHALL 更新 `confrontation_records.declare_json` 与 `declared_at`。

#### Scenario: 成功落库
- **WHEN** validator 通过
- **THEN** `confront show` SHALL 可读到 declare 字段
