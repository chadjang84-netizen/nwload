"""
Advanced Cell Traffic Simulator

50개 셀(LTE Band 5 x25 + NR Band 78 x25), 100개 단말(LTE_ONLY/NR_SA/NSA)을
이용해 3-Phase 시나리오(정상 → 과부하 → 복구)를 시뮬레이션한다.

실제 단말과 동일한 67바이트 바이너리 패킷을 생성하여 서버 검증에 사용한다.

사용법:
    python simulate_advanced.py [options]

예시:
    # realtime 10배속 (30분 시나리오를 3분에)
    python simulate_advanced.py --mode realtime --host localhost --port 9000

    # 파일만 생성
    python simulate_advanced.py --mode file --output-dir ./sim_output
"""

import argparse
import json
import os
import random
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import List, Optional

# ── HTTP 클라이언트 (카메라/매핑 등록용, requests 없으면 urllib fallback) ──────
try:
    import requests as _requests
    _USE_REQUESTS = True
except ImportError:
    import urllib.request as _urllib_req
    import urllib.error as _urllib_err
    _USE_REQUESTS = False

# ── 패킷 포맷 상수 ─────────────────────────────────────────────────────────────
PACKET_LENGTH  = 67
VERSION        = 0x01
MSG_TYPE       = 0x01
RAT_LTE        = 0x01
RAT_NR         = 0x02
RAT_NONE       = 0x00

HEADER_FMT     = ">BBH15s"    # 1+1+2+15 = 19 bytes
RAT_BLOCK_FMT  = ">B3s5sIQH"  # 1+3+5+4+8+2 = 23 bytes

# PLMN ID — 한국 SKT: MCC=450, MNC=05
# 3GPP TS 24.008 BCD 인코딩: MCC digit2|digit1, MCC digit3|MNC digit3, MNC digit2|digit1
# MCC=4,5,0 / MNC=0,5 → nibble: 54 F0 05 (MNC digit3=F=absent)
DEFAULT_PLMN   = bytes([0x54, 0xF0, 0x05])

# ── 셀 구성 상수 ──────────────────────────────────────────────────────────────
# LTE Band 3 (EARFCN 1200~1949, 서버 임계값 band:3)
# 실제 기지국은 보통 같은 Band 내에서 50~100 간격으로 EARFCN을 배치
LTE_EARFCN_START = 1300   # Band 3 중간 대역 (1.8GHz)
LTE_EARFCN_STEP  = 50     # 셀 간 약 10MHz 간격
NR_ARFCN_START   = 623334 # NR Band 78 시작 대역 (620000~653333), 10셀 × 3000 = 30000 범위 내 수용
NR_ARFCN_STEP    = 3000   # 셀 간 약 15MHz 간격 (SCS 30kHz 기준)

# eNB ID 기반 ECGI 생성 (3GPP TS 36.413)
# ECGI = PLMN + ECI(28bit) = eNB_ID(20bit) + Cell_ID(8bit)
# 예시 eNB_ID: 0x12A00 (가상 기지국 ID 시작값)
LTE_ENB_ID_START = 0x12A00  # 20비트 eNB ID
# gNB ID 기반 NR CGI 생성 (3GPP TS 38.413)
# NR-CGI = PLMN + NCI(36bit) = gNB_ID(22~32bit) + Cell_ID
NR_GNB_ID_START  = 0x3E8000 # 22비트 gNB ID 시작값

NUM_LTE_CELLS    = 10
NUM_NR_CELLS     = 10

# ── 단말 구성 비율 (합계 30) ──────────────────────────────────────────────────
# 실제 5G NSA 상용망 기준: LTE 앵커 단말 40%, NR SA 20%, NSA 40%
NUM_LTE_ONLY  = 12
NUM_NR_SA     = 6
NUM_NSA       = 12
NUM_BURST     = 3    # burst 단말 수
NUM_IDLE      = 3    # idle 단말 수

