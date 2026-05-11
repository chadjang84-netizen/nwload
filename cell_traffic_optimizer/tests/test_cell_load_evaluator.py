import pytest
from cell_traffic_optimizer.evaluator import CellLoadEvaluator
from cell_traffic_optimizer.models import CellState, ThresholdConfig, GroupingKey

T = ThresholdConfig(warning=100, congestion=200, overload_enter=300, overload_exit=250)
KEY = GroupingKey(ecgi=1, band=3)


def eval(current: CellState, usage: int) -> CellState:
    return CellLoadEvaluator({KEY.band: T}).evaluate(KEY, usage, current)


def test_normal_to_warning():
    assert eval(CellState.NORMAL, 101) == CellState.WARNING


def test_normal_stays_normal():
    assert eval(CellState.NORMAL, 99) == CellState.NORMAL  # < warning(100)


def test_warning_to_congestion():
    assert eval(CellState.WARNING, 200) == CellState.CONGESTION  # >= congestion(200)


def test_warning_stays_warning():
    assert eval(CellState.WARNING, 150) == CellState.WARNING


def test_warning_to_normal():
    assert eval(CellState.WARNING, 99) == CellState.NORMAL  # < warning(100)


def test_congestion_to_overload():
    assert eval(CellState.CONGESTION, 301) == CellState.OVERLOAD


def test_congestion_stays_congestion():
    assert eval(CellState.CONGESTION, 250) == CellState.CONGESTION


def test_congestion_to_warning():
    assert eval(CellState.CONGESTION, 199) == CellState.WARNING  # < congestion(200)


def test_overload_to_normal_hysteresis():
    # overload_exit=250: must go below 250 to exit overload
    assert eval(CellState.OVERLOAD, 249) == CellState.NORMAL


def test_overload_stays_overload_above_exit():
    # at overload_exit=250, stays overload (not < 250)
    assert eval(CellState.OVERLOAD, 250) == CellState.OVERLOAD


def test_overload_stays_overload_high():
    assert eval(CellState.OVERLOAD, 500) == CellState.OVERLOAD


def test_hysteresis_no_direct_overload_to_warning():
    # Once overload, must reach < overload_exit(250) to exit — even if below overload_enter(300)
    assert eval(CellState.OVERLOAD, 280) == CellState.OVERLOAD
