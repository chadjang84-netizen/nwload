"""통합 테스트: 전체 파이프라인 End-to-End"""
import struct
import pytest
from cell_traffic_optimizer.config import ConfigParser
from cell_traffic_optimizer.aggregator import BandMapper, TrafficAggregator
from cell_traffic_optimizer.evaluator import CellLoadEvaluator
from cell_traffic_optimizer.state_machine import CellStateMachine, DeviceStateMachine
from cell_traffic_optimizer.controller import QualityController
from cell_traffic_optimizer.data import DeviceRegistry, CameraRegistry, DeviceCameraMapping
from cell_traffic_optimizer.parser import PacketParser, EventConverter
from cell_traffic_optimizer.pipeline import DataPipeline
from cell_traffic_optimizer.models import QualityProfile, CellState, DeviceState

# 10자 CTN — 15바이트 필드에 안전하게 들어감
TEST_CTN = "0101234567"

# NSA 테스트용 셀 식별자 — LTE/NR은 서로 다른 ECGI·Band로 별도 집계된다
LTE_ECGI = 12345
LTE_ARFCN = 1850     # → LTE Band 3
NR_ECGI = 54321
NR_ARFCN = 640000    # → NR Band 78

SAMPLE_CONFIG = """
thresholds:
  - band: 3
    warning: 100
    congestion: 200
    overload_enter: 300
    overload_exit: 250
  - band: 78
    warning: 100
    congestion: 200
    overload_enter: 300
    overload_exit: 250

degraded_ratio: 0.25
step_up_ratio: 0.50

sliding_window_seconds: 300
recovery_cooldown_seconds: 60
step_up_interval_seconds: 60
supported_version: 1
supported_message_type: 1
max_onvif_retries: 3
"""


class MockONVIFClient:
    def __init__(self):
        self.calls = []

    def get_video_encoder_configuration(self, ip, port, username, password, profile_token, **kwargs):
        return {"bitrate": 4096000, "framerate": 30, "resolution": (1920, 1080)}

    def get_video_encoder_configurations(self, ip, port, username, password, **kwargs):
        return ["profile1"]

    def resolve_token(self, ip, port, username, password, profile_token, **kwargs):
        return profile_token or "profile1"

    def set_video_encoder_configuration(self, ip, port, username, password, profile_token, bitrate, framerate, resolution, **kwargs):
        self.calls.append({"ip": ip, "bitrate": bitrate, "framerate": framerate})
        return True


def _make_raw_packet(ctn: str = TEST_CTN, ul_rb_usage: int = 50, arfcn: int = 1850) -> bytes:
    ctn_raw = ctn.encode("ascii").ljust(15, b"\x00")
    ecgi_low = struct.pack(">I", 12345)
    primary = struct.pack(">B3sB4sIQH", 0x01, b"\x00\x10\x00", 0, ecgi_low, arfcn, 1700000000, ul_rb_usage)
    secondary = struct.pack(">B3sB4sIQH", 0x00, b"\x00\x00\x00", 0, b"\x00" * 4, 0, 0, 0)
    header = struct.pack(">BBH15s", 0x01, 0x01, 67, ctn_raw)
    return header + primary + secondary + b"\x00\x00"


def _make_nsa_packet(ctn: str = TEST_CTN, lte_rb: int = 50, nr_rb: int = 50) -> bytes:
    """NSA 단말 패킷 — Primary=LTE, Secondary=NR (서로 다른 ECGI/Band)."""
    ctn_raw = ctn.encode("ascii").ljust(15, b"\x00")
    primary = struct.pack(
        ">B3sB4sIQH", 0x01, b"\x00\x10\x00", 0,
        struct.pack(">I", LTE_ECGI), LTE_ARFCN, 1700000000, lte_rb,
    )
    secondary = struct.pack(
        ">B3sB4sIQH", 0x02, b"\x00\x10\x00", 0,
        struct.pack(">I", NR_ECGI), NR_ARFCN, 1700000000, nr_rb,
    )
    header = struct.pack(">BBH15s", 0x01, 0x01, 67, ctn_raw)
    return header + primary + secondary + b"\x00\x00"


