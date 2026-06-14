"""应用配置加载器。

职责：
- load_app_config()：从 config/app.yaml 加载运行时配置；
  若 app.yaml 不存在，从 app.example.yaml 自动复制并创建 data/ 目录。
- load_validation_stocks()：加载 config/value_data_validation_stocks.yaml，
  返回样本股票列表（E2E 测试 / fetch 脚本的单一真源）。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 以仓库根为基准（本文件位于 src/common/，向上两层）
_REPO_ROOT = Path(__file__).parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_APP_YAML = _CONFIG_DIR / "app.yaml"
_APP_EXAMPLE_YAML = _CONFIG_DIR / "app.example.yaml"
_VALIDATION_STOCKS_YAML = _CONFIG_DIR / "value_data_validation_stocks.yaml"
_DATA_DIR = _REPO_ROOT / "data"


def _ensure_yaml_available():
    """若 app.yaml 不存在，从 example 复制；同时确保 data/ 目录存在。"""
    _DATA_DIR.mkdir(exist_ok=True)
    if not _APP_YAML.exists():
        if not _APP_EXAMPLE_YAML.exists():
            raise FileNotFoundError(
                f"找不到 {_APP_EXAMPLE_YAML}，无法初始化 config/app.yaml"
            )
        shutil.copy(_APP_EXAMPLE_YAML, _APP_YAML)
        logger.info("已从 app.example.yaml 创建 %s", _APP_YAML)


def load_app_config() -> dict[str, Any]:
    """加载并返回 config/app.yaml 的内容（dict）。

    缺少 app.yaml 时，自动从 example 复制（bootstrap）。
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        raise ImportError("缺少 pyyaml，请运行 pip install pyyaml")

    _ensure_yaml_available()
    with _APP_YAML.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    logger.debug("已加载 config/app.yaml")
    return config


def load_validation_stocks() -> list[dict[str, str]]:
    """加载样本股票清单，返回列表，每项包含 code / name / prototype。

    示例返回：
        [{"code": "601398", "name": "工商银行", "prototype": "bank"}, ...]
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        raise ImportError("缺少 pyyaml，请运行 pip install pyyaml")

    if not _VALIDATION_STOCKS_YAML.exists():
        raise FileNotFoundError(f"找不到 {_VALIDATION_STOCKS_YAML}")
    with _VALIDATION_STOCKS_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    stocks: list[dict[str, str]] = data.get("stocks", [])
    logger.debug("加载了 %d 只样本股票", len(stocks))
    return stocks
