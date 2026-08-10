## Why

V1 对保险/军工已能识别并提示「专用方法暂缺」，但通用方法仍产出「低估/高估」与安全边际，双轨融合可据此推「买入」——对非金融背景用户是**半诚实**：警告在，行动措辞仍在。更严重的是比亚迪、分众等持仓样本**连识别都没有**，被静默路由为 `value_growth`，单点 DCF/EPV 在制造周期与广告周期上系统性偏乐观或偏悲观，却以专业公允价呈现。

本 change 是 V2 专用估值之前的「第 0 刀诚实层」：先停止误导，再谈情景 DCF / Cyclical / EV/NBV。

## What Changes

- **名单（本期固定）**
  - code 白名单：`002594`（比亚迪）→「成长+制造周期」；`002027`（分众）→「现金流+广告周期」
  - 行业升级：保险、军工（含平安、中船等）与持仓**同一压制标准**（补完 T-15 半诚实缺口）
- **三层压制**
  1. 精确警告：缺什么方法 + V1 错用时容易如何偏 + 「不能作为买卖依据」
  2. 主评估改写：`assessment` →「方法暂不适用」；保留公允区间/MOS 仅作对照；confidence 降级
  3. 双轨：价值评级强制 `UNKNOWN`，融合**不得**因假「价值低估」推买入（技术面信号可单独保留）
- **路由**：比亚迪/分众 SHALL 短路为 `unknown`（不再静默 `value_growth`）；保险/军工保持既有 `unknown` 短路
- **不做**：情景 DCF、Cyclical port、EV/NBV、华测成长原型、按「汽车/传媒」行业名海量扩容

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `value-prototype-router`：code 级 V2 暂缺名单 + 统一的诚实缺口描述（code 优先于行业）；比亚迪/分众路由为 `unknown`
- `value-analyzer`：诚实降级时改写主评估、降 confidence、透出「方法不可用于决策」标记；加强 warning 文案
- `dual-track-analyzer`：诚实降级时 `value_rating` 强制 `UNKNOWN`，融合矩阵不吃假价值优势
- `cli-report-value`：文本报告对诚实降级标的突出警告，主评估展示「方法暂不适用」，避免把对照用 MOS 读成买入依据

## Impact

- **代码**：`src/service/value/router.py`、`analyzer.py`、`models/analysis_result.py`；`src/service/dual_track/signal_fusion.py`（及必要时 `analyzer.py` / evidence 分桶）；价值面 CLI 格式化（`apps` / `service/report` 中 format value 路径）
- **测试**：router / analyzer / dual-track / report value 相关单测；样例 code `002594`、`002027`、`601318`、军工行业
- **文档**：`docs/mrd/features/value-analysis.md`（场景 5 扩展为三层压制；§2.2 / T-15 状态）；`docs/mrd/roadmap-todo.md` 可标注「V2 诚实层」
- **依赖**：建立在已归档的 `add-industry-prototype-router`、`add-prototype-fallback-message` 之上；与人工 override 共存——**显式覆盖为已实现原型时，本期不强制诚实压制**（用户知情选择）
- **非 BREAKING API**：新增字段须带默认值，既有 JSON 消费者可忽略