def _build_pipeline(onvif_mock):
    config = ConfigParser.parse(SAMPLE_CONFIG)

    camera_reg = CameraRegistry()
    camera_reg.register("cam-001", "192.168.1.10", 80, "admin", "pass123", "profile1")

    mapping = DeviceCameraMapping()
    mapping.add_mapping(TEST_CTN, "cam-001", 0.0)

    pipeline = DataPipeline(
        parser=PacketParser(),
        event_converter=EventConverter(BandMapper.arfcn_to_band),
        aggregator=TrafficAggregator(window_seconds=config.sliding_window_seconds),
        evaluator=CellLoadEvaluator(config.thresholds),
        cell_sm=CellStateMachine(),
        device_sm=DeviceStateMachine(recovery_cooldown_seconds=config.recovery_cooldown_seconds),
        quality_ctrl=QualityController(
            onvif_client=onvif_mock,
            camera_registry=camera_reg,
            device_camera_mapping=mapping,
            degraded_ratio=config.degraded_ratio,
            step_up_ratio=config.step_up_ratio,
            max_retries=config.max_onvif_retries,
        ),
        device_registry=DeviceRegistry(),
    )
    return pipeline


def test_config_parse_roundtrip():
    from cell_traffic_optimizer.config import ConfigPrinter
    config = ConfigParser.parse(SAMPLE_CONFIG)
    printed = ConfigPrinter.print(config)
    config2 = ConfigParser.parse(printed)
    assert config.thresholds == config2.thresholds
    assert config.sliding_window_seconds == config2.sliding_window_seconds
    assert config.recovery_cooldown_seconds == config2.recovery_cooldown_seconds


def test_config_invalid_yaml():
    from cell_traffic_optimizer.config import ConfigValidationError
    with pytest.raises(ConfigValidationError):
        ConfigParser.parse(": invalid: yaml: :")


def test_pipeline_valid_packet_normal():
    mock = MockONVIFClient()
    pipeline = _build_pipeline(mock)
    data = _make_raw_packet(ul_rb_usage=50)
    result = pipeline.process_packet(data, 1000.0)
    assert result.success
    assert result.router_ctn == TEST_CTN
    assert result.events_generated == 1
    assert len(result.cell_transitions) == 0  # 윈도우 만료 전이므로 판정 없음


def test_pipeline_overload_triggers_degrade():
    mock = MockONVIFClient()
    pipeline = _build_pipeline(mock)
    T = 1000.0

    # 윈도우(300s) 동안 패킷을 누적해서 ul_rb_sum이 각 임계값을 초과하도록 설정
    # 패킷 1개로 각 임계값(100, 200, 300)을 넘기기 위해 큰 값 사용
    pipeline.process_packet(_make_raw_packet(ul_rb_usage=101), T)
    window_result = pipeline.check_window_expiry(T + 300)   # WARNING
    assert any(t.new_state == CellState.WARNING for t in window_result.cell_transitions)

    pipeline.process_packet(_make_raw_packet(ul_rb_usage=201), T + 300)
    window_result = pipeline.check_window_expiry(T + 600)   # CONGESTION
    assert any(t.new_state == CellState.CONGESTION for t in window_result.cell_transitions)

    pipeline.process_packet(_make_raw_packet(ul_rb_usage=301), T + 600)
    window_result = pipeline.check_window_expiry(T + 900)   # OVERLOAD
    assert any(t.new_state == CellState.OVERLOAD for t in window_result.cell_transitions)
    assert len(window_result.device_actions) > 0
    assert window_result.device_actions[0].new_state == DeviceState.DEGRADED
    assert len(mock.calls) > 0  # ONVIF command sent


def test_pipeline_parse_error_does_not_crash():
    mock = MockONVIFClient()
    pipeline = _build_pipeline(mock)
    result = pipeline.process_packet(b"\x00" * 10, 1000.0)  # too short
    assert not result.success
    assert len(result.errors) > 0


def test_pipeline_recovery_timer():
    mock = MockONVIFClient()
    pipeline = _build_pipeline(mock)
    T = 1000.0

    # Phase 1: 패킷 누적 후 윈도우 만료로 OVERLOAD 진입
    pipeline.process_packet(_make_raw_packet(ul_rb_usage=101), T)
    pipeline.check_window_expiry(T + 300)       # WARNING

    pipeline.process_packet(_make_raw_packet(ul_rb_usage=201), T + 300)
    pipeline.check_window_expiry(T + 600)       # CONGESTION

    pipeline.process_packet(_make_raw_packet(ul_rb_usage=301), T + 600)
    pipeline.check_window_expiry(T + 900)       # OVERLOAD → device DEGRADED

    assert pipeline._device_sm._get_state(TEST_CTN) == DeviceState.DEGRADED

    # Phase 2: 낮은 패킷 전송 후 윈도우 만료로 NORMAL 복귀
    pipeline.process_packet(_make_raw_packet(ul_rb_usage=10), T + 900)
    pipeline.check_window_expiry(T + 1200)      # NORMAL → device RECOVERY_PENDING

    assert pipeline._device_sm._get_state(TEST_CTN) == DeviceState.RECOVERY_PENDING

    # Phase 3: 쿨다운(60s) 만료 후 step_up
    actions = pipeline.check_recovery_timers(T + 1200 + 61)
    assert len(actions) > 0
    assert actions[0].success


