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

SAMPLE_CONFIG = """
thresholds:
  - band: 3
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

    def get_video_encoder_configuration(self, ip, port, username, password, profile_token):
        return {"bitrate": 4096000, "framerate": 30, "resolution": (1920, 1080)}

    def set_video_encoder_configuration(self, ip, port, username, password, profile_token, bitrate, framerate, resolution):
        self.calls.append({"ip": ip, "bitrate": bitrate, "framerate": framerate})
        return True


def _make_raw_packet(ctn: str = TEST_CTN, ul_rb_usage: int = 50, arfcn: int = 1850) -> bytes:
    ctn_raw = ctn.encode("ascii").ljust(15, b"\x00")
    ecgi_low = struct.pack(">I", 12345)
    primary = struct.pack(">B3sB4sIQH", 0x01, b"\x00\x10\x00", 0, ecgi_low, arfcn, 1700000000, ul_rb_usage)
    secondary = struct.pack(">B3sB4sIQH", 0x00, b"\x00\x00\x00", 0, b"\x00" * 4, 0, 0, 0)
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

        def set_video_encoder_configuration(self, ip, port, username, password, profile_token, bitrate, framerate, resolution):
            self.calls += 1
            if self.calls <= self.fail_count:
                return False
            return True

    failing = FailingONVIF(fail_count=2)
    cam_reg = CameraRegistry()
    cam_reg.register("cam-001", "192.168.1.1", 80, "admin", "pass", "profile1")
    mapping = DeviceCameraMapping()
    mapping.add_mapping("ctn1", "cam-001", 0.0)

    class MockGet:
        def get_video_encoder_configuration(self, ip, port, username, password, profile_token):
            return {"bitrate": 4096000, "framerate": 30, "resolution": (1920, 1080)}

        def set_video_encoder_configuration(self, *args, **kwargs):
            return failing.set_video_encoder_configuration(*args, **kwargs)

    qc = QualityController(MockGet(), cam_reg, mapping, degraded_ratio=0.25, step_up_ratio=0.50, max_retries=3)
    qc._default_configs["cam-001"] = {"bitrate": 4096000, "framerate": 30, "resolution": (1920, 1080)}
    qc._client = failing
    results = qc.apply_profile("ctn1", QualityProfile.DEGRADED)
    assert results[0].success
    assert failing.calls == 3  # failed twice, succeeded on 3rd