# ── 트래픽 파라미터 ───────────────────────────────────────────────────────────
# 평가 방식: 슬라이딩 윈도우(60s) 만료 시 ul_rb_sum 합계로 임계값 판정
# 단말 30개, 패킷 간격 ~1초 → 윈도우 내 이벤트 수 ≈ 30 × 60 = 1800개
#
# 임계값(서버 기본값):
#   주의=10000, 혼잡=20000, 과부하진입=30000, 과부하해제=25000
#
# Phase 1 (정상): 단말당 ul_rb=3 → sum ≈ 3 × 1800 = 5400 → warning(10000) 미달
# Phase 2 (과부하): 단말당 ul_rb=20 → sum ≈ 20 × 1800 = 36000 → overload_enter(30000) 초과
# Phase 3 (복구): 단말당 ul_rb=3 → sum ≈ 5400 → warning(10000) 미달 → NORMAL 복귀
BASE_UL_RB         = 3    # Phase 1/3 단말당 ul_rb
OVERLOAD_UL_RB     = 20   # Phase 2 단말당 ul_rb: sum ≈ 36000 → overload_enter(30000) 초과
NOISE_FACTOR       = 0.20 # ±20%
IDLE_ZERO_PROB     = 0.30 # idle 단말이 0을 보낼 확률
BURST_INSTANT_PROB = 0.05 # burst 단말의 순간 폭발 확률
BURST_FACTOR_MIN   = 2.0  # burst 단말 순간 폭발 배율 하한 (일반 burst 이벤트용)
BURST_FACTOR_MAX   = 3.0  # burst 단말 순간 폭발 배율 상한
UL_RB_MAX          = 100  # 단말당 UL_RB 상한

# ── 시나리오 타이밍 (실제 분 = 시뮬레이션 분, speed_factor=1) ────────────────
# cooldown=1분(60s), step_up=1분(60s) → 화질 완전 복구 소요: 2분
# Phase 1(2분) + Phase 2(3분) + Phase 3(5분) = 총 10분
# Phase 3: 복구(2분) + 여유(3분)
PHASE1_END_MIN = 2.0
PHASE2_END_MIN = 5.0
PHASE3_END_MIN = 10.0
OVERLOAD_DEVICE_COUNT_MIN = 3
OVERLOAD_DEVICE_COUNT_MAX = 5


# ── 데이터 모델 ───────────────────────────────────────────────────────────────

@dataclass
class CellInfo:
    cell_id: int
    rat_type: int       # RAT_LTE or RAT_NR
    ecgi: int           # 5바이트 Cell ID (ECGI 또는 NRCGI)
    arfcn: int
    plmn_id: bytes = field(default_factory=lambda: DEFAULT_PLMN)

    def __repr__(self) -> str:
        rat = "LTE" if self.rat_type == RAT_LTE else "NR"
        return f"Cell({rat},ecgi={self.ecgi},arfcn={self.arfcn})"


@dataclass
class DeviceInfo:
    ctn: bytes           # 15바이트 null-padded
    device_type: str     # "LTE_ONLY" | "NR_SA" | "NSA"
    is_burst: bool
    is_idle: bool
    primary_cell: CellInfo
    secondary_cell: Optional[CellInfo]
    base_ul_rb: int = BASE_UL_RB
    _restored: bool = field(default=False, repr=False)

    @property
    def ctn_str(self) -> str:
        return self.ctn.rstrip(b'\x00').decode('ascii', errors='replace')


@dataclass
class SimState:
    current_phase: int = 0
    sim_start_monotonic: float = 0.0
    overload_cell: Optional[CellInfo] = None
    concentrated_devices: List['DeviceInfo'] = field(default_factory=list)
    restored_count: int = 0


# ── CellRegistry ──────────────────────────────────────────────────────────────

