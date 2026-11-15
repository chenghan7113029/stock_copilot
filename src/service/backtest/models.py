"""回测域契约：枚举 / dataclass / 异常（design §4.1，T2.1）。

约定（design §4.1 开头 + 否-2）：
- 数值字段一律无「业务默认值」；来自 `config/app.yaml backtest:` 段，缺键即
  `MissingBacktestConfigError`。
- 只有两类默认值是允许的：① design 明文写死的落盘路径默认值（`results_dir` /
  `registry_store_path`）；② spec 已固定、不属于「待确认口径」的常量（事件窗口
  20/60、三段年份、MA60/MA20、R14 的 30 只/3 年）。
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

# spec R17 固定的 MVP 事件窗口（Q8 的自定义窗口未答复前拒绝自定义）
EVENT_WINDOWS: tuple[int, int] = (20, 60)
# R8/R10 已固定的标的级不变量（不得配置化，见 _design §4.1「canon 不可调」）
LOT_SIZE = 100  # A 股 100 股一手
# design 明文的落盘默认值（可注入，QA-F10）
DEFAULT_RESULTS_DIR = "data/backtest/results"
DEFAULT_REGISTRY_STORE = "data/backtest/registry.ndjson"
DEFAULT_PREREG_DIR = "config/backtest/preregistrations"

# T2.2 判定真伪：缺这三类口径必须拒绝（缺键即拒绝，不预埋默认值）
PIPELINE_REQUIRED_KEYS: tuple[str, ...] = (
    "commission.rate",
    "commission.min",
    "stamp_tax.sell_rate",
    "slippage_tiers",
)


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
    """信号条件定义（design §4.1 `evaluate_condition` 的入参类型）。"""

    condition_id: str
    kind: str  # 本波只实现 "ma_breakdown"（MVP 事件研究）
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventSignal:
    condition_id: str
    event_date: str


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
    hypothesis_id: str | None = None  # 导出 join 键（R1-03：hypothesis_id + experiment_id）
    reason: str | None = None
    prereg_commit: str | None = None
    data_version: str | None = None  # R1-04：与结果行同名同源（来自 registry 注入）
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
class EventObservation:
    """单个事件 × 单个窗口 × 单个基准的超额观测（compute_event_study 的输入行）。"""

    code: str
    event_date: str
    window: int
    benchmark_kind: str
    excess: float
    cap_tier: int | None = None


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
    """`ledger` 导出一行（QA-F10 13 字段）。

    `verdict` 在「只有执行行（REJECTED/FAILED）」时为 None（R1-03 join 规则）：
    verdict 是结论，拒绝/失败没有结论。
    """

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


@dataclass(frozen=True)
class BacktestConfig:
    """回测运行配置（QA-F10：落盘路径可注入；口径参数缺键即拒绝）。"""

    results_dir: Path
    registry_store_path: Path
    prereg_dir: Path
    params: Mapping[str, Any]
    source_path: Path | None = None

    # ---- 读值入口（缺键/空值/None 一律拒绝）----
    def require(self, dotted: str, *, allow_empty: bool = False) -> Any:
        value: Any = self.params
        for part in dotted.split("."):
            if not isinstance(value, Mapping) or part not in value:
                raise MissingBacktestConfigError(f"回测配置缺键: {dotted}")
            value = value[part]
        if value is None:
            raise MissingBacktestConfigError(f"回测配置缺键（未答复）: {dotted}")
        if not allow_empty and isinstance(value, (list, tuple, dict)) and len(value) == 0:
            raise MissingBacktestConfigError(f"回测配置缺键（空值）: {dotted}")
        return value

    def get(self, dotted: str, default: Any = None) -> Any:
        value: Any = self.params
        for part in dotted.split("."):
            if not isinstance(value, Mapping) or part not in value:
                return default
            value = value[part]
        return value

    def missing(self, keys: tuple[str, ...]) -> list[str]:
        missing: list[str] = []
        for key in keys:
            try:
                self.require(key)
            except MissingBacktestConfigError:
                missing.append(key)
        return missing

    def require_keys(self, keys: tuple[str, ...]) -> None:
        missing = self.missing(keys)
        if missing:
            raise MissingBacktestConfigError("回测配置缺键: " + ", ".join(missing))

    @property
    def segments(self) -> dict["Segment", tuple[str, str]]:
        """三段样本边界（design §4.2 R3：`BacktestConfig.segments`）。

        Q3（右边界/滚动）未答复 → 三个段必须**显式配置**起止，缺键即拒绝；
        段之间不得重叠（跨段请求因此可被识别，R3 Scenario2）。
        """
        raw = self.require("segments")
        if not isinstance(raw, Mapping):
            raise MissingBacktestConfigError("回测配置 segments 必须是映射")
        result: dict["Segment", tuple[str, str]] = {}
        for segment in (Segment.TRAIN, Segment.VALIDATION, Segment.OUT_OF_SAMPLE):
            item = raw.get(segment.value)
            if not isinstance(item, Mapping):
                raise MissingBacktestConfigError(f"回测配置缺键: segments.{segment.value}")
            start = item.get("start")
            end = item.get("end")
            if not start or not end:
                raise MissingBacktestConfigError(
                    f"回测配置缺键: segments.{segment.value}.start/end（Q3 未答复）"
                )
            if str(start) >= str(end):
                raise MissingBacktestConfigError(
                    f"segments.{segment.value} 起止非法: {start} >= {end}"
                )
            result[segment] = (str(start), str(end))
        ordered = [result[Segment.TRAIN], result[Segment.VALIDATION], result[Segment.OUT_OF_SAMPLE]]
        for earlier, later in zip(ordered, ordered[1:]):
            if not earlier[1] < later[0]:
                raise MissingBacktestConfigError(
                    "segments 三段必须互不重叠且按时间递增（R3 Scenario2）"
                )
        return result

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any] | None,
        *,
        base_dir: Path | None = None,
        require_pipeline: bool = True,
    ) -> "BacktestConfig":
        """从 `backtest:` 段（或整个 app 配置）构造；相对路径按 `base_dir`（默认 cwd）。"""
        base = Path(base_dir) if base_dir is not None else Path.cwd()
        section: Mapping[str, Any] = dict(config or {})
        if isinstance(section.get("backtest"), Mapping):
            section = dict(section["backtest"])  # type: ignore[index]
        cfg = cls(
            results_dir=_resolve_path(section.get("results_dir"), base, DEFAULT_RESULTS_DIR),
            registry_store_path=_resolve_path(
                section.get("registry_store_path"), base, DEFAULT_REGISTRY_STORE
            ),
            prereg_dir=_resolve_path(section.get("prereg_dir"), base, DEFAULT_PREREG_DIR),
            params=section,
        )
        if require_pipeline:
            cfg.require_keys(PIPELINE_REQUIRED_KEYS)
        return cfg


def _resolve_path(value: Any, base: Path, default: str) -> Path:
    path = Path(str(value)) if value not in (None, "") else Path(default)
    return path if path.is_absolute() else base / path
