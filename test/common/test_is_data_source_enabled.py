"""is_data_source_enabled 单元测试。"""

from common.config_loader import is_data_source_enabled


def test_enabled_when_listed() -> None:
    cfg = {"data_sources": {"enabled": [{"name": "baostock"}, {"name": "AKShare"}]}}
    assert is_data_source_enabled(cfg, "akshare") is True
    assert is_data_source_enabled(cfg, "baostock") is True


def test_disabled_when_commented_out_or_absent() -> None:
    cfg = {"data_sources": {"enabled": [{"name": "baostock"}, {"name": "tushare"}]}}
    assert is_data_source_enabled(cfg, "akshare") is False


def test_empty_config() -> None:
    assert is_data_source_enabled(None, "akshare") is False
    assert is_data_source_enabled({}, "akshare") is False
