"""根级 conftest：确保 src/ 最先加入 sys.path。"""

import sys
from pathlib import Path

src = str(Path(__file__).parent / "src")
if src not in sys.path:
    sys.path.insert(0, src)
