"""项目级异常。"""


class StockCopilotError(Exception):
    """stock_copilot 基础异常。"""


class ConfigError(StockCopilotError):
    """配置加载或校验失败。"""


class DataProviderError(StockCopilotError):
    """外部数据 API 调用失败。"""


class UnsupportedMarketError(StockCopilotError):
    """不支持的市场（V1 仅支持 A 股）。"""


class KlineUnavailableError(DataProviderError):
    """K 线数据无法从任何数据源获取。"""


# --- 回测域异常（design §4.1「异常清单」，QA-F5）---
# 放 common 是因为 data_provider/backtest 只允许依赖 common（分层约束），
# 而 service/backtest/models.py 会原样重导出，调用方从任一入口 import 都成立。


class BacktestError(StockCopilotError):
    """回测域异常根。"""


class InvalidAdjustModeError(BacktestError):
    """复权口径非法（如请求前复权 qfq）——区别于「数据缺失」。"""


class BacktestDataGapError(BacktestError):
    """回测所需数据缺口（后复权价/成交额/涨跌停/停牌/退市名单/ann_date）。"""


class MissingBacktestConfigError(BacktestError):
    """回测配置缺键（费率/税率/档位/阈值/块长等），不得按 0 或默认值继续。"""


class FutureDataError(BacktestError):
    """访问 as_of 之后的数据（未来函数）。"""


class RegistryCorruptedError(BacktestError):
    """实验台账逐行哈希校验失败（被篡改）。"""


class RegistryImmutableError(BacktestError):
    """修改已写入行 / 样本外二次请求 / 改假设未新开实验。"""


class CalibrationFailedError(BacktestError):
    """R18 校准未通过（库层 raise；CLI 捕获后退出码 2）。"""


class GateSkipError(BacktestError):
    """三级门禁跳级请求被拒。"""
