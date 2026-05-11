import logging
import time
from dataclasses import dataclass
from typing import Optional
from ..models import CellState, GroupingKey, CellStabilityRecord

logger = logging.getLogger(__name__)

# Valid forward transitions
_VALID_TRANSITIONS = {
    CellState.NORMAL: {CellState.WARNING},
    CellState.WARNING: {CellState.NORMAL, CellState.CONGESTION},
    CellState.CONGESTION: {CellState.WARNING, CellState.OVERLOAD},
    CellState.OVERLOAD: {CellState.NORMAL},
}


@dataclass
class TransitionResult:
    success: bool
    grouping_key: GroupingKey
    previous_state: CellState
    new_state: CellState
    ctn_list: list
    timestamp: float


class CellStateMachine:

    def __init__(self):
        self._states: dict = {}
        self._stability_records: dict = {}
        self._ctn_map: dict = {}  # grouping_key -> set of ctns
        self._ul_rb_map: dict = {}  # grouping_key -> latest ul_rb_sum

    def get_state(self, grouping_key: GroupingKey) -> CellState:
        return self._states.get(grouping_key, CellState.NORMAL)

    def ensure_registered(self, grouping_key: GroupingKey) -> None:
        """패킷 수신 시 셀을 _states에 등록해 list_cells에 노출되도록 한다."""
        if grouping_key not in self._states:
            self._states[grouping_key] = CellState.NORMAL

    def expire(self, grouping_key: GroupingKey) -> None:
        """슬라이딩 윈도우에서 해당 셀의 이벤트가 모두 만료됐을 때 목록에서 제거한다."""
        self._states.pop(grouping_key, None)
        self._stability_records.pop(grouping_key, None)
        self._ctn_map.pop(grouping_key, None)
        self._ul_rb_map.pop(grouping_key, None)

    def update_ctns(self, grouping_key: GroupingKey, ctn_set: set) -> None:
        self._ctn_map[grouping_key] = set(ctn_set)

    def update_ul_rb(self, grouping_key: GroupingKey, ul_rb_sum: int) -> None:
        self._ul_rb_map[grouping_key] = ul_rb_sum

    def get_ul_rb(self, grouping_key: GroupingKey) -> int:
        return self._ul_rb_map.get(grouping_key, 0)

    def transition(self, grouping_key: GroupingKey, new_state: CellState, timestamp: float) -> TransitionResult:
        current = self.get_state(grouping_key)

        if current == new_state:
            return TransitionResult(
                success=True,
                grouping_key=grouping_key,
                previous_state=current,
                new_state=new_state,
                ctn_list=[],
                timestamp=timestamp,
            )

        if new_state not in _VALID_TRANSITIONS.get(current, set()):
            logger.warning(
                "Invalid cell transition rejected: %s -> %s for %s",
                current, new_state, grouping_key,
            )
            return TransitionResult(
                success=False,
                grouping_key=grouping_key,
                previous_state=current,
                new_state=new_state,
                ctn_list=[],
                timestamp=timestamp,
            )

        self._states[grouping_key] = new_state
        self._update_stability_record(grouping_key, new_state, timestamp)

        ctn_list = list(self._ctn_map.get(grouping_key, set()))

        logger.info(
            "Cell state transition: %s %s -> %s (ctns: %d)",
            grouping_key, current, new_state, len(ctn_list),
        )

        return TransitionResult(
            success=True,
            grouping_key=grouping_key,
            previous_state=current,
            new_state=new_state,
            ctn_list=ctn_list,
            timestamp=timestamp,
        )

    def _update_stability_record(self, grouping_key: GroupingKey, new_state: CellState, timestamp: float) -> None:
        prev_record = self._stability_records.get(grouping_key)

        if new_state == CellState.NORMAL:
            normal_duration = 0.0
            if prev_record and prev_record.current_state == CellState.NORMAL:
                normal_duration = timestamp - prev_record.state_entered_at
            self._stability_records[grouping_key] = CellStabilityRecord(
                grouping_key=grouping_key,
                current_state=new_state,
                state_entered_at=timestamp,
                normal_duration_seconds=normal_duration,
            )
        else:
            self._stability_records[grouping_key] = CellStabilityRecord(
                grouping_key=grouping_key,
                current_state=new_state,
                state_entered_at=timestamp,
                normal_duration_seconds=0.0,
            )

    def get_stability_record(self, grouping_key: GroupingKey) -> Optional[CellStabilityRecord]:
        return self._stability_records.get(grouping_key)
