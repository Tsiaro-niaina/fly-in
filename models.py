"""Data model of the drone network: zones, connections and the graph."""

from collections import deque
from enum import Enum
from typing import NamedTuple


class ZoneType(Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


class Zone:
    """A hub of the network."""

    def __init__(self, name: str, x: int, y: int,
                 zone_type: ZoneType = ZoneType.NORMAL,
                 color: str | None = None,
                 max_drones: int = 1) -> None:
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.color = color
        self.max_drones = max_drones

    @property
    def cost(self) -> int:
        """Number of turns needed to enter this zone."""
        if self.zone_type is ZoneType.RESTRICTED:
            return 2
        return 1

    @property
    def is_blocked(self) -> bool:
        return self.zone_type is ZoneType.BLOCKED

    def __repr__(self) -> str:
        return f"Zone({self.name!r}, {self.zone_type.value})"


class Connection:
    """A bidirectional link between two zones."""

    def __init__(self, a: Zone, b: Zone, capacity: int = 1) -> None:
        self.a = a
        self.b = b
        self.capacity = capacity

    @property
    def key(self) -> frozenset[str]:
        """Direction-independent identifier (a-b is the same as b-a)."""
        return frozenset((self.a.name, self.b.name))

    def other(self, zone: Zone) -> Zone:
        """Return the zone at the opposite end of the link."""
        if zone is self.a:
            return self.b
        if zone is self.b:
            return self.a
        raise ValueError(f"{zone.name} is not an end of {self!r}")

    def __repr__(self) -> str:
        return f"Connection({self.a.name}-{self.b.name})"


class Position(NamedTuple):
    """Where a drone is at the end of a turn.

    link is the connection crossed during that turn (None if the drone
    waited). flying is True while the drone is on the way to a restricted
    zone: zone is then its destination, not a place it occupies.
    """

    zone: Zone
    link: Connection | None = None
    flying: bool = False


class Graph:
    """The whole network, built once by the parser and never modified."""

    def __init__(self, nb_drones: int, zones: dict[str, Zone],
                 connections: list[Connection],
                 start: Zone, end: Zone) -> None:
        self.nb_drones = nb_drones
        self.zones = zones
        self.connections = connections
        self.start = start
        self.end = end
        self._links: dict[str, list[Connection]] = {
            name: [] for name in zones
        }
        for link in connections:
            self._links[link.a.name].append(link)
            self._links[link.b.name].append(link)

    def neighbors(self, zone: Zone) -> list[tuple[Zone, Connection]]:
        """Zones reachable in one move, blocked zones excluded."""
        result = []
        for link in self._links[zone.name]:
            target = link.other(zone)
            if not target.is_blocked:
                result.append((target, link))
        return result

    def end_is_reachable(self) -> bool:
        """Tell whether at least one valid path leads from start to end."""
        seen = {self.start.name}
        queue = deque([self.start])
        while queue:
            zone = queue.popleft()
            if zone is self.end:
                return True
            for target, _ in self.neighbors(zone):
                if target.name not in seen:
                    seen.add(target.name)
                    queue.append(target)
        return False
