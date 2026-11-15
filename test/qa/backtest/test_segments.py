"""R3 三段样本切分（TC-R03-01..03）。

锚点：spec R3；design §4.1（T2-fix-4 后）`BacktestConfig.segments: tuple[Segment, ...]`（必须键）+
`Segment` 枚举；区间起止属预注册输入（`cfg_raw["segments"]`，测试自持），结果/导出层用
`LedgerExportRow.segments: tuple[str, ...]` 表达各段区间；§4.2 R3「每段独立可用状态；跨段报告显式列出各段」。
"""

from __future__ import annotations

import pytest


def test_tc_r03_01_default_three_segments_reported(cfg, cfg_raw, models):
    """TC-R03-01（R3 Scenario1）：默认切分含训练/验证/样本外三段，区间起止来自预注册输入。"""
    segments = cfg.segments
    assert len(segments) == 3
    assert set(segments) == {models.Segment.TRAIN, models.Segment.VALIDATION, models.Segment.OUT_OF_SAMPLE}

    for name, bounds in cfg_raw["segments"].items():
        assert len(bounds) == 2 and bounds[0] < bounds[1], f"{name} 需给出有效起止"
        assert name in {item.value for item in models.Segment}


def test_tc_r03_02_cross_segment_request_is_guarded(cfg, cfg_raw, models):
    """TC-R03-02（R3 Scenario2）：区间不可跨段——三段互不重叠、枚举无「跨段」成员。

    说明：§4.1 未单列「跨段请求」入口（仅 `BacktestConfig.segments` 与 `Segment` 枚举），
    故本用例断配置层不变量；真正的拒绝由 T5 端到端复跑 TC-EXIT-02 的退出码面复核。
    """
    ordered = [cfg_raw["segments"][name] for name in ("train", "validation", "out_of_sample")]
    for earlier, later in zip(ordered, ordered[1:]):
        assert earlier[1] < later[0], "三段必须互不重叠（否则跨段请求无法被识别）"
    assert {item.value for item in cfg.segments} == {"train", "validation", "out_of_sample"}
    with pytest.raises(ValueError):
        models.Segment("cross_segment")


def test_tc_r03_03_training_segment_reusable(registry, models, result_rows, registry_path):
    """TC-R03-03（R3 Scenario3）：训练段可重复评估 3 次，台账可数（同一规则训练段评估次数 = 3）。"""
    for index in range(3):
        experiment_id = registry.next_experiment_id("hyp-001")
        registry.append(models.ExperimentRecord(
            experiment_id=experiment_id, hypothesis_id="hyp-001", params={"ma_days": 60},
            segment=models.Segment.TRAIN, K=index + 1, verdict=models.Verdict.INCONCLUSIVE, metrics={},
            prereg_commit="deadbeef", data_version="test-v1", adjust_mode=models.AdjustMode.HFQ,
            timestamps={"created_at": "2026-01-02T09:30:00+08:00"}, parent_experiment_id=None))

    rows = [row for row in result_rows(registry_path) if row["segment"] == models.Segment.TRAIN.value]
    assert len(rows) == 3
