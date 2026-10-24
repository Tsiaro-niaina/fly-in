"""Remembers which zones and connections are taken at each turn."""

from models import Connection, Position, Zone


class ReservationTable:
    """Occupancy of zones and connections, turn by turn.

    A zone is counted for the drones standing in it at the end of a turn,
    so a drone leaving a zone frees its place for the same turn. A
    connection is counted for every drone crossing it during a turn, in
    either direction.
    """

    def __init__(self) -> None:
        self._zones: dict[tuple[Zone, int], int] = {}
        self._links: dict[tuple[Connection, int], int] = {}

    def zone_free(self, zone: Zone, turn: int) -> bool:
        return self._zones.get((zone, turn), 0) < zone.max_drones

    def link_free(self, link: Connection, turn: int) -> bool:
        return self._links.get((link, turn), 0) < link.capacity

    def reserve(self, path: list[Position]) -> None:
        """Book every turn of a path (index in the list = turn number)."""
        for turn, position in enumerate(path):
            if position.link is not None:
                key = (position.link, turn)
                self._links[key] = self._links.get(key, 0) + 1
            if not position.flying:
                zkey = (position.zone, turn)
                self._zones[zkey] = self._zones.get(zkey, 0) + 1
