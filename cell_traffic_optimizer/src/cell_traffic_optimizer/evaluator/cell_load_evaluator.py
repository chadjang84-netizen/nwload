from ..models import CellState, ThresholdConfig, GroupingKey


class CellLoadEvaluator:

    def __init__(self, thresholds: dict):  # band (int) -> ThresholdConfig
        self._thresholds = thresholds

    def evaluate(self, grouping_key: GroupingKey, ul_rb_sum: int, current_state: CellState) -> CellState:
        t = self._thresholds.get(grouping_key.band)
        if t is None:
            return current_state

        if current_state == CellState.NORMAL:
            if ul_rb_sum >= t.warning:
                return CellState.WARNING
            return CellState.NORMAL

        if current_state == CellState.WARNING:
            if ul_rb_sum >= t.congestion:
                return CellState.CONGESTION
            if ul_rb_sum < t.warning:
                return CellState.NORMAL
            return CellState.WARNING

        if current_state == CellState.CONGESTION:
            if ul_rb_sum >= t.overload_enter:
                return CellState.OVERLOAD
            if ul_rb_sum < t.congestion:
                return CellState.WARNING
            return CellState.CONGESTION

        if current_state == CellState.OVERLOAD:
            if ul_rb_sum < t.overload_exit:
                return CellState.NORMAL
            return CellState.OVERLOAD

        return current_state
