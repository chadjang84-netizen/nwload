import pytest
from cell_traffic_optimizer.aggregator import TrafficAggregator
from cell_traffic_optimizer.models import RawEvent, GroupingKey

KEY_A = GroupingKey(ecgi=1000, band=3)
KEY_B = GroupingKey(ecgi=2000, band=7)


def _event(ctn: str, key: GroupingKey, usage: int, ts: float) -> RawEvent:
    return RawEvent(router_ctn=ctn, grouping_key=key, ul_rb_usage=usage, timestamp=ts)


def test_add_event_accumulates():
    agg = TrafficAggregator(window_seconds=300)
    agg.add_event(_event("ctn1", KEY_A, 100, 1000.0))
    stats = agg.get_group_stats(KEY_A)
    assert stats.ul_rb_sum == 100


def test_multiple_events_same_group_sum():
    agg = TrafficAggregator(window_seconds=300)
    agg.add_event(_event("ctn1", KEY_A, 100, 1000.0))
    agg.add_event(_event("ctn2", KEY_A, 200, 1001.0))
    agg.add_event(_event("ctn3", KEY_A, 50, 1002.0))
    stats = agg.get_group_stats(KEY_A)
    assert stats.ul_rb_sum == 350
    assert stats.event_count == 3


def test_ctn_set_tracking():
    agg = TrafficAggregator(window_seconds=300)
    agg.add_event(_event("ctn1", KEY_A, 100, 1000.0))
    agg.add_event(_event("ctn2", KEY_A, 100, 1001.0))
    stats = agg.get_group_stats(KEY_A)
    assert stats.ctn_set == {"ctn1", "ctn2"}


def test_expired_events_evicted():
    agg = TrafficAggregator(window_seconds=300)
    agg.add_event(_event("ctn1", KEY_A, 999, 0.0))        # ts=0, expires at t=300
    agg.add_event(_event("ctn2", KEY_A, 50, 301.0))       # now=301, cutoff=1 → ts=0 evicted
    stats = agg.get_group_stats(KEY_A)
    assert stats.ul_rb_sum == 50
    assert stats.event_count == 1


def test_empty_group_stats():
    agg = TrafficAggregator(window_seconds=300)
    stats = agg.get_group_stats(KEY_A)
    assert stats.ul_rb_sum == 0
    assert stats.event_count == 0
    assert stats.ctn_set == set()


def test_multiple_groups_independent():
    agg = TrafficAggregator(window_seconds=300)
    agg.add_event(_event("ctn1", KEY_A, 100, 1000.0))
    agg.add_event(_event("ctn2", KEY_B, 200, 1000.0))
    assert agg.get_group_stats(KEY_A).ul_rb_sum == 100
    assert agg.get_group_stats(KEY_B).ul_rb_sum == 200


def test_window_boundary_exact():
    agg = TrafficAggregator(window_seconds=300)
    agg.add_event(_event("ctn1", KEY_A, 100, 0.0))    # ts=0, evicted when now=300
    agg.add_event(_event("ctn2", KEY_A, 50, 300.0))   # now=300, cutoff=0, ts=0 is NOT > cutoff
    stats = agg.get_group_stats(KEY_A)
    assert stats.ul_rb_sum == 50


def test_pop_expired_windows_fires_after_window():
    agg = TrafficAggregator(window_seconds=60)
    agg.add_event(_event("ctn1", KEY_A, 100, 0.0))
    # 평가 시점에 윈도우 안에 있는 이벤트 합이 들어가도록 30초 시점에 한 번 더 적재
    agg.add_event(_event("ctn1", KEY_A, 100, 30.0))
    # 60초 미만 — 아직 만료 아님
    assert agg.pop_expired_windows(59.0) == {}
    # 60초 경과 — 만료. t=0 이벤트는 cutoff=0에서 제거, t=30만 남음
    expired = agg.pop_expired_windows(60.0)
    assert KEY_A in expired
    assert expired[KEY_A].ul_rb_sum == 100


def test_pop_expired_windows_drops_key_when_silent():
    # 마지막 패킷 이후 윈도우 동안 추가 패킷이 없으면 키가 _last_evaluated에서 제거된다
    agg = TrafficAggregator(window_seconds=60)
    agg.add_event(_event("ctn1", KEY_A, 100, 0.0))
    expired = agg.pop_expired_windows(60.0)
    # 한 번 만료 통지는 하지만 (셀 상태 정리용)
    assert KEY_A in expired
    # 두 번째 호출에는 더 이상 잡히지 않는다
    assert agg.pop_expired_windows(120.0) == {}


def test_pop_expired_windows_resets_timer():
    agg = TrafficAggregator(window_seconds=60)
    agg.add_event(_event("ctn1", KEY_A, 100, 0.0))
    agg.add_event(_event("ctn1", KEY_A, 100, 30.0))
    agg.pop_expired_windows(60.0)
    # 타이머 리셋 후 즉시 다시 호출하면 빈 결과
    assert agg.pop_expired_windows(60.0) == {}


def test_pop_expired_windows_evicts_stale_when_no_new_packets():
    # 사용자 시나리오: 마지막 패킷이 임계치 초과 → 이후 무패킷
    # 기존 버그: 300초마다 같은 값을 계속 평가해 WARNING→CONGESTION→OVERLOAD로 천이
    # 수정 후: 윈도우 만료 시점에 이벤트가 제거되어 ul_rb_sum=0으로 평가됨
    agg = TrafficAggregator(window_seconds=60)
    agg.add_event(_event("ctn1", KEY_A, 9999, 0.0))
    expired = agg.pop_expired_windows(60.0)
    assert KEY_A in expired
    assert expired[KEY_A].ul_rb_sum == 0  # t=0 이벤트는 cutoff=0에서 만료됨
