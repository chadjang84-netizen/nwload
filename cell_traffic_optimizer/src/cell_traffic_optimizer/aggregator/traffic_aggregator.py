from collections import defaultdict
from ..models import RawEvent, GroupingKey, GroupStats


class TrafficAggregator:

    def __init__(self, window_seconds: int = 300):
        self._window_seconds = window_seconds
        self._events: list = []  # list of RawEvent
        # 각 grouping_key의 마지막 윈도우 판정 시각 (monotonic)
        self._last_evaluated: dict = {}  # GroupingKey -> float

    def add_event(self, event: RawEvent) -> None:
        self._events.append(event)
        self._evict_expired(event.timestamp)
        # 새 키는 첫 이벤트 수신 시각을 기준으로 등록
        if event.grouping_key not in self._last_evaluated:
            self._last_evaluated[event.grouping_key] = event.timestamp

    def get_group_stats(self, grouping_key: GroupingKey) -> GroupStats:
        ul_rb_sum = 0
        ctn_set = set()
        count = 0
        for e in self._events:
            if e.grouping_key == grouping_key:
                ul_rb_sum += e.ul_rb_usage
                ctn_set.add(e.router_ctn)
                count += 1
        return GroupStats(
            grouping_key=grouping_key,
            ul_rb_sum=ul_rb_sum,
            ctn_set=ctn_set,
            event_count=count,
        )

    def active_keys(self) -> set:
        """현재 윈도우 내에 이벤트가 있는 grouping_key 집합을 반환한다."""
        return {e.grouping_key for e in self._events}

    def pop_expired_windows(self, now: float) -> dict:
        """윈도우 만료 시각이 된 키의 확정 GroupStats를 반환하고 타이머를 갱신한다.

        반환된 키에 대해서만 evaluator를 호출해야 한다.
        """
        expired = {}
        for key, last in list(self._last_evaluated.items()):
            if now - last >= self._window_seconds:
                stats = self.get_group_stats(key)
                expired[key] = stats
                self._last_evaluated[key] = now  # 다음 윈도우 시작
        return expired

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self._window_seconds
        self._events = [e for e in self._events if e.timestamp > cutoff]