class CellRegistry:
    """LTE Band 3 x10 + NR Band 78 x10 셀을 생성하고 관리한다."""

    def __init__(self, plmn_id: bytes = DEFAULT_PLMN):
        self._plmn = plmn_id
        self._lte_cells: List[CellInfo] = []
        self._nr_cells: List[CellInfo] = []

    def build(self) -> List[CellInfo]:
        self._lte_cells = self._make_lte_cells()
        self._nr_cells = self._make_nr_cells()
        return self._lte_cells + self._nr_cells

    def _make_lte_cells(self) -> List[CellInfo]:
        cells = []
        for i in range(NUM_LTE_CELLS):
            # ECI = eNB_ID(20bit) << 8 | Cell_ID(8bit)
            # 하나의 eNB에 셀 여러 개 (섹터): Cell_ID 0,1,2 반복
            enb_id  = LTE_ENB_ID_START + (i // 3)   # eNB 3개
            cell_id = i % 3                           # 셀당 섹터 0~2
            eci = (enb_id << 8) | cell_id
            cells.append(CellInfo(
                cell_id=i,
                rat_type=RAT_LTE,
                ecgi=eci,
                arfcn=LTE_EARFCN_START + i * LTE_EARFCN_STEP,
                plmn_id=self._plmn,
            ))
        return cells

    def _make_nr_cells(self) -> List[CellInfo]:
        cells = []
        for i in range(NUM_NR_CELLS):
            # NCI = gNB_ID(22bit) << 14 | Cell_ID(14bit)
            gnb_id  = NR_GNB_ID_START + (i // 3)    # gNB 3개
            cell_id = i % 3
            nci = (gnb_id << 14) | cell_id
            cells.append(CellInfo(
                cell_id=NUM_LTE_CELLS + i,
                rat_type=RAT_NR,
                ecgi=nci,
                arfcn=NR_ARFCN_START + i * NR_ARFCN_STEP,
                plmn_id=self._plmn,
            ))
        return cells

    def get_all(self) -> List[CellInfo]:
        return self._lte_cells + self._nr_cells

    def get_lte_cells(self) -> List[CellInfo]:
        return list(self._lte_cells)

    def get_nr_cells(self) -> List[CellInfo]:
        return list(self._nr_cells)


# ── DeviceRegistry ────────────────────────────────────────────────────────────

class DeviceRegistry:
    """100개 단말을 생성하고 셀 배정 / 이동을 관리한다."""

    def __init__(self, cells: List[CellInfo], seed: int = 42):
        self._rng = random.Random(seed)
        self._lte_cells = [c for c in cells if c.rat_type == RAT_LTE]
        self._nr_cells  = [c for c in cells if c.rat_type == RAT_NR]
        self.devices: List[DeviceInfo] = []

    def build(self) -> List[DeviceInfo]:
        devices = []
        idx = 0

        # LTE_ONLY
        for i in range(NUM_LTE_ONLY):
            cell = self._lte_cells[i % len(self._lte_cells)]
            devices.append(DeviceInfo(
                ctn=self._make_ctn(idx),
                device_type="LTE_ONLY",
                is_burst=False, is_idle=False,
                primary_cell=cell,
                secondary_cell=None,
            ))
            idx += 1

        # NR_SA
        for i in range(NUM_NR_SA):
            cell = self._nr_cells[i % len(self._nr_cells)]
            devices.append(DeviceInfo(
                ctn=self._make_ctn(idx),
                device_type="NR_SA",
                is_burst=False, is_idle=False,
                primary_cell=cell,
                secondary_cell=None,
            ))
            idx += 1

        # NSA
        for i in range(NUM_NSA):
            lte_cell = self._lte_cells[i % len(self._lte_cells)]
            nr_cell  = self._nr_cells[i % len(self._nr_cells)]
            devices.append(DeviceInfo(
                ctn=self._make_ctn(idx),
                device_type="NSA",
                is_burst=False, is_idle=False,
                primary_cell=lte_cell,
                secondary_cell=nr_cell,
            ))
            idx += 1

        # burst / idle 랜덤 지정
        burst_indices = self._rng.sample(range(len(devices)), NUM_BURST)
        idle_indices  = self._rng.sample(
            [i for i in range(len(devices)) if i not in burst_indices], NUM_IDLE
        )
        for i in burst_indices:
            devices[i].is_burst = True
        for i in idle_indices:
            devices[i].is_idle = True

        self.devices = devices
        return devices

    def _make_ctn(self, index: int) -> bytes:
        # 한국 이동전화 번호 형식: 010-XXXX-XXXX (11자리)
        # 시뮬레이터 번호 대역: 010-9000-0000 ~ 010-9000-0029
        number = 9000_0000 + index
        ctn_str = f"010{number:08d}"   # 예: "01090000000"
        encoded = ctn_str.encode('ascii')
        return encoded[:15].ljust(15, b'\x00')

    def assign_cells_uniformly(self) -> None:
        """Phase 1: 50개 셀에 round-robin 배치."""
        all_lte = self._lte_cells
        all_nr  = self._nr_cells
        lte_i = nr_i = 0
        for dev in self.devices:
            if dev.device_type == "LTE_ONLY":
                dev.primary_cell = all_lte[lte_i % len(all_lte)]
                lte_i += 1
            elif dev.device_type == "NR_SA":
                dev.primary_cell = all_nr[nr_i % len(all_nr)]
                nr_i += 1
            else:  # NSA
                dev.primary_cell   = all_lte[lte_i % len(all_lte)]
                dev.secondary_cell = all_nr[nr_i % len(all_nr)]
                lte_i += 1
                nr_i  += 1

    def move_to_overload_cell(
        self, overload_cell: CellInfo, count: int
    ) -> List[DeviceInfo]:
        """Phase 2: NSA/NR_SA 단말 중 count개를 overload_cell로 이동."""
        candidates = [
            d for d in self.devices
            if d.device_type in ("NSA", "NR_SA")
        ]
        self._rng.shuffle(candidates)
        selected = candidates[:count]

        for dev in selected:
            if dev.device_type == "NSA":
                dev.secondary_cell = overload_cell
            else:  # NR_SA
                dev.primary_cell = overload_cell
            # 단말당 평균 ul_rb를 과부하 임계값(20) 초과로 직접 설정
            dev.base_ul_rb = OVERLOAD_UL_RB
            dev._restored = False

        return selected

    def restore_all_immediately(
        self,
        concentrated: List[DeviceInfo],
        other_nr_cells: List[CellInfo],
    ) -> None:
        """Phase 3 진입 즉시 집중 단말 전원을 다른 NR 셀로 이동하고 UL_RB 정상화."""
        for dev in concentrated:
            if dev._restored:
                continue
            dest = self._rng.choice(other_nr_cells)
            if dev.device_type == "NSA":
                dev.secondary_cell = dest
            else:
                dev.primary_cell = dest
            dev.base_ul_rb = BASE_UL_RB
            dev._restored = True


# ── PacketBuilder ─────────────────────────────────────────────────────────────

class PacketBuilder:
    """67바이트 패킷 빌드 (static methods)."""

    @staticmethod
    def build_rat_block(
        rat_type: int,
        plmn_id: bytes,
        ecgi: int,
        arfcn: int,
        timestamp_ms: int,
        ul_rb: int,
    ) -> bytes:
        ecgi_bytes = ecgi.to_bytes(5, "big")
        return struct.pack(
            RAT_BLOCK_FMT,
            rat_type, plmn_id,
            ecgi_bytes,
            arfcn,
            timestamp_ms,
            ul_rb,
        )

    @staticmethod
    def build_null_rat_block() -> bytes:
        return bytes(23)

    @staticmethod
    def build_packet(
        router_ctn: bytes,
        primary_block: bytes,
        secondary_block: bytes,
    ) -> bytes:
        header = struct.pack(HEADER_FMT, VERSION, MSG_TYPE, PACKET_LENGTH, router_ctn)
        pkt = header + primary_block + secondary_block + b"\x00\x00"
        assert len(pkt) == PACKET_LENGTH, f"Packet length error: {len(pkt)}"
        return pkt

    @staticmethod
    def build_device_packet(
        device: DeviceInfo,
        ul_rb: int,
        timestamp_ms: int,
    ) -> bytes:
        primary = PacketBuilder.build_rat_block(
            device.primary_cell.rat_type,
            device.primary_cell.plmn_id,
            device.primary_cell.ecgi,
            device.primary_cell.arfcn,
            timestamp_ms,
            ul_rb,
        )
        if device.secondary_cell is not None:
            secondary = PacketBuilder.build_rat_block(
                device.secondary_cell.rat_type,
                device.secondary_cell.plmn_id,
                device.secondary_cell.ecgi,
                device.secondary_cell.arfcn,
                timestamp_ms,
                ul_rb,  # Secondary = Primary와 동일
            )
        else:
            secondary = PacketBuilder.build_null_rat_block()

        return PacketBuilder.build_packet(device.ctn, primary, secondary)


# ── TrafficModel ──────────────────────────────────────────────────────────────

class TrafficModel:
    """UL_RB 값을 계산한다 (noise, burst, idle 포함)."""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed + 1)

    def compute_ul_rb(self, device: DeviceInfo) -> int:
        if device.is_idle and self._rng.random() < IDLE_ZERO_PROB:
            return 0

        base = float(device.base_ul_rb)

        # burst 단말의 순간 폭발
        if device.is_burst and self._rng.random() < BURST_INSTANT_PROB:
            base *= self._rng.uniform(BURST_FACTOR_MIN, BURST_FACTOR_MAX)

        # ±20% noise
        base *= self._rng.uniform(1.0 - NOISE_FACTOR, 1.0 + NOISE_FACTOR)

        return max(0, min(UL_RB_MAX, int(base)))


# ── ScenarioController ────────────────────────────────────────────────────────

class ScenarioController:
    """시뮬레이션 시간을 관리하고 Phase 전환을 수행한다."""

    def __init__(
        self,
        device_registry: DeviceRegistry,
        cell_registry: CellRegistry,
        speed_factor: float,
    ):
        self._devices = device_registry
        self._cells   = cell_registry
        self._speed   = speed_factor
        self._state   = SimState()

    def start(self) -> None:
        self._state.sim_start_monotonic = time.monotonic()
        self._state.current_phase = 1
        self._devices.assign_cells_uniformly()

    def elapsed_sim_minutes(self) -> float:
        real_elapsed = time.monotonic() - self._state.sim_start_monotonic
        return real_elapsed * self._speed / 60.0

    def sim_timestamp_ms(self) -> int:
        elapsed_min = self.elapsed_sim_minutes()
        return int(time.time() * 1000) + int(elapsed_min * 60 * 1000)

    def tick_interval_seconds(self) -> float:
        """단말 전송 주기: 1분마다 1회 → 실제 60/speed_factor 초."""
        return 60.0 / self._speed

    def update_phase(self) -> bool:
        """Phase 전환 체크. 시뮬레이션 종료면 False 반환."""
        elapsed = self.elapsed_sim_minutes()

        if elapsed >= PHASE3_END_MIN:
            return False

        if self._state.current_phase == 1 and elapsed >= PHASE1_END_MIN:
            self._enter_phase2()

        elif self._state.current_phase == 2 and elapsed >= PHASE2_END_MIN:
            self._state.current_phase = 3
            nr_cells = self._cells.get_nr_cells()
            other_nr = [c for c in nr_cells if c != self._state.overload_cell]
            self._devices.restore_all_immediately(
                self._state.concentrated_devices, other_nr
            )
            restored = sum(1 for d in self._state.concentrated_devices if d._restored)
            print(f"\n[Phase 3] 복구 시작 (경과: {elapsed:.1f}분)")
            print(f"  집중 단말 {restored}개 → 다른 NR 셀로 즉시 이동, UL_RB 정상화")

        return True

    def _enter_phase2(self) -> None:
        rng = self._devices._rng
        nr_cells = self._cells.get_nr_cells()
        overload_cell = rng.choice(nr_cells)
        count = rng.randint(OVERLOAD_DEVICE_COUNT_MIN, OVERLOAD_DEVICE_COUNT_MAX)
        concentrated = self._devices.move_to_overload_cell(overload_cell, count)

        self._state.current_phase        = 2
        self._state.overload_cell        = overload_cell
        self._state.concentrated_devices = concentrated

        elapsed = self.elapsed_sim_minutes()
        print(f"\n[Phase 2] 과부하 발생 (경과: {elapsed:.1f}분)")
        print(f"  과부하 셀: {overload_cell}")
        print(f"  집중 단말 {len(concentrated)}개: {[d.ctn_str for d in concentrated]}")

    @property
    def current_phase(self) -> int:
        return self._state.current_phase

    @property
    def overload_cell(self) -> Optional[CellInfo]:
        return self._state.overload_cell

    def is_concentrated(self, device: DeviceInfo) -> bool:
        return device in self._state.concentrated_devices


# ── OutputManager ─────────────────────────────────────────────────────────────

class OutputManager:
    """UDP 송신, JSON 로그, 바이너리 출력을 관리한다."""

    def __init__(self, mode: str, host: str, port: int, output_dir: str):
        self._mode       = mode
        self._host       = host
        self._port       = port
        self._output_dir = output_dir
        self._json_log: List[dict] = []
        self._binary_buf = bytearray()
        self._seq        = 0
        self._sock: Optional[socket.socket] = None
        self._ts_suffix  = int(time.time())
        self._err_count  = 0

    def setup(self) -> None:
        os.makedirs(self._output_dir, exist_ok=True)
        if self._mode == "realtime":
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(
        self,
        pkt: bytes,
        device: DeviceInfo,
        ul_rb: int,
        sim_time_ms: int,
        phase: int,
    ) -> None:
        if self._mode == "realtime":
            self._udp_send(pkt)

        entry = self._make_log_entry(device, ul_rb, sim_time_ms, phase, pkt)
        self._json_log.append(entry)
        self._binary_buf.extend(pkt)
        self._seq += 1

    def _udp_send(self, pkt: bytes) -> None:
        try:
            self._sock.sendto(pkt, (self._host, self._port))
        except Exception as e:
            self._err_count += 1
            if self._err_count <= 5:
                print(f"  [UDP ERROR] {e}")

    def teardown(self) -> None:
        if self._sock:
            self._sock.close()

    def _make_log_entry(
        self,
        device: DeviceInfo,
        ul_rb: int,
        sim_time_ms: int,
        phase: int,
        pkt: bytes,
    ) -> dict:
        primary = {
            "rat_type": device.primary_cell.rat_type,
            "ecgi": device.primary_cell.ecgi,
            "arfcn": device.primary_cell.arfcn,
            "ul_rb": ul_rb,
        }
        secondary = None
        if device.secondary_cell is not None:
            secondary = {
                "rat_type": device.secondary_cell.rat_type,
                "ecgi": device.secondary_cell.ecgi,
                "arfcn": device.secondary_cell.arfcn,
                "ul_rb": ul_rb,
            }
        return {
            "seq":         self._seq,
            "sim_time_ms": sim_time_ms,
            "phase":       phase,
            "ctn":         device.ctn_str,
            "device_type": device.device_type,
            "is_burst":    device.is_burst,
            "is_idle":     device.is_idle,
            "primary":     primary,
            "secondary":   secondary,
            "raw_hex":     pkt.hex(),
        }

    def flush(self) -> None:
        ts = self._ts_suffix
        json_path = os.path.join(self._output_dir, f"sim_log_{ts}.json")
        bin_path  = os.path.join(self._output_dir, f"sim_packets_{ts}.bin")

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self._json_log, f, ensure_ascii=False, indent=2)

        with open(bin_path, 'wb') as f:
            f.write(self._binary_buf)

        pkt_count = len(self._binary_buf) // PACKET_LENGTH
        print(f"\n출력 파일 저장:")
        print(f"  JSON 로그:  {json_path}  ({len(self._json_log)} 레코드)")
        print(f"  바이너리:   {bin_path}   ({pkt_count} 패킷 x {PACKET_LENGTH}B)")

    def print_tick_summary(
        self,
        tick: int,
        phase: int,
        elapsed_min: float,
        sent: int,
        send_secs: float = 0.0,
    ) -> None:
        print(
            f"  Tick {tick:4d} | Phase {phase} | {elapsed_min:5.1f}min"
            f" | 전송:{sent:3d}개({send_secs:.3f}s) | 총:{self._seq:5d}패킷"
        )


