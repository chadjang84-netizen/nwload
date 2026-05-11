import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from ..parser import PacketParser, PacketValidationError, EventConverter
from ..aggregator import TrafficAggregator
from ..evaluator import CellLoadEvaluator
from ..state_machine import CellStateMachine, DeviceStateMachine
from ..controller import QualityController
from ..data import DeviceRegistry
from ..models import CellState, DeviceState, GroupingKey

logger = logging.getLogger(__name__)


@dataclass
class StageTimings:
    parse_ms: float = 0.0
    aggregate_ms: float = 0.0
    evaluate_ms: float = 0.0
    cell_transition_ms: float = 0.0
    device_transition_ms: float = 0.0
    quality_control_ms: float = 0.0


@dataclass
class PipelineResult:
    success: bool
    packet_timestamp: float
    router_ctn: Optional[str] = None
    events_generated: int = 0
    cell_transitions: list = field(default_factory=list)
    device_actions: list = field(default_factory=list)
    quality_commands: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    timings: StageTimings = field(default_factory=StageTimings)
    affected_keys: list = field(default_factory=list)


def _ms(start: float) -> float:
    return (time.monotonic() - start) * 1000


class DataPipeline:

    def __init__(
        self,
        parser: PacketParser,
        event_converter: EventConverter,
        aggregator: TrafficAggregator,
        evaluator: CellLoadEvaluator,
        cell_sm: CellStateMachine,
        device_sm: DeviceStateMachine,
        quality_ctrl: QualityController,
        device_registry: DeviceRegistry,
    ):
        self._parser = parser
        self._converter = event_converter
        self._aggregator = aggregator
        self._evaluator = evaluator
        self._cell_sm = cell_sm
        self._device_sm = device_sm
        self._quality_ctrl = quality_ctrl
        self._device_registry = device_registry

    def process_packet(self, data: bytes, timestamp: float) -> PipelineResult:
        result = PipelineResult(success=False, packet_timestamp=timestamp)

        # 1. Parse
        t0 = time.monotonic()
        try:
            packet = self._parser.parse(data)
        except PacketValidationError as e:
            result.errors.append(f"Parse error: {e}")
            logger.error("Packet parse error: %s", e)
            return result
        result.timings.parse_ms = _ms(t0)
        result.router_ctn = packet.router_ctn

        # 2. Register/update device
        self._device_registry.register_or_update(packet.router_ctn, timestamp)

        # 3. Convert to RawEvents
        events = self._converter.convert(packet, timestamp)
        result.events_generated = len(events)

        # 4. Aggregate — 이벤트를 윈도우에 누적만 하고 판정은 하지 않는다
        t0 = time.monotonic()
        affected_keys = {e.grouping_key for e in events}
        result.affected_keys = list(affected_keys)
        for event in events:
            self._aggregator.add_event(event)

        # ctn_map 및 ul_rb 업데이트 (대시보드 실시간 표시용)
        for key in affected_keys:
            self._cell_sm.ensure_registered(key)
            stats = self._aggregator.get_group_stats(key)
            self._cell_sm.update_ctns(key, stats.ctn_set)
            self._cell_sm.update_ul_rb(key, stats.ul_rb_sum)
        result.timings.aggregate_ms = _ms(t0)

        result.success = True
        return result

    def _handle_cell_transition(self, key: GroupingKey, new_state: CellState, timestamp: float, result: PipelineResult) -> None:
        t0 = time.monotonic()
        transition = self._cell_sm.transition(key, new_state, timestamp)
        result.timings.cell_transition_ms += _ms(t0)

        if not transition.success:
            return

        result.cell_transitions.append(transition)
        logger.info("Cell %s -> %s for %s", transition.previous_state, new_state, key)

        t0 = time.monotonic()
        if new_state == CellState.WARNING:
            current_ctns = list(self._cell_sm._ctn_map.get(key, set()))
            for ctn in current_ctns:
                self._quality_ctrl.prefetch_camera_defaults(ctn)

        elif new_state == CellState.OVERLOAD:
            current_ctns = list(self._cell_sm._ctn_map.get(key, set()))
            for ctn in current_ctns:
                if self._device_sm._get_state(ctn) == DeviceState.NORMAL:
                    if self._quality_ctrl.is_mapped(ctn):
                        action = self._device_sm.degrade(ctn, timestamp)
                        result.device_actions.append(action)
                        if action.success:
                            cmds = self._quality_ctrl.apply_profile(ctn, action.new_profile)
                            result.quality_commands.extend(cmds)
                    else:
                        action = self._device_sm.mark_unmanaged(ctn, timestamp)
                        result.device_actions.append(action)

        if new_state == CellState.NORMAL:
            current_ctns = list(self._cell_sm._ctn_map.get(key, set()))
            for ctn in current_ctns:
                state = self._device_sm._get_state(ctn)
                if state == DeviceState.DEGRADED:
                    action = self._device_sm.start_recovery(ctn, timestamp)
                    result.device_actions.append(action)
                elif state == DeviceState.UNMANAGED:
                    action = self._device_sm.clear_unmanaged(ctn, timestamp)
                    result.device_actions.append(action)

        result.timings.device_transition_ms += _ms(t0)

    def check_window_expiry(self, now: float) -> PipelineResult:
        """윈도우 만료 시점마다 호출 — ul_rb_sum 합계로 셀 상태를 판정한다."""
        result = PipelineResult(success=True, packet_timestamp=now)
        expired = self._aggregator.pop_expired_windows(now)
        for key, stats in expired.items():
            self._cell_sm.ensure_registered(key)
            self._cell_sm.update_ctns(key, stats.ctn_set)
            self._cell_sm.update_ul_rb(key, stats.ul_rb_sum)
            current_state = self._cell_sm.get_state(key)
            new_state = self._evaluator.evaluate(key, stats.ul_rb_sum, current_state)
            if new_state != current_state:
                self._handle_cell_transition(key, new_state, now, result)

        # 윈도우에 이벤트가 없는 셀은 NORMAL로 복귀 처리
        active_keys = self._aggregator.active_keys()
        for key in list(self._cell_sm._states.keys()):
            if key not in active_keys:
                self._cell_sm.expire(key)

        return result

    def check_recovery_timers(self, now: float) -> list:
        actions = []
        for ctn, history in list(self._device_sm._histories.items()):
            if self._device_sm._get_state(ctn) != DeviceState.RECOVERY_PENDING:
                continue
            if not self._device_sm.is_cooldown_expired(ctn, now):
                continue

            # Determine which cell this device belongs to (find its grouping key)
            cell_is_normal = self._is_device_cell_normal(ctn)

            if cell_is_normal:
                action = self._device_sm.step_up(ctn, now)
                actions.append(action)
                if action.success:
                    cmds = self._quality_ctrl.apply_profile(ctn, action.new_profile)
                    logger.info("Step-up applied for %s -> %s (%d camera commands)", ctn, action.new_profile, len(cmds))
            else:
                action = self._device_sm.cancel_recovery(ctn, now)
                actions.append(action)

        return actions

    def _is_device_cell_normal(self, ctn: str) -> bool:
        # Check all known grouping keys for cells that contain this ctn
        for key, ctn_set in self._cell_sm._ctn_map.items():
            if ctn in ctn_set:
                return self._cell_sm.get_state(key) == CellState.NORMAL
        # If no cell record found, assume normal
        return True
