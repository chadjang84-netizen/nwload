from typing import Callable
from ..models import ParsedPacket, RawEvent, GroupingKey, RATType, RATBlock


class EventConverter:

    def __init__(self, arfcn_to_band: Callable[[int, RATType], int]):
        self._arfcn_to_band = arfcn_to_band

    def convert(self, packet: ParsedPacket, received_at: float) -> list:
        events = []
        events.append(self._block_to_event(packet.router_ctn, packet.primary, received_at))
        if packet.secondary is not None and packet.secondary.rat_type != RATType.NONE:
            events.append(self._block_to_event(packet.router_ctn, packet.secondary, received_at))
        return events

    def _block_to_event(self, router_ctn: str, block: RATBlock, received_at: float) -> RawEvent:
        band = self._arfcn_to_band(block.arfcn, block.rat_type)
        return RawEvent(
            router_ctn=router_ctn,
            grouping_key=GroupingKey(ecgi=block.ecgi, band=band),
            ul_rb_usage=block.ul_rb_usage,
            timestamp=received_at,
        )