# ── Simulator ─────────────────────────────────────────────────────────────────

class Simulator:
    """메인 시뮬레이션 루프를 실행한다."""

    def __init__(
        self,
        device_registry: DeviceRegistry,
        traffic_model: TrafficModel,
        scenario: ScenarioController,
        output: OutputManager,
        verbose: bool = False,
    ):
        self._devices  = device_registry
        self._traffic  = traffic_model
        self._scenario = scenario
        self._output   = output
        self._verbose  = verbose

    def run(self) -> None:
        self._output.setup()
        self._scenario.start()

        elapsed = self._scenario.elapsed_sim_minutes()
        print(f"\n시뮬레이션 시작 (총 {PHASE3_END_MIN:.0f}분 시나리오)")
        print(f"  단말: {len(self._devices.devices)}개 | 속도: {self._scenario._speed}배속")
        print(f"[Phase 1] 정상 상태 시작")

        tick = 0
        try:
            while True:
                tick_start = time.monotonic()

                if not self._scenario.update_phase():
                    break

                sim_ts  = self._scenario.sim_timestamp_ms()
                phase   = self._scenario.current_phase
                elapsed = self._scenario.elapsed_sim_minutes()

                sent = 0
                for dev in self._devices.devices:
                    ul_rb = self._traffic.compute_ul_rb(dev)
                    pkt   = PacketBuilder.build_device_packet(dev, ul_rb, sim_ts)
                    self._output.send(pkt, dev, ul_rb, sim_ts, phase)
                    sent += 1

                tick += 1
                elapsed_real = time.monotonic() - tick_start
                self._output.print_tick_summary(tick, phase, elapsed, sent, elapsed_real)

                # 전송에 걸린 시간을 제외하고 남은 시간만 sleep
                interval = self._scenario.tick_interval_seconds()
                remaining = interval - elapsed_real
                if remaining > 0:
                    time.sleep(remaining)
                elif self._verbose:
                    print(f"    [경고] 전송 소요({elapsed_real:.2f}s) > tick 간격({interval:.2f}s) — speed_factor를 낮추세요")

        except KeyboardInterrupt:
            print("\n시뮬레이션 중단됨 (Ctrl+C)")
        finally:
            self._output.teardown()
            self._output.flush()
            print("시뮬레이션 완료.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Advanced Cell Traffic Simulator - 50 cells, 100 devices, 3-phase scenario"
    )
    parser.add_argument(
        "--mode", choices=["realtime", "file"], default="realtime",
        help="realtime: UDP 즉시 전송 / file: 파일만 생성 (기본: realtime)"
    )
    parser.add_argument(
        "--host", default="localhost",
        help="백엔드 서버 호스트 (기본: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=9000,
        help="백엔드 UDP 포트 (기본: 9000)"
    )
    parser.add_argument(
        "--url", default="http://localhost:8000",
        help="백엔드 HTTP URL — 카메라/매핑 등록용 (기본: http://localhost:8000)"
    )
    parser.add_argument(
        "--output-dir", default="./sim_output",
        help="JSON/바이너리 출력 디렉터리 (기본: ./sim_output)"
    )
    parser.add_argument(
        "--speed-factor", type=float, default=1.0,
        help="시뮬레이션 배속 - 1이면 실제 시간과 1:1 동작 (기본: 1)"
    )
    parser.add_argument(
        "--num-cells", type=int, default=50,
        help="총 셀 수 (LTE/NR 절반씩, 기본: 50)"
    )
    parser.add_argument(
        "--num-devices", type=int, default=100,
        help="총 단말 수 (기본: 100, 현재 비율 고정)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="랜덤 시드 (기본: 42)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="셀 전이/단말 액션 발생 시 상세 출력"
    )
    # 향후 Kafka 확장용 플래그 (현재 미구현)
    parser.add_argument(
        "--kafka-brokers", default="",
        help="[미구현] 향후 Kafka 출력 확장용"
    )
    args = parser.parse_args()

    # 실시간 모드에서 백엔드 HTTP 연결 확인 (카메라/매핑 등록용)
    if args.mode == "realtime":
        try:
            if _USE_REQUESTS:
                r = _requests.get(f"{args.url}/api/config", timeout=3)
                r.raise_for_status()
            else:
                _urllib_req.urlopen(f"{args.url}/api/config", timeout=3)
            print(f"백엔드 HTTP 연결 확인: {args.url}")
        except Exception as e:
            print(f"[ERROR] 백엔드 HTTP 연결 실패: {e}")
            print("  --mode file 옵션으로 파일 생성 모드를 사용하거나 서버를 먼저 시작하세요.")
            return
        print(f"UDP 전송 대상: {args.host}:{args.port}")

    # 구성 요약 출력
    total_min  = PHASE3_END_MIN
    total_real = total_min * 60 / args.speed_factor

    print(f"\nCell Traffic Advanced Simulator")
    print(f"  모드:       {args.mode}")
    print(f"  UDP 대상:   {args.host}:{args.port}")
    print(f"  HTTP 서버:  {args.url}  (카메라/매핑 등록용)")
    print(f"  출력 경로:  {args.output_dir}")
    print(f"  배속:       {args.speed_factor}x  ({total_min:.0f}분 시나리오 → {total_real:.0f}초 = 약 {total_real/60:.1f}분)")
    print(f"  시드:       {args.seed}")
    print(f"  셀:         LTE Band3 {NUM_LTE_CELLS}개 + NR Band78 {NUM_NR_CELLS}개 = {NUM_LTE_CELLS+NUM_NR_CELLS}개")
    print(f"  단말:       LTE_ONLY {NUM_LTE_ONLY} + NR_SA {NUM_NR_SA} + NSA {NUM_NSA} = {NUM_LTE_ONLY+NUM_NR_SA+NUM_NSA}개")
    print()
    print(f"  [시나리오]")
    print(f"  Phase 1 (0~{PHASE1_END_MIN:.0f}분): 정상 - 단말 균등 분산")
    print(f"  Phase 2 ({PHASE1_END_MIN:.0f}~{PHASE2_END_MIN:.0f}분): 과부하 - 특정 NR 셀에 {OVERLOAD_DEVICE_COUNT_MIN}~{OVERLOAD_DEVICE_COUNT_MAX}개 단말 집중")
    print(f"  Phase 3 ({PHASE2_END_MIN:.0f}~{PHASE3_END_MIN:.0f}분): 복구 - 집중 단말 즉시 분산 → 셀 NORMAL → 화질 DEGRADED→STEP_UP→NORMAL")

    # 객체 생성 및 실행
    cell_reg   = CellRegistry()
    cells      = cell_reg.build()
    dev_reg    = DeviceRegistry(cells, seed=args.seed)
    dev_reg.build()
    traffic    = TrafficModel(seed=args.seed)
    scenario   = ScenarioController(dev_reg, cell_reg, speed_factor=args.speed_factor)
    output     = OutputManager(args.mode, args.host, args.port, args.output_dir)
    sim        = Simulator(dev_reg, traffic, scenario, output, verbose=args.verbose)

    # ONVIF 검증용 카메라 자동 등록 (realtime 모드)
    if args.mode == "realtime":
        _setup_cameras(args.url, dev_reg)

    sim.run()


