import struct
from typing import Optional
from ..models import RATType, RATBlock, ParsedPacket

PACKET_LENGTH = 67
RAT_BLOCK_SIZE = 23

# struct format: big-endian
# Version(1B) + MsgType(1B) + TotalLength(2B) + RouterCTN(15B) +
# Primary(23B) + Secondary(23B) + Reserved(2B) = 67B
_HEADER_FMT = ">BBH15s"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 19

# RAT_Block: RAT_Type(1B) + PLMN_ID(3B) + ECGI/NRCGI(5B) + ARFCN(4B) + Timestamp(8B) + UL_RB_Usage(2B)
_RAT_FMT = ">B3s5sIQH"  # 1+3+5+4+8+2 = 23B


class PacketValidationError(Exception):
    pass


class PacketParser:

    SUPPORTED_VERSIONS = {0x01}
    SUPPORTED_MESSAGE_TYPES = {0x01}

    @staticmethod
    def parse(data: bytes) -> ParsedPacket:
        if len(data) != PACKET_LENGTH:
            raise PacketValidationError(
                f"Invalid packet length: expected {PACKET_LENGTH}, got {len(data)}"
            )

        version, message_type, total_length, ctn_raw = struct.unpack_from(_HEADER_FMT, data, 0)

        if version not in PacketParser.SUPPORTED_VERSIONS:
            raise PacketValidationError(f"Unsupported version: 0x{version:02X}")

        if message_type not in PacketParser.SUPPORTED_MESSAGE_TYPES:
            raise PacketValidationError(f"Unsupported message type: 0x{message_type:02X}")

        if total_length != PACKET_LENGTH:
            raise PacketValidationError(
                f"TotalLength field mismatch: {total_length} != {PACKET_LENGTH}"
            )

        router_ctn = ctn_raw.rstrip(b"\x00").decode("ascii", errors="replace")

        offset = _HEADER_SIZE  # 19
        primary = PacketParser._parse_rat_block(data[offset: offset + RAT_BLOCK_SIZE])
        offset += RAT_BLOCK_SIZE  # 42

        if primary.rat_type not in (RATType.LTE_PRIMARY, RATType.NR, RATType.REDCAP):
            raise PacketValidationError(
                f"Invalid Primary RAT_Type: 0x{primary.rat_type.value:02X}"
            )

        secondary_raw = data[offset: offset + RAT_BLOCK_SIZE]
        secondary = PacketParser._parse_rat_block(secondary_raw)
        if secondary.rat_type == RATType.NONE:
            secondary = None

        offset += RAT_BLOCK_SIZE  # 65
        reserved = struct.unpack_from(">H", data, offset)[0]

        return ParsedPacket(
            version=version,
            message_type=message_type,
            total_length=total_length,
            router_ctn=router_ctn,
            primary=primary,
            secondary=secondary,
            reserved=reserved,
        )

    @staticmethod
    def _parse_rat_block(data: bytes) -> RATBlock:
        # RAT_Type(1B) + PLMN_ID(3B) + ECGI/NRCGI(5B) + ARFCN(4B) + Timestamp(8B) + UL_RB_Usage(2B)
        rat_type_val, plmn_id, ecgi_bytes, arfcn, timestamp, ul_rb_usage = struct.unpack(
            _RAT_FMT, data
        )

        try:
            rat_type = RATType(rat_type_val)
        except ValueError:
            raise PacketValidationError(f"Unknown RAT_Type: 0x{rat_type_val:02X}")

        # ECGI/NRCGI: 5바이트를 big-endian 정수로 변환
        ecgi = int.from_bytes(ecgi_bytes, "big")

        return RATBlock(
            rat_type=rat_type,
            plmn_id=plmn_id,
            ecgi=ecgi,
            arfcn=arfcn,
            timestamp=timestamp,
            ul_rb_usage=ul_rb_usage,
        )
