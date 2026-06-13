"""pytest 公共 fixtures。"""

import sys
from pathlib import Path

# 确保 src 在 PYTHONPATH 中
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
