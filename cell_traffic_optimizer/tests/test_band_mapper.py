import pytest
from cell_traffic_optimizer.aggregator.band_mapper import BandMapper
from cell_traffic_optimizer.models import RATType


def test_earfcn_band1():
    assert BandMapper.earfcn_to_band(0) == 1
    assert BandMapper.earfcn_to_band(599) == 1


def test_earfcn_band3():
    assert BandMapper.earfcn_to_band(1200) == 3
    assert BandMapper.earfcn_to_band(1850) == 3


def test_earfcn_band7():
    assert BandMapper.earfcn_to_band(2750) == 7
    assert BandMapper.earfcn_to_band(3449) == 7


def test_earfcn_band8():
    assert BandMapper.earfcn_to_band(3450) == 8


def test_earfcn_band28():
    assert BandMapper.earfcn_to_band(9210) == 28


def test_earfcn_unknown():
    with pytest.raises(ValueError, match="EARFCN"):
        BandMapper.earfcn_to_band(999999)


def test_nrarfcn_band78():
    assert BandMapper.nrarfcn_to_band(620000) == 78
    assert BandMapper.nrarfcn_to_band(640000) == 78


def test_nrarfcn_band41():
    assert BandMapper.nrarfcn_to_band(499200) == 41


def test_nrarfcn_band257():
    assert BandMapper.nrarfcn_to_band(2054166) == 257


def test_nrarfcn_unknown():
    with pytest.raises(ValueError, match="NR_ARFCN"):
        BandMapper.nrarfcn_to_band(9999999)


def test_arfcn_to_band_lte():
    assert BandMapper.arfcn_to_band(1850, RATType.LTE_PRIMARY) == 3


def test_arfcn_to_band_nr():
    assert BandMapper.arfcn_to_band(627264, RATType.NR) == 78


def test_arfcn_to_band_invalid_rat():
    with pytest.raises(ValueError, match="RAT_Type"):
        BandMapper.arfcn_to_band(1850, RATType.NONE)
