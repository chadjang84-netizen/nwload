import pytest
from cell_traffic_optimizer.models import (
    RATType, CellState, DeviceState, QualityProfile, DeviceAction,
    GroupingKey, ThresholdConfig,
)


def test_grouping_key_hashable():
    k1 = GroupingKey(ecgi=12345, band=3)
    k2 = GroupingKey(ecgi=12345, band=3)
    assert k1 == k2
    assert hash(k1) == hash(k2)
    assert k1 in {k2}


def test_grouping_key_frozen():
    k = GroupingKey(ecgi=1, band=1)
    with pytest.raises(Exception):
        k.ecgi = 2  # type: ignore


def test_threshold_config_valid():
    cfg = ThresholdConfig(warning=100, congestion=200, overload_enter=300, overload_exit=250)
    assert cfg.warning == 100


def test_threshold_config_invalid_order():
    with pytest.raises(ValueError):
        ThresholdConfig(warning=300, congestion=200, overload_enter=100, overload_exit=50)


def test_threshold_config_exit_ge_enter():
    with pytest.raises(ValueError):
        ThresholdConfig(warning=100, congestion=200, overload_enter=300, overload_exit=300)


def test_rat_type_values():
    assert RATType.NONE.value == 0x00
    assert RATType.LTE_PRIMARY.value == 0x01
    assert RATType.NR.value == 0x02
    assert RATType.REDCAP.value == 0x03


def test_cell_state_values():
    assert CellState.NORMAL.value == "정상"
    assert CellState.WARNING.value == "주의"
    assert CellState.CONGESTION.value == "혼잡"
    assert CellState.OVERLOAD.value == "과부하"


def test_device_state_values():
    assert DeviceState.NORMAL.value == "NORMAL"
    assert DeviceState.DEGRADED.value == "DEGRADED"
    assert DeviceState.RECOVERY_PENDING.value == "RECOVERY_PENDING"


def test_quality_profile_values():
    assert QualityProfile.DEGRADED.value == "DEGRADED"
    assert QualityProfile.STEP_UP.value == "STEP_UP"
    assert QualityProfile.NORMAL.value == "NORMAL"
