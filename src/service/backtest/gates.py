"""R19 三级门禁状态机（design §4.1，薄状态机，持久化委托台账目录）。

- 每规则**唯一**状态：`backtest_pending → backtest_passed → shadow_running → live_small`
  （`rejected` 为终态）；
- 只允许相邻迁移；跳级/前置条件未满足 → `GateSkipError`（子类 `BacktestError`）并**留痕**；
- 判据数值（Q7/KQ-4）缺键即 `MissingBacktestConfigError`，不默认「通过」。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from common.exceptions import BacktestError, GateSkipError
from service.backtest.models import (
    BacktestConfig,
    GateRecord,
    GateStage,
    RunRecord,
    RunStatus,
)

STAGE_ORDER: tuple[GateStage, ...] = (
    GateStage.BACKTEST_PENDING,
    GateStage.BACKTEST_PASSED,
    GateStage.SHADOW_RUNNING,
    GateStage.LIVE_SMALL,
)
GATE_STORE_NAME = "gates.ndjson"
# GateRecord.evidence_experiment_ids / stage_timestamps 的级名（R19 Scenario3「每级依据」）
GATE_LEVEL_KEYS: dict[GateStage, str] = {
    GateStage.BACKTEST_PASSED: "backtest",
    GateStage.SHADOW_RUNNING: "shadow",
    GateStage.LIVE_SMALL: "live",
}


def _default_clock() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class _Transition:
    rule_id: str
    stage: GateStage
    at: str
    accepted: bool
    experiment_id: str | None
    direction_agree: bool | None
    reason: str | None


class GateStateMachine:
    def __init__(
        self,
        store: Path | Any,
        *,
        cfg: BacktestConfig,
        clock: Callable[[], str] | None = None,
    ) -> None:
        """`store` 可为 gate 台账路径，或 `ExperimentRegistry`（design §4.0：读写委托台账）。

        传入 registry 时，门禁状态落在同一目录的 `gates.ndjson`，且**拒绝动作**额外以
        `RunRecord(status=REJECTED)` 落实验台账留痕（R19「拒绝记录写入台账」）。
        """
        if hasattr(store, "append_run") and hasattr(store, "store_path"):
            self.registry = store
            self.store_path = Path(store.store_path).parent / GATE_STORE_NAME
        else:
            self.registry = None
            self.store_path = Path(store)
        self.cfg = cfg
        self.clock = clock or _default_clock

    # ---- 查询 ----
    def current(self, rule_id: str) -> GateRecord:
        transitions = [item for item in self._read() if item.rule_id == rule_id]
        accepted = [item for item in transitions if item.accepted]
        stage = accepted[-1].stage if accepted else GateStage.BACKTEST_PENDING
        timestamps: dict[str, str] = {}
        evidence: dict[str, str] = {}
        direction_agree: bool | None = None
        for item in accepted:
            key = GATE_LEVEL_KEYS.get(item.stage, item.stage.value)
            timestamps[key] = item.at
            if item.experiment_id:
                evidence[key] = item.experiment_id
            direction_agree = item.direction_agree
        return GateRecord(
            rule_id=rule_id,
            stage=stage,
            stage_timestamps=timestamps,
            evidence_experiment_ids=evidence,
            direction_agree=direction_agree,
        )

    # ---- 迁移 ----
    def transition(
        self, rule_id: str, to: GateStage, evidence: Mapping[str, Any] | None = None
    ) -> GateRecord:
        target = to if isinstance(to, GateStage) else GateStage(str(to))
        current = self.current(rule_id)
        payload = dict(evidence or {})
        experiment_id = payload.get("experiment_id")
        if experiment_id is not None:
            experiment_id = str(experiment_id)
        try:
            self._validate(current, target, payload)
        except GateSkipError as exc:
            at = self.clock()
            self._append(
                _Transition(
                    rule_id=rule_id,
                    stage=target,
                    at=at,
                    accepted=False,
                    experiment_id=experiment_id,
                    direction_agree=payload.get("direction_agree"),
                    reason=str(exc),
                )
            )
            if self.registry is not None:
                self.registry.append_run(
                    RunRecord(
                        run_id=self.registry.next_experiment_id(f"gate-{rule_id}"),
                        status=RunStatus.REJECTED,
                        at=at,
                        hypothesis_id=f"gate:{rule_id}",
                        reason=f"门禁拒绝（{current.stage.value} → {target.value}）：{exc}",
                    )
                )
            raise
        self._append(
            _Transition(
                rule_id=rule_id,
                stage=target,
                at=self.clock(),
                accepted=True,
                experiment_id=experiment_id,
                direction_agree=payload.get("direction_agree"),
                reason=payload.get("reason"),
            )
        )
        return self.current(rule_id)

    def _validate(
        self, current: GateRecord, target: GateStage, evidence: Mapping[str, Any]
    ) -> None:
        if target is GateStage.REJECTED:
            return
        if target not in STAGE_ORDER:
            raise GateSkipError(f"未知门禁阶段: {target!r}（R19）")
        if target is GateStage.BACKTEST_PENDING:
            raise GateSkipError("门禁不可回退到「回测未通过」（R19）")
        if current.stage is GateStage.REJECTED:
            raise GateSkipError(f"规则 {current.rule_id} 门禁已拒绝，不得继续迁移（R19）")
        current_index = STAGE_ORDER.index(current.stage)
        target_index = STAGE_ORDER.index(target)
        if target_index != current_index + 1:
            raise GateSkipError(
                f"跳级请求被拒：{current.stage.value} → {target.value}（R19 只允许逐级）"
            )
        if target is GateStage.BACKTEST_PASSED:
            self.cfg.require("gates.backtest_pass")  # Q7 判据缺键即拒绝
            if not evidence.get("experiment_id"):
                raise GateSkipError("进入「回测通过」需给出依据实验 ID（R19 Scenario 3）")
        elif target is GateStage.SHADOW_RUNNING:
            if not evidence.get("experiment_id"):
                raise GateSkipError("进入影子运行需给出依据实验 ID（R19）")
        elif target is GateStage.LIVE_SMALL:
            min_months = int(self.cfg.require("gates.shadow_min_months"))
            self.cfg.require("gates.direction_agree")  # Q7 判据缺键即拒绝
            if evidence.get("direction_agree") is not True:
                raise GateSkipError("方向一致判据未满足：不得进入实盘小仓位（R19）")
            started = current.stage_timestamps.get(GATE_LEVEL_KEYS[GateStage.SHADOW_RUNNING])
            if not started:
                raise GateSkipError("影子运行起始时间缺失，无法核对最短期限（KQ-4）")
            elapsed = _months_between(started, self.clock())
            if elapsed < min_months:
                raise GateSkipError(
                    f"影子期未满：已 {elapsed} 个月 < 最短 {min_months} 个月（R19 Scenario 2）"
                )

    # ---- 持久化 ----
    def _append(self, transition: _Transition) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rule_id": transition.rule_id,
            "stage": transition.stage.value,
            "at": transition.at,
            "accepted": transition.accepted,
            "experiment_id": transition.experiment_id,
            "direction_agree": transition.direction_agree,
            "reason": transition.reason,
        }
        with self.store_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def _read(self) -> list[_Transition]:
        if not self.store_path.exists():
            return []
        items: list[_Transition] = []
        with self.store_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                items.append(
                    _Transition(
                        rule_id=str(payload["rule_id"]),
                        stage=GateStage(str(payload["stage"])),
                        at=str(payload["at"]),
                        accepted=bool(payload["accepted"]),
                        experiment_id=payload.get("experiment_id"),
                        direction_agree=payload.get("direction_agree"),
                        reason=payload.get("reason"),
                    )
                )
        return items


def _months_between(start: str, end: str) -> int:
    try:
        start_date = datetime.fromisoformat(str(start))
        end_date = datetime.fromisoformat(str(end))
    except ValueError as exc:
        raise BacktestError(f"时间戳非法: {start!r} / {end!r}") from exc
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return max(0, months)
