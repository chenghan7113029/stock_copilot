"""技术指标计算器（纯 pandas，无 IO）。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from service.tech.config import IndicatorParams
from service.tech.models.tech_result import (
    KDJStatus,
    MACDStatus,
    RSIStatus,
    TrendStatus,
    VolumeStatus,
    WeeklyTrendStatus,
)


@dataclass
class TechIndicators:
    """最新一根 K 线的指标快照 + 历史 DataFrame（供趋势扩散度计算）。"""

    code: str
    df: pd.DataFrame
    current_price: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    bias_ma5: float = 0.0
    bias_ma10: float = 0.0
    bias_ma20: float = 0.0

    trend_status: TrendStatus = TrendStatus.CONSOLIDATION
    ma_alignment: str = ""
    trend_strength: float = 0.0

    volume_status: VolumeStatus = VolumeStatus.NORMAL
    volume_ratio_5d: float = 0.0
    volume_trend: str = ""

    support_ma5: bool = False
    support_ma10: bool = False
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)

    macd_dif: float = 0.0
    macd_dea: float = 0.0
    macd_bar: float = 0.0
    macd_status: MACDStatus = MACDStatus.BULLISH
    macd_signal: str = ""

    rsi_6: float = 0.0
    rsi_12: float = 0.0
    rsi_24: float = 0.0
    rsi_status: RSIStatus = RSIStatus.NEUTRAL
    rsi_signal: str = ""

    kdj_k: float = 0.0
    kdj_d: float = 0.0
    kdj_j: float = 0.0
    kdj_status: KDJStatus = KDJStatus.NEUTRAL
    kdj_signal: str = ""

    warnings: list[str] = field(default_factory=list)


@dataclass
class WeeklyIndicators:
    weekly_trend_status: WeeklyTrendStatus = WeeklyTrendStatus.NEUTRAL
    weekly_ma5: float = 0.0
    weekly_ma10: float = 0.0
    weekly_ma20: float = 0.0
    weekly_macd_dif: float = 0.0
    weekly_macd_dea: float = 0.0
    weekly_macd_bar: float = 0.0
    weekly_rsi_6: float = 0.0
    weekly_ma_alignment: str = ""
    weekly_macd_signal: str = ""
    warnings: list[str] = field(default_factory=list)


class WeeklyKlineAggregator:
    """日线 OHLCV 聚合为自然周 K 线。"""

    _MIN_DAILY_ROWS = 25

    @classmethod
    def aggregate(cls, df_daily: pd.DataFrame) -> pd.DataFrame:
        if df_daily is None or df_daily.empty or len(df_daily) < cls._MIN_DAILY_ROWS:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        work = df_daily.sort_values("date").copy()
        work["date"] = pd.to_datetime(work["date"])
        work = work.set_index("date")

        weekly = (
            work.resample("W-MON", label="left", closed="left")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna(subset=["close"])
        )

        weekly = weekly.reset_index()
        weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")
        return weekly


class IndicatorCalculator:
    """基于 OHLCV DataFrame 计算技术指标。"""

    def calculate(
        self,
        df: pd.DataFrame,
        code: str,
        params: IndicatorParams | None = None,
    ) -> TechIndicators:
        params = params or IndicatorParams()
        result = TechIndicators(code=code, df=df.copy())

        if df is None or df.empty or len(df) < 20:
            result.warnings.append("数据不足，无法完成分析")
            return result

        work = df.sort_values("date").reset_index(drop=True).copy()
        work = self._calculate_mas(work, params)
        work = self._calculate_macd(work, params)
        work = self._calculate_rsi(work, params)
        work = self._calculate_kdj(work, params)

        latest = work.iloc[-1]
        result.df = work
        result.current_price = float(latest["close"])
        result.ma5 = float(latest["MA5"])
        result.ma10 = float(latest["MA10"])
        result.ma20 = float(latest["MA20"])
        result.ma60 = float(latest.get("MA60", latest["MA20"]))

        if len(work) < 60:
            result.warnings.append("MA60 数据不足，以 MA20 替代")

        self._calculate_bias(result)
        self._analyze_trend(work, result)
        self._analyze_volume(work, result, params)
        self._analyze_support_resistance(work, result, params)
        self._analyze_macd(work, result, params)
        self._analyze_rsi(work, result, params)
        self._analyze_kdj(work, result, params)

        return result

    def _calculate_mas(self, df: pd.DataFrame, params: IndicatorParams) -> pd.DataFrame:
        df["MA5"] = df["close"].rolling(window=5).mean()
        df["MA10"] = df["close"].rolling(window=10).mean()
        df["MA20"] = df["close"].rolling(window=20).mean()
        if len(df) >= 60:
            df["MA60"] = df["close"].rolling(window=60).mean()
        else:
            df["MA60"] = df["MA20"]
        return df

    def _calculate_macd(self, df: pd.DataFrame, params: IndicatorParams) -> pd.DataFrame:
        ema_fast = df["close"].ewm(span=params.macd_fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=params.macd_slow, adjust=False).mean()
        df["MACD_DIF"] = ema_fast - ema_slow
        df["MACD_DEA"] = df["MACD_DIF"].ewm(span=params.macd_signal, adjust=False).mean()
        df["MACD_BAR"] = (df["MACD_DIF"] - df["MACD_DEA"]) * 2
        return df

    def _calculate_rsi(self, df: pd.DataFrame, params: IndicatorParams) -> pd.DataFrame:
        for period, col in (
            (params.rsi_short, "RSI_6"),
            (params.rsi_mid, "RSI_12"),
            (params.rsi_long, "RSI_24"),
        ):
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
            rs = avg_gain / avg_loss
            df[col] = (100 - (100 / (1 + rs))).fillna(50)
        return df

    def _calculate_kdj(self, df: pd.DataFrame, params: IndicatorParams) -> pd.DataFrame:
        period = params.kdj_period
        low_min = df["low"].rolling(window=period).min()
        high_max = df["high"].rolling(window=period).max()
        spread = high_max - low_min
        rsv = ((df["close"] - low_min) / spread.replace(0, pd.NA)) * 100
        rsv = rsv.fillna(50)

        k_values: list[float] = []
        d_values: list[float] = []
        k_prev, d_prev = 50.0, 50.0
        k_weight = 1 / params.kdj_smooth_k
        d_weight = 1 / params.kdj_smooth_d

        for rsv_val in rsv:
            k_curr = k_prev * (1 - k_weight) + float(rsv_val) * k_weight
            d_curr = d_prev * (1 - d_weight) + k_curr * d_weight
            k_values.append(k_curr)
            d_values.append(d_curr)
            k_prev, d_prev = k_curr, d_curr

        df["KDJ_K"] = k_values
        df["KDJ_D"] = d_values
        df["KDJ_J"] = 3 * df["KDJ_K"] - 2 * df["KDJ_D"]
        return df

    @staticmethod
    def _calculate_bias(result: TechIndicators) -> None:
        price = result.current_price
        if result.ma5 > 0:
            result.bias_ma5 = (price - result.ma5) / result.ma5 * 100
        if result.ma10 > 0:
            result.bias_ma10 = (price - result.ma10) / result.ma10 * 100
        if result.ma20 > 0:
            result.bias_ma20 = (price - result.ma20) / result.ma20 * 100

    @staticmethod
    def _analyze_trend(df: pd.DataFrame, result: TechIndicators) -> None:
        ma5, ma10, ma20 = result.ma5, result.ma10, result.ma20

        if ma5 > ma10 > ma20:
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (
                (prev["MA5"] - prev["MA20"]) / prev["MA20"] * 100 if prev["MA20"] > 0 else 0
            )
            curr_spread = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
            if curr_spread > prev_spread and curr_spread > 5:
                result.trend_status = TrendStatus.STRONG_BULL
                result.ma_alignment = "强势多头排列，均线发散上行"
                result.trend_strength = 90
            else:
                result.trend_status = TrendStatus.BULL
                result.ma_alignment = "多头排列 MA5>MA10>MA20"
                result.trend_strength = 75
        elif ma5 > ma10 and ma10 <= ma20:
            result.trend_status = TrendStatus.WEAK_BULL
            result.ma_alignment = "弱势多头，MA5>MA10 但 MA10≤MA20"
            result.trend_strength = 55
        elif ma5 < ma10 < ma20:
            prev = df.iloc[-5] if len(df) >= 5 else df.iloc[-1]
            prev_spread = (
                (prev["MA20"] - prev["MA5"]) / prev["MA5"] * 100 if prev["MA5"] > 0 else 0
            )
            curr_spread = (ma20 - ma5) / ma5 * 100 if ma5 > 0 else 0
            if curr_spread > prev_spread and curr_spread > 5:
                result.trend_status = TrendStatus.STRONG_BEAR
                result.ma_alignment = "强势空头排列，均线发散下行"
                result.trend_strength = 10
            else:
                result.trend_status = TrendStatus.BEAR
                result.ma_alignment = "空头排列 MA5<MA10<MA20"
                result.trend_strength = 25
        elif ma5 < ma10 and ma10 >= ma20:
            result.trend_status = TrendStatus.WEAK_BEAR
            result.ma_alignment = "弱势空头，MA5<MA10 但 MA10≥MA20"
            result.trend_strength = 40
        else:
            result.trend_status = TrendStatus.CONSOLIDATION
            result.ma_alignment = "均线缠绕，趋势不明"
            result.trend_strength = 50

    @staticmethod
    def _analyze_volume(
        df: pd.DataFrame, result: TechIndicators, params: IndicatorParams
    ) -> None:
        if len(df) < 5:
            return
        latest = df.iloc[-1]
        vol_5d_avg = df["volume"].iloc[-6:-1].mean()
        if vol_5d_avg > 0:
            result.volume_ratio_5d = float(latest["volume"]) / vol_5d_avg

        prev_close = df.iloc[-2]["close"]
        price_change = (latest["close"] - prev_close) / prev_close * 100

        if result.volume_ratio_5d >= params.volume_heavy_ratio:
            if price_change > 0:
                result.volume_status = VolumeStatus.HEAVY_VOLUME_UP
                result.volume_trend = "放量上涨，多头力量强劲"
            else:
                result.volume_status = VolumeStatus.HEAVY_VOLUME_DOWN
                result.volume_trend = "放量下跌，注意风险"
        elif result.volume_ratio_5d <= params.volume_shrink_ratio:
            if price_change > 0:
                result.volume_status = VolumeStatus.SHRINK_VOLUME_UP
                result.volume_trend = "缩量上涨，上攻动能不足"
            else:
                result.volume_status = VolumeStatus.SHRINK_VOLUME_DOWN
                result.volume_trend = "缩量回调，洗盘特征明显（好）"
        else:
            result.volume_status = VolumeStatus.NORMAL
            result.volume_trend = "量能正常"

    @staticmethod
    def _analyze_support_resistance(
        df: pd.DataFrame, result: TechIndicators, params: IndicatorParams
    ) -> None:
        price = result.current_price
        tol = params.ma_support_tolerance

        if result.ma5 > 0:
            ma5_distance = abs(price - result.ma5) / result.ma5
            if ma5_distance <= tol and price >= result.ma5:
                result.support_ma5 = True
                result.support_levels.append(result.ma5)

        if result.ma10 > 0:
            ma10_distance = abs(price - result.ma10) / result.ma10
            if ma10_distance <= tol and price >= result.ma10:
                result.support_ma10 = True
                if result.ma10 not in result.support_levels:
                    result.support_levels.append(result.ma10)

        if result.ma20 > 0 and price >= result.ma20:
            if result.ma20 not in result.support_levels:
                result.support_levels.append(result.ma20)

        if len(df) >= 20:
            recent_high = float(df["high"].iloc[-20:].max())
            if recent_high > price:
                result.resistance_levels.append(recent_high)

    def _analyze_macd(
        self, df: pd.DataFrame, result: TechIndicators, params: IndicatorParams
    ) -> None:
        if len(df) < params.macd_slow:
            result.macd_signal = "数据不足"
            return

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        result.macd_dif = float(latest["MACD_DIF"])
        result.macd_dea = float(latest["MACD_DEA"])
        result.macd_bar = float(latest["MACD_BAR"])

        prev_dif_dea = prev["MACD_DIF"] - prev["MACD_DEA"]
        curr_dif_dea = result.macd_dif - result.macd_dea
        is_golden_cross = prev_dif_dea <= 0 and curr_dif_dea > 0
        is_death_cross = prev_dif_dea >= 0 and curr_dif_dea < 0
        is_crossing_up = prev["MACD_DIF"] <= 0 and result.macd_dif > 0
        is_crossing_down = prev["MACD_DIF"] >= 0 and result.macd_dif < 0

        if is_golden_cross and result.macd_dif > 0:
            result.macd_status = MACDStatus.GOLDEN_CROSS_ZERO
            result.macd_signal = "零轴上金叉，强烈买入信号"
        elif is_crossing_up:
            result.macd_status = MACDStatus.CROSSING_UP
            result.macd_signal = "DIF上穿零轴，趋势转强"
        elif is_golden_cross:
            result.macd_status = MACDStatus.GOLDEN_CROSS
            result.macd_signal = "金叉，趋势向上"
        elif is_death_cross:
            result.macd_status = MACDStatus.DEATH_CROSS
            result.macd_signal = "死叉，趋势向下"
        elif is_crossing_down:
            result.macd_status = MACDStatus.CROSSING_DOWN
            result.macd_signal = "DIF下穿零轴，趋势转弱"
        elif result.macd_dif > 0 and result.macd_dea > 0:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = "多头排列，持续上涨"
        elif result.macd_dif < 0 and result.macd_dea < 0:
            result.macd_status = MACDStatus.BEARISH
            result.macd_signal = "空头排列，持续下跌"
        else:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = "MACD 中性区域"

    def _analyze_rsi(
        self, df: pd.DataFrame, result: TechIndicators, params: IndicatorParams
    ) -> None:
        if len(df) < params.rsi_long:
            result.rsi_signal = "数据不足"
            return

        latest = df.iloc[-1]
        result.rsi_6 = float(latest["RSI_6"])
        result.rsi_12 = float(latest["RSI_12"])
        result.rsi_24 = float(latest["RSI_24"])
        rsi_mid = result.rsi_12

        if rsi_mid > params.rsi_overbought:
            result.rsi_status = RSIStatus.OVERBOUGHT
            result.rsi_signal = f"RSI超买({rsi_mid:.1f}>70)，短期回调风险高"
        elif rsi_mid > 60:
            result.rsi_status = RSIStatus.STRONG_BUY
            result.rsi_signal = f"RSI强势({rsi_mid:.1f})，多头力量充足"
        elif rsi_mid >= 40:
            result.rsi_status = RSIStatus.NEUTRAL
            result.rsi_signal = f"RSI中性({rsi_mid:.1f})，震荡整理中"
        elif rsi_mid >= params.rsi_oversold:
            result.rsi_status = RSIStatus.WEAK
            result.rsi_signal = f"RSI弱势({rsi_mid:.1f})，关注反弹"
        else:
            result.rsi_status = RSIStatus.OVERSOLD
            result.rsi_signal = f"RSI超卖({rsi_mid:.1f}<30)，反弹机会大"

    def _analyze_kdj(
        self, df: pd.DataFrame, result: TechIndicators, params: IndicatorParams
    ) -> None:
        if len(df) < params.kdj_period + 1:
            result.kdj_signal = "数据不足"
            return

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        result.kdj_k = float(latest["KDJ_K"])
        result.kdj_d = float(latest["KDJ_D"])
        result.kdj_j = float(latest["KDJ_J"])

        prev_k, prev_d = float(prev["KDJ_K"]), float(prev["KDJ_D"])
        is_golden = prev_k <= prev_d and result.kdj_k > result.kdj_d
        is_death = prev_k >= prev_d and result.kdj_k < result.kdj_d

        if result.kdj_k > params.kdj_overbought and result.kdj_d > params.kdj_overbought:
            result.kdj_status = KDJStatus.OVERBOUGHT
            result.kdj_signal = f"KDJ超买(K={result.kdj_k:.1f}, D={result.kdj_d:.1f})"
        elif result.kdj_k < params.kdj_oversold and result.kdj_d < params.kdj_oversold:
            result.kdj_status = KDJStatus.OVERSOLD
            result.kdj_signal = f"KDJ超卖(K={result.kdj_k:.1f}, D={result.kdj_d:.1f})"
        elif is_golden:
            result.kdj_status = KDJStatus.GOLDEN_CROSS
            result.kdj_signal = "KDJ金叉"
        elif is_death:
            result.kdj_status = KDJStatus.DEATH_CROSS
            result.kdj_signal = "KDJ死叉"
        else:
            result.kdj_status = KDJStatus.NEUTRAL
            result.kdj_signal = "KDJ中性"

        if result.kdj_j > 100:
            result.kdj_status = KDJStatus.OVERBOUGHT
            result.kdj_signal += f"；J值超界({result.kdj_j:.1f}>100)"
        elif result.kdj_j < 0:
            result.kdj_status = KDJStatus.OVERSOLD
            result.kdj_signal += f"；J值超界({result.kdj_j:.1f}<0)"

    def calculate_weekly(
        self,
        df_daily: pd.DataFrame,
        params: IndicatorParams | None = None,
    ) -> WeeklyIndicators:
        params = params or IndicatorParams()
        result = WeeklyIndicators()

        if df_daily is None or df_daily.empty or len(df_daily) < WeeklyKlineAggregator._MIN_DAILY_ROWS:
            result.warnings.append("周线数据不足，周线趋势分析未启用")
            return result

        weekly_df = WeeklyKlineAggregator.aggregate(df_daily)
        if weekly_df.empty:
            result.warnings.append("周线数据不足，周线趋势分析未启用")
            return result

        work = weekly_df.copy()
        work["MA5"] = work["close"].rolling(window=5).mean()
        work["MA10"] = work["close"].rolling(window=10).mean()
        if len(work) >= 20:
            work["MA20"] = work["close"].rolling(window=20).mean()
        else:
            window = max(len(work), 1)
            work["MA20"] = work["close"].rolling(window=window).mean()
            result.warnings.append("周线 MA20 数据不足，以可用窗口替代")

        ema_fast = work["close"].ewm(span=params.weekly_macd_fast, adjust=False).mean()
        ema_slow = work["close"].ewm(span=params.weekly_macd_slow, adjust=False).mean()
        work["MACD_DIF"] = ema_fast - ema_slow
        work["MACD_DEA"] = work["MACD_DIF"].ewm(
            span=params.weekly_macd_signal, adjust=False
        ).mean()
        work["MACD_BAR"] = (work["MACD_DIF"] - work["MACD_DEA"]) * 2

        period = 6
        delta = work["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
        rs = avg_gain / avg_loss
        work["RSI_6"] = (100 - (100 / (1 + rs))).fillna(50)

        latest = work.iloc[-1]
        result.weekly_ma5 = float(latest["MA5"])
        result.weekly_ma10 = float(latest["MA10"])
        result.weekly_ma20 = float(latest["MA20"])
        result.weekly_macd_dif = float(latest["MACD_DIF"])
        result.weekly_macd_dea = float(latest["MACD_DEA"])
        result.weekly_macd_bar = float(latest["MACD_BAR"])
        result.weekly_rsi_6 = float(latest["RSI_6"])

        self._analyze_weekly_trend(work, result)
        self._analyze_weekly_macd(work, result, params)

        return result

    @staticmethod
    def _analyze_weekly_trend(df: pd.DataFrame, result: WeeklyIndicators) -> None:
        ma5, ma10, ma20 = result.weekly_ma5, result.weekly_ma10, result.weekly_ma20

        if ma5 > ma10 > ma20:
            prev = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
            prev_spread = (
                (prev["MA5"] - prev["MA20"]) / prev["MA20"] * 100 if prev["MA20"] > 0 else 0
            )
            curr_spread = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
            if curr_spread > prev_spread and curr_spread > 5:
                result.weekly_trend_status = WeeklyTrendStatus.STRONG_BULL
                result.weekly_ma_alignment = "周线强势多头排列，均线发散上行"
            else:
                result.weekly_trend_status = WeeklyTrendStatus.BULL
                result.weekly_ma_alignment = "周线多头排列 MA5W>MA10W>MA20W"
        elif ma5 < ma10 < ma20:
            prev = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
            prev_spread = (
                (prev["MA20"] - prev["MA5"]) / prev["MA5"] * 100 if prev["MA5"] > 0 else 0
            )
            curr_spread = (ma20 - ma5) / ma5 * 100 if ma5 > 0 else 0
            if curr_spread > prev_spread and curr_spread > 5:
                result.weekly_trend_status = WeeklyTrendStatus.STRONG_BEAR
                result.weekly_ma_alignment = "周线强势空头排列，均线发散下行"
            else:
                result.weekly_trend_status = WeeklyTrendStatus.BEAR
                result.weekly_ma_alignment = "周线空头排列 MA5W<MA10W<MA20W"
        else:
            result.weekly_trend_status = WeeklyTrendStatus.NEUTRAL
            result.weekly_ma_alignment = "周线均线缠绕，趋势不明"

    def _analyze_weekly_macd(
        self, df: pd.DataFrame, result: WeeklyIndicators, params: IndicatorParams
    ) -> None:
        if len(df) < params.weekly_macd_slow:
            result.weekly_macd_signal = "数据不足"
            return

        prev = df.iloc[-2]
        prev_dif_dea = prev["MACD_DIF"] - prev["MACD_DEA"]
        curr_dif_dea = result.weekly_macd_dif - result.weekly_macd_dea
        is_golden_cross = prev_dif_dea <= 0 and curr_dif_dea > 0
        is_death_cross = prev_dif_dea >= 0 and curr_dif_dea < 0

        if is_golden_cross and result.weekly_macd_dif > 0:
            result.weekly_macd_signal = "周线零轴上金叉"
        elif is_golden_cross:
            result.weekly_macd_signal = "周线金叉"
        elif is_death_cross:
            result.weekly_macd_signal = "周线死叉"
        elif result.weekly_macd_dif > 0 and result.weekly_macd_dea > 0:
            result.weekly_macd_signal = "周线多头"
        elif result.weekly_macd_dif < 0 and result.weekly_macd_dea < 0:
            result.weekly_macd_signal = "周线空头"
        else:
            result.weekly_macd_signal = "周线 MACD 中性"
