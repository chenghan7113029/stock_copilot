"""数据源抽象基类与通用工具。"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional, TypeVar

from common.exceptions import DataProviderError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


# ── A 股代码识别 ──────────────────────────────────────────────────────────────

_A_SHARE_PATTERN = re.compile(r"^\d{6}$")


def is_a_share(code: str) -> bool:
    """判断是否为 6 位纯数字 A 股代码。"""
    return bool(_A_SHARE_PATTERN.match(code.strip()))


def normalize_stock_code(raw: str) -> tuple[str, str]:
    """将原始代码标准化为 (6 位代码, 交易所) 元组。

    规则：
    - 0xxxxx → SZ（深交所）
    - 3xxxxx → SZ
    - 6xxxxx → SH（上交所）
    - 8xxxxx / 4xxxxx → BJ（北交所/新三板）
    """
    code = raw.strip().upper()
    # 去除前缀（如 SH.600519 / 600519.SH / sh600519）
    code = re.sub(r"^(SH|SZ|BJ)[._]?", "", code)
    code = re.sub(r"[._]?(SH|SZ|BJ)$", "", code)

    digits = re.sub(r"\D", "", code)
    if len(digits) != 6:
        raise DataProviderError(f"无法标准化股票代码：{raw!r}")

    if digits[0] in ("6",):
        exchange = "SH"
    elif digits[0] in ("0", "3"):
        exchange = "SZ"
    elif digits[0] in ("8", "4"):
        exchange = "BJ"
    else:
        raise DataProviderError(f"无法识别交易所：{raw!r}")

    return digits, exchange


# ── FetchResult ───────────────────────────────────────────────────────────────

@dataclass
class FetchResult:
    """单次数据源调用的结果。

    约定：
    - 字段缺失用 None 表示（区别于真实的 0）
    - missing_fields 列出无法获取的字段名
    - 业务代码不应将 None 替换为 0，除非语义明确
    """
    code: str = ""
    source: str = ""
    data: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


# ── BaseFetcher ───────────────────────────────────────────────────────────────

class BaseFetcher(ABC):
    """所有数据源 fetcher 的抽象基类。

    子类必须：
    - 设置类属性 source_name（唯一标识符）
    - 设置类属性 priority（数字越小越优先）
    - 实现 fetch_quote / fetch_fundamentals
    """

    source_name: str = ""
    priority: int = 99

    def fetch_all(self, code: str, exchange: str) -> FetchResult:
        """获取所有可用字段（行情 + 基本面合并）。

        签名与 fetch_quote / fetch_fundamentals 对齐，均接收已标准化的
        (code, exchange)，避免 SourceManager / Provider 层的特殊分支。
        """
        quote = self.fetch_quote(code, exchange)
        if not quote.ok:
            return quote
        fundamentals = self.fetch_fundamentals(code, exchange)
        merged_data = {**fundamentals.data, **quote.data}
        merged_missing = list(
            set(quote.missing_fields + fundamentals.missing_fields) - set(merged_data.keys())
        )
        return FetchResult(
            code=code,
            source=self.source_name,
            data=merged_data,
            missing_fields=merged_missing,
            error=fundamentals.error,
        )

    @abstractmethod
    def fetch_quote(self, code: str, exchange: str) -> FetchResult:
        """获取实时行情（当前价、市值等）。"""

    @abstractmethod
    def fetch_fundamentals(self, code: str, exchange: str) -> FetchResult:
        """获取基本面数据（财报、分红、财务指标等）。"""


# ── 指数退避重试工具 ──────────────────────────────────────────────────────────

def retry_with_backoff(
    func: Callable,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs,
):
    """对 func(*args, **kwargs) 执行最多 max_attempts 次指数退避重试。

    抛出最后一次异常；调用方负责将其包装为 FetchResult.error。
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_attempts:
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning("第 %d 次调用失败，%.1fs 后重试: %s", attempt, delay, exc)
            time.sleep(delay)
