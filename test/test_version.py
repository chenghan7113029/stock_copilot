"""测试 common 模块。"""

from common.constants import __version__


def test_version():
    assert __version__ == "0.1.0"
