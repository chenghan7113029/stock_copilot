"""StockData 模型字段、默认值、缺失语义测试。"""

from common.models.stock_data import StockData


def test_default_values():
    sd = StockData(code="600519", name="贵州茅台")
    assert sd.code == "600519"
    assert sd.name == "贵州茅台"
    assert sd.current_price is None
    assert sd.eps is None
    assert sd.missing_fields == []
    assert sd.field_sources == {}


def test_mark_missing():
    sd = StockData(code="000001", current_price=10.0)
    sd.mark_missing("current_price")
    assert sd.current_price is None
    assert "current_price" in sd.missing_fields


def test_mark_missing_idempotent():
    sd = StockData(code="000001")
    sd.mark_missing("eps")
    sd.mark_missing("eps")
    assert sd.missing_fields.count("eps") == 1


def test_is_missing():
    sd = StockData(code="000001", eps=1.5)
    assert not sd.is_missing("eps")
    assert sd.is_missing("bvps")


def test_set_field_only_when_none():
    """高优先级数据已填写时，低优先级不覆盖。"""
    sd = StockData(code="600519")
    sd.set_field("eps", 55.0, "akshare")
    assert sd.eps == 55.0
    assert sd.field_sources["eps"] == "akshare"
    # 低优先级尝试覆盖，应忽略
    sd.set_field("eps", 54.0, "baostock")
    assert sd.eps == 55.0
    assert sd.field_sources["eps"] == "akshare"


def test_set_field_removes_from_missing():
    sd = StockData(code="600519")
    sd.mark_missing("eps")
    assert "eps" in sd.missing_fields
    sd.set_field("eps", 55.0, "akshare")
    assert "eps" not in sd.missing_fields


def test_none_is_not_zero():
    """None 语义：缺失；0 语义：真实的零值，二者不可混用。"""
    sd = StockData(code="600519")
    assert sd.eps is None
    sd.set_field("eps", 0.0, "akshare")
    assert sd.eps == 0.0
    assert sd.eps is not None
