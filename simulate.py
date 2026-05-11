"""
Cell Traffic Optimizer - 시뮬레이터

시나리오:
  1. NORMAL   : 3개 단말이 낮은 UL_RB 송신 (합계 ~600)
  2. WARNING  : UL_RB 증가 (합계 ~1500)
  3. CONGESTION: UL_RB 증가 (합계 ~2500)
  4. OVERLOAD  : UL_RB 급증 (합계 ~3500) -> 단말 화질 저하 트리거
  5. RECOVERY  : UL_RB 감소 (합계 ~800)  -> 단말 복구 대기 시작

사용법:
    python simulate.py [--url http://localhost:8000] [--interval 1.0] [--scenario all]

시나리오 종류:
    all        전체 시나리오 순서대로 실행 (기본값)
    normal     정상 구간만 반복
    overload   과부하 구간만 반복
    recovery   복구 구간만 반복
"""
import argparse
import struct
import time
import sys
import urllib.request
import urllib.error

# ── 패킷 구조 상수 ────────────────────────────────────────────────────────────
PACKET_LENGTH = 67
VERSION       = 0x01
MSG_TYPE      = 0x01

RAT_LTE = 0x01
RAT_NR  = 0x02
RAT_NONE= 0x00

# LTE Band 3: EARFCN 1300 (2100 MHz)
# LTE Band 1: EARFCN 100
PLMN_ID = bytes([0x45, 0x09, 0x10])  # 한국 SKT 예시

# 셀 A: ECGI=1, LTE Band 3 (EARFCN 1300)
CELL_A_ECGI  = 1          # 5바이트 Cell ID
CELL_A_ARFCN = 1300       # LTE Band 3

# 단말 목록
DEVICES = [
    b"01012340001\x00\x00\x00\x00",
    b"01012340002\x00\x00\x00\x00",
    b"01012340003\x00\x00\x00\x00",
]


def build_rat_block(rat_type: int, ecgi: int, arfcn: int,
                    timestamp: int, ul_rb: int) -> bytes:
    # >B3s5sIQH = 1+3+5+4+8+2 = 23 bytes
    ecgi_bytes = ecgi.to_bytes(5, "big")
    return struct.pack(
        ">B3s5sIQH",
        rat_type, PLMN_ID,
        ecgi_bytes,
        arfcn,
        timestamp,
        ul_rb,
    )


def build_null_rat_block() -> bytes:
    return bytes(23)


def build_packet(router_ctn: bytes, ul_rb: int, ts: int) -> bytes:
    primary = build_rat_block(RAT_LTE, CELL_A_ECGI, CELL_A_ARFCN, ts, ul_rb)
    secondary = build_null_rat_block()
    reserved = b"\x00\x00"

    header = struct.pack(">BBH15s", VERSION, MSG_TYPE, PACKET_LENGTH, router_ctn)
    pkt = header + primary + secondary + reserved
    assert len(pkt) == PACKET_LENGTH, f"Packet length error: {len(pkt)}"
    return pkt


def send_packet(url: str, data: bytes) -> dict:
    req = urllib.request.Request(
        f"{url}/api/ingest/packet",
        data=data,
        method="POST",
        headers={"Content-Type": "application/octet-stream"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [HTTP {e.code}] {body}")
        return {}
    except Exception as e:
        print(f"  [ERROR] {e}")
        return {}


def run_phase(name: str, url: str, ul_rbs: list, interval: float, rounds: int):
    """단말별 UL_RB를 지정해서 rounds회 패킷 전송"""
    print(f"\n{'='*50}")
    print(f"  Phase: {name}")
    print(f"  UL_RB per device: {ul_rbs}  (total ~{sum(ul_rbs)})")
    print(f"  Rounds: {rounds} x interval {interval}s")
    print(f"{'='*50}")

    for r in range(1, rounds + 1):
        ts = int(time.time())
        results = []
        for i, ctn in enumerate(DEVICES):
            ul_rb = ul_rbs[i % len(ul_rbs)]
            pkt = build_packet(ctn, ul_rb, ts)
            result = send_packet(url, pkt)
            results.append(result)

        # 요약 출력
        transitions = sum(r.get("cellTransitions", 0) for r in results)
        actions     = sum(r.get("deviceActions", 0) for r in results)
        status = ""
        if transitions: status += f" [CELL_TRANSITION x{transitions}]"
        if actions:     status += f" [DEVICE_ACTION x{actions}]"
        print(f"  [{r:2d}/{rounds}] ts={ts}  total_UL_RB~{sum(ul_rbs)}{status}")

        if r < rounds:
            time.sleep(interval)


SCENARIOS = {
    "normal": [
        ("NORMAL - low load",    [150, 200, 250],  10),
    ],
    "overload": [
        ("WARNING",              [350, 400, 450],   5),
        ("CONGESTION",           [600, 700, 800],   5),
        ("OVERLOAD",             [900, 1100, 1500], 5),
    ],
    "recovery": [
        ("RECOVERY - low load",  [150, 200, 250],  10),
    ],
    "all": [
        ("NORMAL - low load",    [150, 200, 250],  8),
        ("WARNING",              [350, 400, 450],  5),
        ("CONGESTION",           [600, 700, 800],  5),
        ("OVERLOAD",             [900, 1100, 1500],5),
        ("RECOVERY - low load",  [100, 150, 200],  8),
    ],
}


def main():
    parser = argparse.ArgumentParser(description="Cell Traffic Optimizer Simulator")
    parser.add_argument("--url",      default="http://localhost:8000", help="Backend URL")
    parser.add_argument("--interval", default=1.0, type=float,         help="Seconds between rounds")
    parser.add_argument("--scenario", default="all", choices=list(SCENARIOS.keys()),
                        help="Scenario to run")
    args = parser.parse_args()

    print(f"Cell Traffic Optimizer Simulator")
    print(f"  Backend  : {args.url}")
    print(f"  Scenario : {args.scenario}")
    print(f"  Interval : {args.interval}s")
    print(f"  Devices  : {[d.rstrip(b'\\x00').decode() for d in DEVICES]}")

    # 백엔드 연결 확인
    try:
        urllib.request.urlopen(f"{args.url}/api/config", timeout=3)
        print(f"\n  Backend OK")
    except Exception as e:
        print(f"\n  [ERROR] Backend not reachable: {e}")
        sys.exit(1)

    phases = SCENARIOS[args.scenario]
    for name, ul_rbs, rounds in phases:
        run_phase(name, args.url, ul_rbs, args.interval, rounds)

    print(f"\n{'='*50}")
    print("  Simulation complete.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
