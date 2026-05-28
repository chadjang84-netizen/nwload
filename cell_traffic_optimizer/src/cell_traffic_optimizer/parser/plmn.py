"""
PLMN_ID (3GPP TS 24.008 §10.5.1.13) BCD <-> 표현 변환 유틸.

BCD 3바이트 구조:
    Byte 0: [MCC digit2 | MCC digit1]
    Byte 1: [MNC digit3 | MCC digit3]   (MNC가 2자리면 digit3 = 0xF)
    Byte 2: [MNC digit2 | MNC digit1]
"""
from __future__ import annotations

# 한국 통신사 PLMN 매핑 (450 = KR MCC)
_KR_OPERATORS: dict[tuple[str, str], str] = {
    ("450", "05"): "SKT",
    ("450", "11"): "SKT",      # IoT
    ("450", "06"): "Uplus",
    ("450", "08"): "KT",
    ("450", "02"): "KT",       # IoT 일부
    ("450", "04"): "KT",
}


def _nibble_hi(b: int) -> int:
    return (b >> 4) & 0x0F


def _nibble_lo(b: int) -> int:
    return b & 0x0F


def decode_plmn(plmn_bytes: bytes) -> tuple[str, str]:
    """3바이트 BCD PLMN_ID → (MCC, MNC) 문자열 튜플.

    invalid한 입력(길이 != 3, 모두 0x00 등)은 ("000", "00")으로 안전 처리.
    """
    if not isinstance(plmn_bytes, (bytes, bytearray)) or len(plmn_bytes) != 3:
        return ("000", "00")

    b0, b1, b2 = plmn_bytes[0], plmn_bytes[1], plmn_bytes[2]

    mcc_d1 = _nibble_lo(b0)
    mcc_d2 = _nibble_hi(b0)
    mcc_d3 = _nibble_lo(b1)
    mnc_d3 = _nibble_hi(b1)
    mnc_d1 = _nibble_lo(b2)
    mnc_d2 = _nibble_hi(b2)

    mcc = f"{mcc_d1}{mcc_d2}{mcc_d3}"
    if mnc_d3 == 0xF:
        mnc = f"{mnc_d1}{mnc_d2}"
    else:
        mnc = f"{mnc_d1}{mnc_d2}{mnc_d3}"

    # 모든 니블이 0~9 범위 밖이면 invalid
    if not (mcc.isdigit() and mnc.isdigit()):
        return ("000", "00")

    return (mcc, mnc)


def format_plmn(plmn_bytes: bytes) -> str:
    """3바이트 BCD PLMN_ID → 표시용 문자열.

    예: b"\\x54\\xF0\\x60" → "Uplus (450-06)"
        알 수 없는 PLMN → "450-99"
        invalid → "Unknown"
    """
    mcc, mnc = decode_plmn(plmn_bytes)
    if mcc == "000":
        return "Unknown"

    raw = f"{mcc}-{mnc}"
    name = _KR_OPERATORS.get((mcc, mnc))
    if name:
        return f"{name} ({raw})"
    return raw