# ── NSA 단말: 발동은 OR, 복구는 AND ────────────────────────────────────────────

@pytest.mark.parametrize("insert_nr_first", [False, True])
def test_is_device_cell_normal_requires_all_serving_cells(insert_nr_first):
    """소속 셀 중 하나라도 부하면 복구 불가 — _ctn_map 등록 순서와 무관해야 한다."""
    from cell_traffic_optimizer.models import GroupingKey

    pipeline = _build_pipeline(MockONVIFClient())
    lte_key = GroupingKey(ecgi=LTE_ECGI, band=3)
    nr_key = GroupingKey(ecgi=NR_ECGI, band=78)

    for key in ([nr_key, lte_key] if insert_nr_first else [lte_key, nr_key]):
        pipeline._cell_sm.ensure_registered(key)
        pipeline._cell_sm.update_ctns(key, {TEST_CTN})

    assert pipeline._is_device_cell_normal(TEST_CTN)          # 둘 다 NORMAL

    pipeline._cell_sm._states[nr_key] = CellState.OVERLOAD
    assert not pipeline._is_device_cell_normal(TEST_CTN)      # NR만 부하

    pipeline._cell_sm._states[nr_key] = CellState.NORMAL
    pipeline._cell_sm._states[lte_key] = CellState.OVERLOAD
    assert not pipeline._is_device_cell_normal(TEST_CTN)      # LTE만 부하

    # 소속 셀 기록이 없으면(윈도우 만료) 부하 근거가 없으므로 NORMAL로 본다
    assert pipeline._is_device_cell_normal("0109999999")


def test_nsa_recovery_waits_for_both_rats():
    """NSA 단말은 LTE·NR 두 셀이 모두 NORMAL이 될 때까지 복구를 시작하지 않는다."""
    mock = MockONVIFClient()
    pipeline = _build_pipeline(mock)
    T = 1000.0

    # 프라이머 — 각 키의 윈도우 타이머를 등록한다(첫 이벤트는 첫 만료 시 evict됨)
    pipeline.process_packet(_make_nsa_packet(lte_rb=1, nr_rb=1), T)

    pipeline.process_packet(_make_nsa_packet(lte_rb=101, nr_rb=101), T + 100)
    pipeline.check_window_expiry(T + 300)     # 두 셀 WARNING

    pipeline.process_packet(_make_nsa_packet(lte_rb=201, nr_rb=201), T + 400)
    pipeline.check_window_expiry(T + 600)     # 두 셀 CONGESTION

    pipeline.process_packet(_make_nsa_packet(lte_rb=301, nr_rb=301), T + 700)
    pipeline.check_window_expiry(T + 900)     # 두 셀 OVERLOAD → 단말 DEGRADED
    assert pipeline._device_sm._get_state(TEST_CTN) == DeviceState.DEGRADED

    # LTE만 부하 해제 — NR은 여전히 OVERLOAD이므로 복구 금지
    pipeline.process_packet(_make_nsa_packet(lte_rb=10, nr_rb=301), T + 1000)
    result = pipeline.check_window_expiry(T + 1200)
    assert any(t.new_state == CellState.NORMAL for t in result.cell_transitions)
    assert pipeline._device_sm._get_state(TEST_CTN) == DeviceState.DEGRADED
    assert pipeline.check_orphan_degraded(T + 1200) == []     # 주기 점검도 풀어주지 않아야 함

    # NR까지 해제 — 이제 복구 진입
    pipeline.process_packet(_make_nsa_packet(lte_rb=10, nr_rb=10), T + 1300)
    pipeline.check_window_expiry(T + 1500)
    assert pipeline._device_sm._get_state(TEST_CTN) == DeviceState.RECOVERY_PENDING


