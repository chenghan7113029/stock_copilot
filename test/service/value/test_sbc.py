"""SBCAnalysis 单元测试。"""


from service.value.valuation.sbc import SBCAnalysis


class _Stock:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattr__(self, name):
        return None


# ── 测试 ─────────────────────────────────────────────────────────────────────

def test_sbc_none_not_applicable():
    """A 股未披露 SBC → Not Applicable。"""
    stock = _Stock(current_price=1500.0)  # sbc = None
    result = SBCAnalysis().calculate(stock)
    assert result.applicability == "Not Applicable"
    assert result.error is None
    assert result.details["dilution_rating"] == "Not Applicable"


def test_sbc_zero_negligible():
    """SBC = 0 → Negligible；adjusted_eps == eps。"""
    net_income = 1e10
    shares = 1.29e10
    stock = _Stock(
        current_price=1500.0,
        sbc=0.0,
        net_income=net_income,
        shares_outstanding=shares,
        revenue=1.5e11,
        prior_shares_outstanding=shares,
    )
    result = SBCAnalysis().calculate(stock)
    assert result.error is None
    assert result.details["dilution_rating"] == "Negligible"
    assert result.details["sbc_to_net_income"] == 0.0
    expected_eps = net_income / shares
    assert abs(result.details["adjusted_eps"] - expected_eps) < 1e-4


def test_sbc_50pct_severe():
    """SBC/净利润 = 50% → Severe 评级；adjusted_eps < 原始 eps。"""
    net_income = 3e9
    sbc = 1.5e9  # = 50%
    shares = 5.5e10
    stock = _Stock(
        current_price=30.0,
        sbc=sbc,
        net_income=net_income,
        shares_outstanding=shares,
        revenue=1e10,
    )
    result = SBCAnalysis().calculate(stock)
    assert result.error is None
    assert result.details["dilution_rating"] == "Severe"
    assert abs(result.details["sbc_to_net_income"] - 0.5) < 1e-6
    adjusted_eps = result.details["adjusted_eps"]
    raw_eps = net_income / shares
    assert adjusted_eps < raw_eps


def test_prior_shares_none_no_dilution_rate():
    """prior_shares_outstanding = None → annual_dilution_rate 不计算，warnings 说明。"""
    stock = _Stock(
        current_price=50.0,
        sbc=5e8,
        net_income=3e9,
        shares_outstanding=1e9,
        # prior_shares_outstanding = None
    )
    result = SBCAnalysis().calculate(stock)
    assert result.error is None
    assert "annual_dilution_rate" not in result.details
    assert any("prior_shares_outstanding" in w for w in result.analysis if isinstance(w, str))


def test_net_income_none_missing_fields():
    """net_income = None → missing_fields 含 net_income，error 非空。"""
    stock = _Stock(
        current_price=100.0,
        sbc=1e8,
        # net_income = None
    )
    result = SBCAnalysis().calculate(stock)
    assert "net_income" in result.missing_fields
    assert result.error is not None


def test_output_type_score():
    stock = _Stock(
        current_price=100.0,
        sbc=1e7,
        net_income=1e9,
        shares_outstanding=1e8,
    )
    result = SBCAnalysis().calculate(stock)
    assert result.details["output_type"] == "score"
    assert result.fair_value == result.current_price


def test_light_moderate_extreme_ratings():
    """覆盖评级边界：Light(10%)、Moderate(20%)、Extreme(60%)。"""
    for sbc_ratio, expected_rating in [(0.10, "Light"), (0.20, "Moderate"), (0.60, "Extreme")]:
        net_income = 1e9
        stock = _Stock(
            current_price=50.0,
            sbc=net_income * sbc_ratio,
            net_income=net_income,
        )
        result = SBCAnalysis().calculate(stock)
        assert result.details["dilution_rating"] == expected_rating, (
            f"Expected {expected_rating} for ratio {sbc_ratio}, got {result.details['dilution_rating']}"
        )
