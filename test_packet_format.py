import struct, sys
sys.path.insert(0, r'C:\Users\chadjang\Claude code_projects\NWload\cell_traffic_optimizer\src')

# ── simulate_advanced.py의 PacketBuilder 로직 인라인 검증 ──────────────────────
RAT_BLOCK_FMT = ">B3s5sIQH"  # 1+3+5+4+8+2 = 23

def build_rat_block(rat_type, plmn_id, ecgi, arfcn, ts_ms, ul_rb):
    return struct.pack(RAT_BLOCK_FMT, rat_type, plmn_id, ecgi.to_bytes(5,"big"), arfcn, ts_ms, ul_rb)

def build_packet(ctn, primary, secondary):
    header = struct.pack(">BBH15s", 0x01, 0x01, 67, ctn)
    pkt = header + primary + secondary + b"\x00\x00"
    assert len(pkt) == 67, f"length={len(pkt)}"
    return pkt

# 테스트 패킷 생성
plmn = bytes([0x44, 0x50, 0x06])
ts = 1714432389000

# LTE-only 단말
p1 = build_rat_block(0x01, plmn, 12345, 2400, ts, 5)
s1 = bytes(23)
pkt_lte = build_packet(b'01000000001\x00\x00\x00\x00', p1, s1)
print(f"LTE-only packet: {len(pkt_lte)}B OK")

# NSA 단말
p2 = build_rat_block(0x01, plmn, 12345, 2400, ts, 8)
s2 = build_rat_block(0x02, plmn, 10101, 630000, ts, 8)
pkt_nsa = build_packet(b'01000000002\x00\x00\x00\x00', p2, s2)
print(f"NSA packet:      {len(pkt_nsa)}B OK")

# ── 백엔드 PacketParser로 파싱 검증 ───────────────────────────────────────────
from cell_traffic_optimizer.parser.packet_parser import PacketParser
from cell_traffic_optimizer.models.enums import RATType

parsed = PacketParser.parse(pkt_lte)
print(f"\n[LTE-only 파싱]")
print(f"  router_ctn : {parsed.router_ctn}")
print(f"  primary    : rat={parsed.primary.rat_type}, ecgi={parsed.primary.ecgi}, arfcn={parsed.primary.arfcn}, ul_rb={parsed.primary.ul_rb_usage}")
print(f"  secondary  : {parsed.secondary}")

parsed2 = PacketParser.parse(pkt_nsa)
print(f"\n[NSA 파싱]")
print(f"  primary    : rat={parsed2.primary.rat_type}, ecgi={parsed2.primary.ecgi}, arfcn={parsed2.primary.arfcn}, ul_rb={parsed2.primary.ul_rb_usage}")
print(f"  secondary  : rat={parsed2.secondary.rat_type}, ecgi={parsed2.secondary.ecgi}, arfcn={parsed2.secondary.arfcn}, ul_rb={parsed2.secondary.ul_rb_usage}")

print("\n모든 패킷 포맷 검증 통과")
