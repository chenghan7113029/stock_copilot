"""回测域契约：枚举 / dataclass / 异常（design §4.1 + T2-fix-4 config schema）。

约定（design §4.1 开头 + 否-2）：
- 数值字段一律无「业务默认值」；来自 `config/app.yaml backtest:` 段（契约源 =
  `config/app.example.yaml`），必须键缺失即 `MissingBacktestConfigError`；
- 待 Q 键形状固定、数值留空；消费处发现 None 即拒绝（不按 0 / 不预埋默认）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from common.exceptions import (  # noqa: F401 —— 重导出：service 侧统一从 models 取
    BacktestDataGapError,
    BacktestError,
    CalibrationFailedError,
    FutureDataError,
    GateSkipError,
    InvalidAdjustModeError,
    MissingBacktestConfigError,
    RegistryCorruptedError,
    RegistryImmutableError,
)

# spec R17 固定的 MVP 事件窗口（Q8 未答复前拒绝自定义窗口）
EVENT_WINDOWS: tuple[int, int] = (20, 60)
# spec R3 固定的三段样本年份（Q3 只影响右边界/滚动，不影响三段定义）
SEGMENT_YEAR_RANGES: Mapping["Segment", tuple[int, int]] = {}
# R8/R10 已固定的不变量（不得配置化，见 _design §4.1「canon 不可调」）
LOT_SIZE = 100  # A 股 100 股一手
# design 明文的落盘默认值（可注入，QA-F10）
DEFAULT_RESULTS_DIR = "data/backtest/results"
DEFAULT_REGISTRY_STORE = "data/backtest/registry.ndjson"
DEFAULT_PREREG_DIR = "config/backtest/preregistrations"
# T2-fix-4：必须键（段落键缺失即拒绝；路径键有 design 明文默认值，可省略）
MUST_KEYS: tuple[str, ...] = ("segments", "windows", "max_delay_days", "min_events")


class AdjustMode(str, Enum):
    """复权口径。前复权（qfq）刻意不在枚举内：请求即 `InvalidAdjustModeError`（R9）。"""

    HFQ = "hfq"
    SEGMENTED_HFQ = "segmented_hfq"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    FILLED = "filled"
    FAILED_LIMIT_SEAL = "failed_limit_seal"
    SKIPPED_SUSPENDED = "skipped_suspended"
    REJECTED_T1 = "rejected_t1"
    CAPPED_LIQUIDITY = "capped_liquidity"


class Segment(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    OUT_OF_SAMPLE = "out_of_sample"


class Verdict(str, Enum):
    """结论三值（只出现在结果行）；执行失败/被拒由 `RunStatus` 表达（QA-F2）。"""

    VALID = "valid"
    INVALID = "invalid"
    INCONCLUSIVE = "inconclusive"


class RunStatus(str, Enum):
    """执行行状态：每次执行尝试一行，含拒绝与失败（QA-F2）。"""

    RUNNING = "running"
    PASSED = "passed"
    REJECTED = "rejected"
    FAILED = "failed"


class GateStage(str, Enum):
    BACKTEST_PENDING = "backtest_pending"
    BACKTEST_PASSED = "backtest_passed"
    SHADOW_RUNNING = "shadow_running"
    LIVE_SMALL = "live_small"
    REJECTED = "rejected"


SEGMENT_YEAR_RANGES = {
    Segment.TRAIN: (2015, 2020),
    Segment.VALIDATION: (2021, 2023),
    Segment.OUT_OF_SAMPLE: (2024, 2026),
}


def segment_of(trade_date: str) -> Segment:
    """按 R3 的三段年份判定某日所属区段（跨段由调用方拆开，不合并报告）。"""
    year = int(str(trade_date)[:4])
    for segment, (start, end) in SEGMENT_YEAR_RANGES.items():
        if start <= year <= end:
            return segment
    raise BacktestError(f"{trade_date} 不在三段样本区间内（R3）")


# --------------------------------------------------------------------------
# 数据传输结构
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceBar:
    code: str
    trade_date: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    amount: float | None = None
    limit_up_price: float | None = None
    limit_down_price: float | None = None
    suspended: bool = False
    delisted: bool = False
    st: bool = False


@dataclass(frozen=True)
class FinancialRecord:
    code: str
    report_period: str
    visible_from: str
    ann_date: str | None = None
    end_date: str | None = None
    ann_date_fallback: bool = False
    fields: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class GroupAssignment:
    code: str
    as_of: str
    tiers: Mapping[str, int]
    effective_range: tuple[str, str]


@dataclass(frozen=True)
class PointInTimeSnapshot:
    """signal 的输入：构造时即被硬裁到 `trade_date/visible_from <= as_of`（R10）。"""

    as_of: str
    price: tuple[PriceBar, ...] = ()
    financials: tuple[FinancialRecord, ...] = ()

    def __post_init__(self) -> None:
        as_of = str(self.as_of)
        for bar in self.price:
            if str(bar.trade_date) > as_of:
                raise FutureDataError(
                    f"未来函数：PriceBar.trade_date={bar.trade_date} > as_of={as_of}"
                )
        for record in self.financials:
            if str(record.visible_from) > as_of:
                raise FutureDataError(
                    f"未来函数：FinancialRecord.visible_from={record.visible_from} > as_of={as_of}"
                )


@dataclass(frozen=True)
class ConditionSpec:
    """信号条件定义（design §4.1，T2-fix-4）：`evaluate_condition` 的唯一条件入参。"""

    condition_id: str
    kind: str  # MVP 至少 "ma60_breakdown"
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventSignal:
    condition_id: str
    event_date: str


@dataclass(frozen=True)
class EventObservation:
    """事件研究的收益载体（design §4.1，T2-fix-4）。

    `excess_returns` = 事件日后第 1..max(window) 个交易日的**逐日相对基准超额**；
    metrics 只消费本结构，不直接读价格。
    """

    code: str
    event_date: str
    condition_id: str
    benchmark_kind: str
    excess_returns: tuple[float, ...]


@dataclass(frozen=True)
class Order:
    code: str
    signal_date: str
    side: OrderSide
    requested_amount: float
    requested_qty: int | None = None


@dataclass(frozen=True)
class CostBreakdown:
    commission: float = 0.0
    stamp_tax: float = 0.0
    slippage: float = 0.0
    transfer_fee: float = 0.0
    total: float = 0.0

    @property
    def is_zero(self) -> bool:
        return self.total == 0.0


ZERO_COST = CostBreakdown()


@dataclass(frozen=True)
class OrderAttempt:
    attempt_date: str
    status: OrderStatus
    reason: str | None = None


@dataclass(frozen=True)
class Fill:
    order: Order
    attempts: tuple[OrderAttempt, ...]
    cost: CostBreakdown
    fill_date: str | None = None
    fill_price: float | None = None
    filled_amount: float | None = None
    delay_days: int = 0
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreregistrationSpec:
    hypothesis_id: str
    statement: str
    params: Mapping[str, Any]
    metrics: tuple[str, ...]
    segments: tuple[Segment, ...]
    benchmarks: tuple[str, ...]
    correction_method: str
    k_definition: str
    created_at: str

    REQUIRED_FIELDS = (
        "hypothesis_id",
        "statement",
        "params",
        "metrics",
        "segments",
        "benchmarks",
        "correction_method",
        "k_definition",
        "created_at",
    )


@dataclass(frozen=True)
class RunRecord:
    """执行行（QA-F2）：拒绝/失败必须落这一行留痕。`row_type` 判别符置末。"""

    run_id: str
    status: RunStatus
    at: str
    experiment_id: str | None = None
    hypothesis_id: str | None = None  # T2-fix-4：拒绝/烧毁发生在结果行之前也可查询
    reason: str | None = None
    prereg_commit: str | None = None
    data_version: str | None = None  # captain R1-04：与结果行同名同源（registry 注入）
    row_type: str = "run"


@dataclass(frozen=True)
class ExperimentRecord:
    """结果行（R2）：仅 PASSED 执行追加；append-only，写后不可改。"""

    experiment_id: str
    hypothesis_id: str
    params: Mapping[str, Any]
    segment: Segment
    K: int | None
    verdict: Verdict
    metrics: Mapping[str, Any]
    prereg_commit: str
    data_version: str
    adjust_mode: AdjustMode
    timestamps: Mapping[str, str]
    parent_experiment_id: str | None = None
    burnt: bool = False
    row_type: str = "result"


@dataclass(frozen=True)
class Benchmark:
    kind: str  # "buy_and_hold" | "market_portfolio"
    label: str


@dataclass(frozen=True)
class WindowStats:
    n: int
    mean: float
    median: float
    std: float
    ci: tuple[float, float]
    effective_n: int
    by_year: Mapping[str, "WindowStats"] = field(default_factory=dict)
    by_cap_tier: Mapping[str, "WindowStats"] = field(default_factory=dict)


@dataclass(frozen=True)
class EventStudyResult:
    windows: Mapping[str, Mapping[str, WindowStats]]
    n_events: int
    inference_method: str
    block_length: int | None = None
    n_bootstrap: int | None = None


@dataclass(frozen=True)
class AttributionResult:
    beta: float
    size: float
    value: float
    momentum: float
    exposures: Mapping[str, float]
    contributions: Mapping[str, float]
    unexplained: float


@dataclass(frozen=True)
class StabilityResult:
    by_year: Mapping[str, WindowStats]
    by_market_state: Mapping[str, WindowStats]
    by_cap_tier: Mapping[str, WindowStats]
    scope_note: str


@dataclass(frozen=True)
class CalibrationResult:
    passed: bool
    direction: str
    params: Mapping[str, Any]
    notes: tuple[str, ...] = ()
    ci: tuple[float, float] | None = None
    K: int | None = None
    corrected_p: float | None = None
    verdict: Verdict = Verdict.INCONCLUSIVE


@dataclass(frozen=True)
class GateRecord:
    rule_id: str
    stage: GateStage
    stage_timestamps: Mapping[str, str] = field(default_factory=dict)
    evidence_experiment_ids: Mapping[str, str] = field(default_factory=dict)
    direction_agree: bool | None = None


@dataclass(frozen=True)
class LedgerExportRow:
    """`ledger` 导出一行（QA-F10 13 字段）；只有执行行时 `verdict` 为 None（R1-03）。"""

    experiment_id: str
    hypothesis_id: str
    statement: str
    params: Mapping[str, Any]
    segments: tuple[str, ...]
    K: int | None
    metrics: Mapping[str, Any]
    verdict: str | None
    burnt: bool
    prereg_commit: str | None
    run_status: str | None
    data_version: str | None
    adjust_mode: str | None


# --------------------------------------------------------------------------
# config schema（T2-fix-4：形状固定，数值留空）
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CommissionSpec:
    rate: float
    min: float


@dataclass(frozen=True)
class StampTaxSpec:
    side: str
    rate: float


@dataclass(frozen=True)
class TransferFeeSpec:
    rate: float
    included: bool


@dataclass(frozen=True)
class SlippageTierSpec:
    amount_lower: float
    amount_upper: float
    bps: float


@dataclass(frozen=True)
class LiquidityCapSpec:
    adv_tier: str
    max_participation: float


@dataclass(frozen=True)
class GateCriteria:
    """三级门禁判据（Q7 待答复）：shape 固定、数值留空，缺即不允许 transition。"""

    backtest_pass: Mapping[str, Any] | None = None
    shadow: Mapping[str, Any] | None = None
    direction_agree: Mapping[str, Any] | None = None
    small_position: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class BacktestConfig:
    """`config/app.yaml` `backtest:` 段的类型化视图（design §4.1，T2-fix-4）。

    必须键缺失 → `MissingBacktestConfigError`；待 Q 键形状固定、数值留空，
    消费处发现 None 即拒绝（不预埋默认）。
    """

    results_dir: Path
    registry_store_path: Path
    segments: tuple[Segment, ...]
    windows: tuple[int, ...]
    max_delay_days: int | None
    min_events: int | None
    commission: CommissionSpec | None = None
    stamp_tax: StampTaxSpec | None = None
    transfer_fee: TransferFeeSpec | None = None
    slippage_tiers: tuple[SlippageTierSpec, ...] | None = None
    liquidity_cap: tuple[LiquidityCapSpec, ...] | None = None
    limit_pct: Mapping[str, Any] | None = None
    seal_definition: str | None = None
    suspend_source: str | None = None
    cut_basis: str | None = None
    tier_count: int | None = None
    recompute_freq: str | None = None
    min_group_size: int | None = None
    gate_criteria: GateCriteria | None = None
    block_length: int | None = None
    n_bootstrap: int | None = None
    shrink: float | None = None
    burn_scope: str | None = None
    burn_counts_as_second: tuple[str, ...] | None = None
    exception_approver: str | None = None
    k_components: tuple[str, ...] | None = None
    custom_allowed: bool | None = None
    k_cost_per_window: int | None = None
    source_path: Path | None = None

    @classmethod
    def from_config(
        cls, config: Mapping[str, Any] | None, *, base_dir: Path | None = None
    ) -> "BacktestConfig":
        """从 `backtest:` 段（或整个 app 配置）构造；相对路径按 `base_dir`（默认 cwd）。"""
        base = Path(base_dir) if base_dir is not None else Path.cwd()
        section: Mapping[str, Any] = dict(config or {})
        if isinstance(section.get("backtest"), Mapping):
            section = dict(section["backtest"])  # type: ignore[index]
        missing = [key for key in MUST_KEYS if key not in section]
        if missing:
            raise MissingBacktestConfigError("回测配置缺键: " + ", ".join(missing))
        segments = _parse_segments(section["segments"])
        custom_allowed = section.get("custom_allowed")
        windows = _parse_windows(section["windows"], custom_allowed=custom_allowed)
        return cls(
            results_dir=_resolve_path(section.get("results_dir"), base, DEFAULT_RESULTS_DIR),
            registry_store_path=_resolve_path(
                section.get("registry_store_path"), base, DEFAULT_REGISTRY_STORE
            ),
            segments=segments,
            windows=windows,
            max_delay_days=_opt_int(section["max_delay_days"], "max_delay_days"),
            min_events=_opt_int(section["min_events"], "min_events"),
            commission=_parse_commission(section.get("commission")),
            stamp_tax=_parse_stamp_tax(section.get("stamp_tax")),
            transfer_fee=_parse_transfer_fee(section.get("transfer_fee")),
            slippage_tiers=_parse_slippage(section.get("slippage_tiers")),
            liquidity_cap=_parse_liquidity(section.get("liquidity_cap")),
            limit_pct=_opt_mapping(section.get("limit_pct")),
            seal_definition=_opt_str(section.get("seal_definition")),
            suspend_source=_opt_str(section.get("suspend_source")),
            cut_basis=_opt_str(section.get("cut_basis")),
            tier_count=_opt_int(section.get("tier_count"), "tier_count"),
            recompute_freq=_opt_str(section.get("recompute_freq")),
            min_group_size=_opt_int(section.get("min_group_size"), "min_group_size"),
            gate_criteria=_parse_gate_criteria(section.get("gates", section.get("gate_criteria"))),
            block_length=_opt_int(section.get("block_length"), "block_length"),
            n_bootstrap=_opt_int(section.get("n_bootstrap"), "n_bootstrap"),
            shrink=_opt_float(section.get("shrink"), "shrink"),
            burn_scope=_opt_str(section.get("burn_scope")),
            burn_counts_as_second=_opt_str_tuple(section.get("burn_counts_as_second")),
            exception_approver=_opt_str(section.get("exception_approver")),
            k_components=_opt_str_tuple(section.get("k_components")),
            custom_allowed=None if custom_allowed is None else bool(custom_allowed),
            k_cost_per_window=_opt_int(section.get("k_cost_per_window"), "k_cost_per_window"),
        )


# --------------------------------------------------------------------------
# config 解析辅助（形状校验；数值缺失 → None，由消费处拒绝）
# --------------------------------------------------------------------------


def _resolve_path(value: Any, base: Path, default: str) -> Path:
    path = Path(str(value)) if value not in (None, "") else Path(default)
    return path if path.is_absolute() else base / path


def _opt_int(value: Any, name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise MissingBacktestConfigError(f"{name} 非法: {value!r}") from exc


def _opt_float(value: Any, name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise MissingBacktestConfigError(f"{name} 非法: {value!r}") from exc


def _opt_str(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _opt_mapping(value: Any) -> Mapping[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _opt_str_tuple(value: Any) -> tuple[str, ...] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, (list, tuple)):
        raise MissingBacktestConfigError(f"应为字符串数组，实际 {value!r}")
    return tuple(str(item) for item in value)


def _parse_segments(value: Any) -> tuple[Segment, ...]:
    if isinstance(value, Mapping):
        names = list(value.keys())
    elif isinstance(value, (list, tuple)):
        names = [str(item) for item in value]
    else:
        raise MissingBacktestConfigError(f"segments 形状非法: {value!r}（须为三段名单）")
    try:
        segments = tuple(Segment(str(name)) for name in names)
    except ValueError as exc:
        raise MissingBacktestConfigError(f"segments 含未知区段: {names}") from exc
    required = {Segment.TRAIN, Segment.VALIDATION, Segment.OUT_OF_SAMPLE}
    if set(segments) != required:
        raise MissingBacktestConfigError(f"segments 必须为三段 {sorted(s.value for s in required)}")
    return segments


def _parse_windows(value: Any, *, custom_allowed: Any) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise MissingBacktestConfigError(f"windows 形状非法: {value!r}（须为非空数组）")
    windows = tuple(int(item) for item in value)
    if any(window < 1 for window in windows):
        raise MissingBacktestConfigError(f"windows 含非法窗口: {windows}")
    if custom_allowed is not True:
        unsupported = [window for window in windows if window not in EVENT_WINDOWS]
        if unsupported:
            raise MissingBacktestConfigError(
                f"自定义窗口未获确认（Q8）: {unsupported}；未答复前只允许 {EVENT_WINDOWS}"
            )
    return windows


def _parse_commission(value: Any) -> CommissionSpec | None:
    if not isinstance(value, Mapping):
        return None
    rate, minimum = value.get("rate"), value.get("min")
    if rate is None or minimum is None:
        return None
    return CommissionSpec(rate=float(rate), min=float(minimum))


def _parse_stamp_tax(value: Any) -> StampTaxSpec | None:
    if not isinstance(value, Mapping):
        return None
    rate = value.get("rate")
    if rate is None:
        return None
    return StampTaxSpec(side=str(value.get("side") or "sell"), rate=float(rate))


def _parse_transfer_fee(value: Any) -> TransferFeeSpec | None:
    if not isinstance(value, Mapping):
        return None
    included = value.get("included")
    if included is None:
        return None
    if not bool(included):
        return TransferFeeSpec(rate=0.0, included=False)
    rate = value.get("rate")
    if rate is None:
        return None
    return TransferFeeSpec(rate=float(rate), included=True)


def _parse_slippage(value: Any) -> tuple[SlippageTierSpec, ...] | None:
    if not isinstance(value, (list, tuple)) or not value:
        return None
    tiers: list[SlippageTierSpec] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise MissingBacktestConfigError(f"slippage_tiers 档位不是映射: {item!r}")
        missing = [key for key in ("amount_lower", "amount_upper", "bps") if item.get(key) is None]
        if missing:
            raise MissingBacktestConfigError(f"slippage_tiers 缺键: {missing}")
        tiers.append(
            SlippageTierSpec(
                amount_lower=float(item["amount_lower"]),
                amount_upper=float(item["amount_upper"]),
                bps=float(item["bps"]),
            )
        )
    return tuple(tiers)


def _parse_liquidity(value: Any) -> tuple[LiquidityCapSpec, ...] | None:
    if not isinstance(value, (list, tuple)) or not value:
        return None
    caps: list[LiquidityCapSpec] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise MissingBacktestConfigError(f"liquidity_cap 档位不是映射: {item!r}")
        if item.get("adv_tier") is None or item.get("max_participation") is None:
            raise MissingBacktestConfigError("liquidity_cap 缺 adv_tier/max_participation")
        caps.append(
            LiquidityCapSpec(
                adv_tier=str(item["adv_tier"]),
                max_participation=float(item["max_participation"]),
            )
        )
    return tuple(caps)


def _parse_gate_criteria(value: Any) -> GateCriteria | None:
    if not isinstance(value, Mapping):
        return None
    return GateCriteria(
        backtest_pass=_opt_mapping(value.get("backtest_pass")),
        shadow=_opt_mapping(value.get("shadow")),
        direction_agree=_opt_mapping(value.get("direction_agree")),
        small_position=_opt_mapping(value.get("small_position")),
    )