def _setup_cameras(url: str, dev_reg: DeviceRegistry) -> None:
    """NSA/NR_SA 단말 앞 5개에 가상 카메라를 등록하고 매핑한다."""
    base = url.rstrip('/')
    candidates = [d for d in dev_reg.devices if d.device_type in ("NSA", "NR_SA")][:5]

    registered = 0
    mapped = 0
    for i, dev in enumerate(candidates):
        cam_id = f"SIM-CAM-{i+1:03d}"
        ctn = dev.ctn_str

        # 카메라 등록
        cam_body = {
            "cameraId": cam_id,
            "ipAddress": f"192.168.1.{10 + i}",
            "onvifPort": 80,
            "username": "admin",
            "password": "sim1234",
            "profileToken": "Profile_1",
        }
        try:
            if _USE_REQUESTS:
                r = _requests.post(f"{base}/api/cameras", json=cam_body, timeout=3)
                if r.status_code in (200, 201, 409):
                    registered += 1
            else:
                import json as _json
                req = _urllib_req.Request(
                    f"{base}/api/cameras",
                    data=_json.dumps(cam_body).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                try:
                    _urllib_req.urlopen(req, timeout=3)
                    registered += 1
                except _urllib_err.HTTPError as e:
                    if e.code == 409:
                        registered += 1  # already exists
        except Exception as e:
            print(f"  [카메라 등록 실패] {cam_id}: {e}")
            continue

        # 단말-카메라 매핑
        map_body = {"routerCtn": ctn, "cameraId": cam_id}
        try:
            if _USE_REQUESTS:
                r = _requests.post(f"{base}/api/mappings", json=map_body, timeout=3)
                if r.status_code in (200, 201, 409):
                    mapped += 1
            else:
                req = _urllib_req.Request(
                    f"{base}/api/mappings",
                    data=_json.dumps(map_body).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                try:
                    _urllib_req.urlopen(req, timeout=3)
                    mapped += 1
                except _urllib_err.HTTPError as e:
                    if e.code == 409:
                        mapped += 1
        except Exception as e:
            print(f"  [매핑 실패] {ctn} -> {cam_id}: {e}")

    print(f"\n[ONVIF 검증] 카메라 {registered}개 등록, 매핑 {mapped}개 완료")
    print(f"  대상 단말: {[d.ctn_str for d in candidates]}")
    print(f"  카메라 관리 탭에서 ONVIF 커맨드 이력을 확인하세요.\n")


if __name__ == "__main__":
    main()
