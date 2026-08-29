# red-blue-confrontation Delta Specification

## MODIFIED Requirements

### Requirement: Evidence bucket output includes stable indices

`EvidenceBucketer` 的分桶结果在对外 JSON 序列化时 SHALL 为每条 bull/bear evidence 附加稳定 1-based index，供 declare 与 persona 引用。

#### Scenario: 分桶后序号稳定
- **WHEN** 对同一 `DualTrackReport` 两次分桶
- **THEN** 相同顺序的 evidence 文本 SHALL 映射到相同 index
