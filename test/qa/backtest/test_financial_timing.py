"""R11 财务字段按公告日对齐（TC-R11-01..02）。

锚点：spec R11；design §4.1（T2-fix-4 修正）`FinancialRecord.visible_from`：**有 ann_date = ann_date**
（缺 ann_date 才回退保守截止日 4/8/10 月底，spec 优先，不是 max()）、
`load_financials_point_in_time(codes, as_of, *, loader)`、§4.2 R11「回退须标注」。
"""

from __future__ import annotations


def test_tc_r11_01_annual_report_visible_only_after_announcement(load, models):
    """TC-R11-01（R11 Scenario1）：公告日 2024-04-25 → 04-24 不可见、04-25 可见。"""
    data = load("service.backtest.data")
    record = models.FinancialRecord(code="000001", report_period="20231231",
                                    ann_date="2024-04-25", end_date="2023-12-31",
                                    visible_from="2024-04-25")

    def _loader(codes, as_of):
        return {"000001": (record,)}

    before = data.load_financials_point_in_time(["000001"], "2024-04-24", loader=_loader)
    after = data.load_financials_point_in_time(["000001"], "2024-04-25", loader=_loader)

    assert before.get("000001", ()) == (), "公告日之前不得进入可用数据（spec R11 Scenario1）"
    assert [item.report_period for item in after["000001"]] == ["20231231"]
    assert after["000001"][0].visible_from == "2024-04-25"


def test_tc_r11_02_missing_ann_date_falls_back_and_flags(load, models):
    """TC-R11-02（R11 Scenario2）：缺公告日 → 年报 4 月底 / 半年报 8 月底 / 三季报 10 月底回退并标注。"""
    data = load("service.backtest.data")
    cases = (("20231231", "2024-04-30"), ("20240630", "2024-08-31"), ("20240930", "2024-10-31"))

    for report_period, expected in cases:
        record = models.FinancialRecord(code="000001", report_period=report_period,
                                        ann_date=None, end_date=None, visible_from=expected)

        def _loader(codes, as_of, _record=record):
            return {"000001": (_record,)}

        visible = data.load_financials_point_in_time(["000001"], expected, loader=_loader)["000001"]

        assert visible, f"{report_period} 回退后应在 {expected} 可见"
        assert visible[0].visible_from == expected, f"{report_period} 的保守截止日应为 {expected}"
        assert visible[0].ann_date is None, "缺公告日必须可被识别（元数据标注回退）"
