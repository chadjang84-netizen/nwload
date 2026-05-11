import json
import logging
import os
from typing import Optional
from ..models import DeviceHistory, CellStabilityRecord, DeviceState, DeviceAction, QualityProfile, CellState, GroupingKey

logger = logging.getLogger(__name__)


class HistoryStore:

    def __init__(self):
        self._device_histories: dict = {}
        self._cell_records: dict = {}

    # ── DeviceHistory ───────────────────────────────────────────────────────

    def set_device_history(self, history: DeviceHistory) -> None:
        self._device_histories[history.router_ctn] = history

    def get_device_history(self, router_ctn: str) -> Optional[DeviceHistory]:
        return self._device_histories.get(router_ctn)

    def all_device_histories(self) -> list:
        return list(self._device_histories.values())

    # ── CellStabilityRecord ─────────────────────────────────────────────────

    def set_cell_record(self, record: CellStabilityRecord) -> None:
        self._cell_records[record.grouping_key] = record

    def get_cell_record(self, grouping_key: GroupingKey) -> Optional[CellStabilityRecord]:
        return self._cell_records.get(grouping_key)

    def update_normal_duration(self, grouping_key: GroupingKey, now: float) -> None:
        record = self._cell_records.get(grouping_key)
        if record and record.current_state == CellState.NORMAL:
            record.normal_duration_seconds = now - record.state_entered_at

    def all_cell_records(self) -> list:
        return list(self._cell_records.values())

    # ── Persistence ─────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        data = {
            "device_histories": [
                {
                    "router_ctn": h.router_ctn,
                    "current_state": h.current_state.value,
                    "last_action": h.last_action.value if h.last_action else None,
                    "last_action_time": h.last_action_time,
                    "cooldown_start_time": h.cooldown_start_time,
                    "current_profile": h.current_profile.value,
                }
                for h in self._device_histories.values()
            ],
            "cell_records": [
                {
                    "ecgi": r.grouping_key.ecgi,
                    "band": r.grouping_key.band,
                    "current_state": r.current_state.value,
                    "state_entered_at": r.state_entered_at,
                    "normal_duration_seconds": r.normal_duration_seconds,
                }
                for r in self._cell_records.values()
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("HistoryStore saved to %s", path)

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            logger.info("No history file at %s, starting fresh", path)
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("device_histories", []):
            self._device_histories[item["router_ctn"]] = DeviceHistory(
                router_ctn=item["router_ctn"],
                current_state=DeviceState(item["current_state"]),
                last_action=DeviceAction(item["last_action"]) if item["last_action"] else None,
                last_action_time=item["last_action_time"],
                cooldown_start_time=item["cooldown_start_time"],
                current_profile=QualityProfile(item["current_profile"]),
            )

        for item in data.get("cell_records", []):
            key = GroupingKey(ecgi=item["ecgi"], band=item["band"])
            self._cell_records[key] = CellStabilityRecord(
                grouping_key=key,
                current_state=CellState(item["current_state"]),
                state_entered_at=item["state_entered_at"],
                normal_duration_seconds=item["normal_duration_seconds"],
            )
        logger.info("HistoryStore loaded from %s", path)
