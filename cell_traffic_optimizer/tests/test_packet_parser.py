import struct
import pytest
from cell_traffic_optimizer.parser import PacketParser, PacketValidationError
from cell_traffic_optimizer.models import RATType


def _make_rat_block(
    rat_type: int = 0x01,
    plmn_id: bytes = b"\x00\x10\x00",
    ecgi_high: int = 0,
    ecgi_low: int = 12345,
    arfcn: int = 1850,
    timestamp: int = 1700000000,
    ul_rb_usage: int = 50,
) -> bytes:
    ecgi_low_bytes = struct.pack(">I", ecgi_low)
    return struct.pack(">B3sB4sIQH", rat_type, plmn_id, ecgi_high, ecgi_low_bytes, arfcn, timestamp, ul_rb_usage)


def _make_packet(
    version: int = 0x01,
    message_type: int = 0x01,
    total_length: int = 67,
    router_ctn: str = "01012345678",
    primary_block: bytes = None,
    secondary_block: bytes = None,
) -> bytes:
    ctn_raw = router_ctn.encode("ascii").ljust(15, b"\x00")
    if primary_block is None:
        primary_block = _make_rat_block()
    if secondary_block is None:
        secondary_block = _make_rat_block(rat_type=0x00, ul_rb_usage=0)
    reserved = b"\x00\x00"
    header = struct.pack(">BBH15s", version, message_type, total_length, ctn_raw)
    return header + primary_block + secondary_block + reserved


def test_parse_valid_packet():
    data = _make_packet()
    pkt = PacketParser.parse(data)
    assert pkt.version == 0x01
    assert pkt.message_type == 0x01
    assert pkt.total_length == 67
    assert pkt.router_ctn == "01012345678"
    assert pkt.primary.rat_type == RATType.LTE_PRIMARY
    assert pkt.primary.ul_rb_usage == 50
    assert pkt.secondary is None


def test_parse_invalid_length():
    with pytest.raises(PacketValidationError, match="Invalid packet length"):
        PacketParser.parse(b"\x00" * 66)


def test_parse_invalid_version():
    data = _make_packet(version=0xFF)
    with pytest.raises(PacketValidationError, match="Unsupported version"):
        PacketParser.parse(data)


def test_parse_invalid_message_type():
    data = _make_packet(message_type=0xFF)
    with pytest.raises(PacketValidationError, match="Unsupported message type"):
        PacketParser.parse(data)


def test_parse_total_length_mismatch():
    data = _make_packet(total_length=100)
    with pytest.raises(PacketValidationError, match="TotalLength field mismatch"):
        PacketParser.parse(data)


def test_parse_invalid_primary_rat_type():
    bad_primary = _make_rat_block(rat_type=0x00)
    data = _make_packet(primary_block=bad_primary)
    with pytest.raises(PacketValidationError, match="Invalid Primary RAT_Type"):
        PacketParser.parse(data)


def test_parse_secondary_rat_type_none():
    secondary = _make_rat_block(rat_type=0x00, ul_rb_usage=0)
    data = _make_packet(secondary_block=secondary)
    pkt = PacketParser.parse(data)
    assert pkt.secondary is None


def test_parse_secondary_rat_type_nr():
    secondary = _make_rat_block(rat_type=0x02, arfcn=627264, ul_rb_usage=30)
    data = _make_packet(secondary_block=secondary)
    pkt = PacketParser.parse(data)
    assert pkt.secondary is not None
    assert pkt.secondary.rat_type == RATType.NR
    assert pkt.secondary.ul_rb_usage == 30


def test_parse_nsa_two_blocks():
    primary = _make_rat_block(rat_type=0x01, arfcn=1850, ul_rb_usage=50)
    secondary = _make_rat_block(rat_type=0x02, arfcn=627264, ul_rb_usage=30)
    data = _make_packet(primary_block=primary, secondary_block=secondary)
    pkt = PacketParser.parse(data)
    assert pkt.primary.rat_type == RATType.LTE_PRIMARY
    assert pkt.secondary.rat_type == RATType.NR


def test_parse_router_ctn_null_padding():
    data = _make_packet(router_ctn="0101234")
    pkt = PacketParser.parse(data)
    assert pkt.router_ctn == "0101234"
    assert "\x00" not in pkt.router_ctn


def test_parse_redcap_primary():
    primary = _make_rat_block(rat_type=0x03)
    data = _make_packet(primary_block=primary)
    pkt = PacketParser.parse(data)
    assert pkt.primary.rat_type == RATType.REDCAP
