"""技术面分析 Facade。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from common.exceptions import KlineUnavailableError, UnsupportedMarketError
from dao.engine import Base, create_db_engine, make_session_factory
from dao.kline_repo import KlineRepo
from dao.models import Kline  # noqa: F401 — register ORM model
from data_provider.base import is_a_share, normalize_stock_code
from data_provider.kline_provider import KlineProvider
from service.tech.calculator import IndicatorCalculator
from service.tech.config import TechAnalysisConfig
from service.tech.models.tech_result import BuySignal, TechAnalysisResult
from service.tech.scorer import BullTrendScorer, ScoringEngine


class TechAnalyzer:
    """技术面分析单一入口。"""

    def __init__(
        self,
        kline_provider: KlineProvider,
        config: TechAnalysisConfig | None = None,
        calculator: IndicatorCalculator | None = None,
        scorer: ScoringEngine | None = None,
    ) -> None:
        self._kline_provider = kline_provider
        self._config = config or TechAnalysisConfig()
        self._calculator = calculator or IndicatorCalculator()
        self._scorer = scorer or BullTrendScorer()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "TechAnalyzer":
        engine = create_db_engine(config)
        Base.metadata.create_all(engine)
        session_factory = make_session_factory(engine)
        session = session_factory()
        repo = KlineRepo(session)
        provider = KlineProvider(repo)
        tech_cfg = TechAnalysisConfig(
            kline_days=config.get("tech", {}).get("kline_days", 90),
        )
        return cls(kline_provider=provider, config=tech_cfg)

    def analyze(self, raw_code: str) -> TechAnalysisResult:
        if not is_a_share(raw_code.strip()):
            raise UnsupportedMarketError(
                f"V1 仅支持 A 股（6 位纯数字），不支持: {raw_code!r}"
            )

        code, _ = normalize_stock_code(raw_code)
        result = TechAnalysisResult(code=code)

        try:
            df, kline_warnings = self._kline_provider.get_kline(
                code, days=self._config.kline_days
            )
            result.warnings.extend(kline_warnings)
        except KlineUnavailableError as exc:
            result.buy_signal = BuySignal.WAIT
            result.risk_factors.append(f"K 线数据获取失败: {exc}")
            result.warnings.append(str(exc))
            return result

        if df is None or df.empty or len(df) < 20:
            result.buy_signal = BuySignal.WAIT
            result.risk_factors.append("数据不足，无法完成分析")
            return result

        indicators = self._calculator.calculate(
            df, code, self._config.indicator_params
        )
        signal = self._scorer.score(indicators, self._config.scoring_params)

        result.current_price = indicators.current_price
        result.trend_status = indicators.trend_status
        result.ma_alignment = indicators.ma_alignment
        result.trend_strength = indicators.trend_strength
        result.ma5 = indicators.ma5
        result.ma10 = indicators.ma10
        result.ma20 = indicators.ma20
        result.ma60 = indicators.ma60
        result.bias_ma5 = indicators.bias_ma5
        result.bias_ma10 = indicators.bias_ma10
        result.bias_ma20 = indicators.bias_ma20
        result.volume_status = indicators.volume_status
        result.volume_ratio_5d = indicators.volume_ratio_5d
        result.volume_trend = indicators.volume_trend
        result.support_ma5 = indicators.support_ma5
        result.support_ma10 = indicators.support_ma10
        result.support_levels = indicators.support_levels
        result.resistance_levels = indicators.resistance_levels
        result.macd_dif = indicators.macd_dif
        result.macd_dea = indicators.macd_dea
        result.macd_bar = indicators.macd_bar
        result.macd_status = indicators.macd_status
        result.macd_signal = indicators.macd_signal
        result.rsi_6 = indicators.rsi_6
        result.rsi_12 = indicators.rsi_12
        result.rsi_24 = indicators.rsi_24
        result.rsi_status = indicators.rsi_status
        result.rsi_signal = indicators.rsi_signal
        result.kdj_k = indicators.kdj_k
        result.kdj_d = indicators.kdj_d
        result.kdj_j = indicators.kdj_j
        result.kdj_status = indicators.kdj_status
        result.kdj_signal = indicators.kdj_signal
        result.buy_signal = signal.buy_signal
        result.signal_score = signal.signal_score
        result.signal_reasons = signal.signal_reasons
        result.risk_factors = signal.risk_factors
        result.warnings.extend(indicators.warnings)
        result.data_timestamp = datetime.now(timezone.utc)

        return result
