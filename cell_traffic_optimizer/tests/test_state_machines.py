import pytest
from cell_traffic_optimizer.state_machine import CellStateMachine, DeviceStateMachine
from cell_traffic_optimizer.models import CellState, DeviceState, QualityProfile, GroupingKey

KEY = GroupingKey(ecgi=1000, band=3)
T = 1000.0


# ─── CellStateMachine ───────────────────────────────────────────────────────

def test_cell_default_state():
    sm = CellStateMachine()
    assert sm.get_state(KEY) == CellState.NORMAL


def test_cell_normal_to_warning():
    sm = CellStateMachine()
    result = sm.transition(KEY, CellState.WARNING, T)
    assert result.success
    assert sm.get_state(KEY) == CellState.WARNING


def test_cell_sequential_transitions():
    sm = CellStateMachine()
    sm.transition(KEY, CellState.WARNING, T)
    sm.transition(KEY, CellState.CONGESTION, T)
    sm.transition(KEY, CellState.OVERLOAD, T)
    assert sm.get_state(KEY) == CellState.OVERLOAD


def test_cell_overload_to_normal():
    sm = CellStateMachine()
    sm.transition(KEY, CellState.WARNING, T)
    sm.transition(KEY, CellState.CONGESTION, T)
    sm.transition(KEY, CellState.OVERLOAD, T)
    result = sm.transition(KEY, CellState.NORMAL, T)
    assert result.success
    assert sm.get_state(KEY) == CellState.NORMAL


def test_cell_invalid_transition_rejected():
    sm = CellStateMachine()
    result = sm.transition(KEY, CellState.OVERLOAD, T)  # NORMAL → OVERLOAD: invalid
    assert not result.success
    assert sm.get_state(KEY) == CellState.NORMAL


def test_cell_ctn_list_on_overload():
    sm = CellStateMachine()
    sm.update_ctns(KEY, {"ctn1", "ctn2", "ctn3"})
    sm.transition(KEY, CellState.WARNING, T)
    sm.transition(KEY, CellState.CONGESTION, T)
    result = sm.transition(KEY, CellState.OVERLOAD, T)
    assert set(result.ctn_list) == {"ctn1", "ctn2", "ctn3"}


def test_cell_stability_record_updated():
    sm = CellStateMachine()
    sm.transition(KEY, CellState.WARNING, T)
    record = sm.get_stability_record(KEY)
    assert record is not None
    assert record.current_state == CellState.WARNING


def test_cell_same_state_transition_is_noop():
    sm = CellStateMachine()
    sm.transition(KEY, CellState.WARNING, T)
    result = sm.transition(KEY, CellState.WARNING, T + 10)
    assert result.success  # no-op is ok, state unchanged


# ─── DeviceStateMachine ─────────────────────────────────────────────────────

def test_device_degrade_normal_to_degraded():
    sm = DeviceStateMachine()
    result = sm.degrade("ctn1", T)
    assert result.success
    assert result.new_state == DeviceState.DEGRADED
    assert result.new_profile == QualityProfile.DEGRADED


def test_device_start_recovery():
    sm = DeviceStateMachine()
    sm.degrade("ctn1", T)
    result = sm.start_recovery("ctn1", T + 100)
    assert result.success
    assert result.new_state == DeviceState.RECOVERY_PENDING


def test_device_step_up_degraded_to_step_up():
    sm = DeviceStateMachine(recovery_cooldown_seconds=60)
    sm.degrade("ctn1", T)
    sm.start_recovery("ctn1", T)
    result = sm.step_up("ctn1", T + 60)
    assert result.success
    assert result.new_profile == QualityProfile.STEP_UP


def test_device_step_up_step_up_to_normal():
    sm = DeviceStateMachine(recovery_cooldown_seconds=60)
    sm.degrade("ctn1", T)
    sm.start_recovery("ctn1", T)
    sm.step_up("ctn1", T + 60)   # DEGRADED → STEP_UP
    result = sm.step_up("ctn1", T + 120)  # STEP_UP → NORMAL
    assert result.success
    assert result.new_state == DeviceState.NORMAL
    assert result.new_profile == QualityProfile.NORMAL


def test_device_cancel_recovery():
    sm = DeviceStateMachine()
    sm.degrade("ctn1", T)
    sm.start_recovery("ctn1", T)
    result = sm.cancel_recovery("ctn1", T + 10)
    assert result.success
    assert result.new_state == DeviceState.DEGRADED
    assert result.new_profile == QualityProfile.DEGRADED


def test_device_cooldown_expired():
    sm = DeviceStateMachine(recovery_cooldown_seconds=300)
    sm.degrade("ctn1", T)
    sm.start_recovery("ctn1", T)
    assert not sm.is_cooldown_expired("ctn1", T + 299)
    assert sm.is_cooldown_expired("ctn1", T + 300)


def test_device_invalid_degrade_from_degraded():
    sm = DeviceStateMachine()
    sm.degrade("ctn1", T)
    result = sm.degrade("ctn1", T + 1)  # already DEGRADED
    assert not result.success


def test_device_history_updated():
    sm = DeviceStateMachine()
    sm.degrade("ctn1", T)
    h = sm.get_history("ctn1")
    assert h is not None
    assert h.current_state == DeviceState.DEGRADED
    assert h.current_profile == QualityProfile.DEGRADED
