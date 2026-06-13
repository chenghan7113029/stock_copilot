"""通用工具函数。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_project_root() -> Path:
    """返回项目根目录。"""
    return PROJECT_ROOT