def test_nsa_degrade_is_or_condition():
    """NR 셀만 부하 조건이어도(LTE는 NORMAL) 단말은 DEGRADED로 내려간다."""
    mock = MockONVIFClient()
    pipeline = _build_pipeline(mock)
    T = 1000.0

    pipeline.process_packet(_make_nsa_packet(lte_rb=1, nr_rb=1), T)

    # LTE는 계속 NORMAL 수준(10), NR만 임계값을 밟아 올라간다
    pipeline.process_packet(_make_nsa_packet(lte_rb=10, nr_rb=101), T + 100)
    pipeline.check_window_expiry(T + 300)

    pipeline.process_packet(_make_nsa_packet(lte_rb=10, nr_rb=201), T + 400)
    pipeline.check_window_expiry(T + 600)

    pipeline.process_packet(_make_nsa_packet(lte_rb=10, nr_rb=301), T + 700)
    result = pipeline.check_window_expiry(T + 900)

    from cell_traffic_optimizer.models import GroupingKey
    assert pipeline._cell_sm.get_state(GroupingKey(ecgi=LTE_ECGI, band=3)) == CellState.NORMAL
    assert pipeline._cell_sm.get_state(GroupingKey(ecgi=NR_ECGI, band=78)) == CellState.OVERLOAD
    assert pipeline._device_sm._get_state(TEST_CTN) == DeviceState.DEGRADED
    assert len(result.quality_commands) > 0


def test_data_layer_device_registry():
    reg = DeviceRegistry()
    entry = reg.register_or_update("ctn1", 1000.0)
    assert entry.is_registered
    entry2 = reg.register_or_update("ctn1", 2000.0)
    assert entry2.last_packet_time == 2000.0
    assert reg.is_registered("ctn1")
    assert not reg.is_registered("unknown")


def test_data_layer_camera_registry_encryption():
    cam_reg = CameraRegistry()
    cam_reg.register("cam-001", "192.168.1.1", 80, "admin", "secret123", "profile1")
    entry = cam_reg.get("cam-001")
    assert entry is not None
    assert entry.encrypted_password != b"secret123"  # encrypted
    assert cam_reg.get_password("cam-001") == "secret123"  # decrypts correctly


def test_data_layer_camera_mapping_1n():
    mapping = DeviceCameraMapping()
    mapping.add_mapping("ctn1", "cam-001", 0.0)
    mapping.add_mapping("ctn1", "cam-002", 0.0)
    ids = mapping.get_camera_ids("ctn1")
    assert set(ids) == {"cam-001", "cam-002"}
    assert mapping.get_camera_ids("unknown") == []


def test_quality_controller_retries():
    class FailingONVIF:
        def __init__(self, fail_count):
            self.calls = 0
            self.fail_count = fail_count

        def set_video_encoder_configuration(self, ip, port, username, password, profile_token, bitrate, framerate, resolution, **kwargs):
            self.calls += 1
            if self.calls <= self.fail_count:
                return False
            return True

        def resolve_token(self, ip, port, username, password, profile_token, **kwargs):
            return profile_token or "profile1"

        def get_video_encoder_configurations(self, ip, port, username, password, **kwargs):
            return ["profile1"]

    failing = FailingONVIF(fail_count=2)
    cam_reg = CameraRegistry()
    cam_reg.register("cam-001", "192.168.1.1", 80, "admin", "pass", "profile1")
    mapping = DeviceCameraMapping()
    mapping.add_mapping("ctn1", "cam-001", 0.0)

    class MockGet:
        def get_video_encoder_configuration(self, ip, port, username, password, profile_token, **kwargs):
            return {"bitrate": 4096000, "framerate": 30, "resolution": (1920, 1080)}

        def get_video_encoder_configurations(self, ip, port, username, password, **kwargs):
            return ["profile1"]

        def resolve_token(self, ip, port, username, password, profile_token, **kwargs):
            return profile_token or "profile1"

        def set_video_encoder_configuration(self, *args, **kwargs):
            return failing.set_video_encoder_configuration(*args, **kwargs)

    qc = QualityController(MockGet(), cam_reg, mapping, degraded_ratio=0.25, step_up_ratio=0.50, max_retries=3)
    qc._default_configs["cam-001"] = {"bitrate": 4096000, "framerate": 30, "resolution": (1920, 1080)}
    qc._client = failing
    results = qc.apply_profile("ctn1", QualityProfile.DEGRADED)
    assert results[0].success
    assert failing.calls == 3  # failed twice, succeeded on 3rd


