"""项目级异常。"""


class StockCopilotError(Exception):
    """stock_copilot 基础异常。"""


class ConfigError(StockCopilotError):
    """配置加载或校验失败。"""


class DataProviderError(StockCopilotError):
    """外部数据 API 调用失败。"""


class UnsupportedMarketError(StockCopilotError):
    """不支持的市场（V1 仅支持 A 股）。"""