# ── ONVIF 토큰 자동 발견 ───────────────────────────────────────────────────────

def test_all_config_tokens_attribute_extraction():
    from cell_traffic_optimizer.controller.onvif_client import _all_config_tokens

    # 쌍따옴표 + namespace prefix + 복수형
    xml_double = '<trt:Configurations token="VEC_1"><tt:Name>main</tt:Name></trt:Configurations>' \
                 '<trt:Configurations token="VEC_2"></trt:Configurations>'
    assert _all_config_tokens(xml_double) == ["VEC_1", "VEC_2"]

    # 단따옴표 + prefix 없음 + 단수형 fallback
    xml_single = "<Configuration token='ENC0'></Configuration>"
    assert _all_config_tokens(xml_single) == ["ENC0"]

    # config 없음 → 빈 리스트
    assert _all_config_tokens("<trt:GetVideoEncoderConfigurationsResponse/>") == []


def test_resolve_token_blank_autodetects():
    """profile_token이 비면 GetVideoEncoderConfigurations 첫 토큰을 자동 사용하고 캐시한다."""
    class DiscoverClient:
        def __init__(self):
            self.discover_calls = 0
            self.set_tokens = []

        def get_video_encoder_configurations(self, ip, port, username, password, **kwargs):
            self.discover_calls += 1
            return ["tokA", "tokB"]

        def resolve_token(self, ip, port, username, password, profile_token, **kwargs):
            if profile_token and profile_token.strip():
                return profile_token
            return self.get_video_encoder_configurations(ip, port, username, password, **kwargs)[0]

        def get_video_encoder_configuration(self, ip, port, username, password, profile_token, **kwargs):
            return {"bitrate": 4096000, "framerate": 30, "resolution": (1920, 1080)}

        def set_video_encoder_configuration(self, ip, port, username, password, profile_token, bitrate, framerate, resolution, **kwargs):
            self.set_tokens.append(profile_token)
            return True

    client = DiscoverClient()
    cam_reg = CameraRegistry()
    cam_reg.register("cam-001", "1.2.3.4", 80, "admin", "pass", "")  # blank token
    mapping = DeviceCameraMapping()
    mapping.add_mapping("ctn1", "cam-001", 0.0)

    qc = QualityController(client, cam_reg, mapping, degraded_ratio=0.25, step_up_ratio=0.50, max_retries=1)
    results = qc.apply_profile("ctn1", QualityProfile.DEGRADED)

    assert results[0].success
    assert client.set_tokens == ["tokA"]          # 자동 발견된 첫 토큰으로 SET
    assert qc._resolved_tokens["cam-001"] == "tokA"  # 캐시됨
    assert client.discover_calls == 1             # GET 캐싱+SET이 토큰을 공유 → 발견 1회


def test_resolve_token_provided_passthrough():
    """profile_token이 주어지면 발견 호출 없이 그대로 사용한다(하위 호환)."""
    class NoDiscoverClient:
        def __init__(self):
            self.set_tokens = []

        def get_video_encoder_configurations(self, ip, port, username, password, **kwargs):
            raise AssertionError("discovery should not be called when token is provided")

        def resolve_token(self, ip, port, username, password, profile_token, **kwargs):
            if profile_token and profile_token.strip():
                return profile_token
            return self.get_video_encoder_configurations(ip, port, username, password, **kwargs)[0]

        def get_video_encoder_configuration(self, ip, port, username, password, profile_token, **kwargs):
            return {"bitrate": 4096000, "framerate": 30, "resolution": (1920, 1080)}

        def set_video_encoder_configuration(self, ip, port, username, password, profile_token, bitrate, framerate, resolution, **kwargs):
            self.set_tokens.append(profile_token)
            return True

    client = NoDiscoverClient()
    cam_reg = CameraRegistry()
    cam_reg.register("cam-001", "1.2.3.4", 80, "admin", "pass", "MyToken")
    mapping = DeviceCameraMapping()
    mapping.add_mapping("ctn1", "cam-001", 0.0)

    qc = QualityController(client, cam_reg, mapping, degraded_ratio=0.25, step_up_ratio=0.50, max_retries=1)
    results = qc.apply_profile("ctn1", QualityProfile.DEGRADED)

    assert results[0].success
    assert client.set_tokens == ["MyToken"]
