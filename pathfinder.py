"""A* search over (zone, turn) states for a single drone."""

import heapq
from collections.abc import Iterator
from itertools import count

from models import Connection, Graph, Position, Zone, ZoneType
from reservations import ReservationTable

State = tuple[Zone, int]
Move = tuple[Zone, int, Connection | None, int]


class Pathfinder:
    """Finds the fastest path that fits around already booked drones.

    The heuristic is the shortest travel time to the end zone when
    nobody else is on the map. It never overestimates, so the first time
    the end zone is popped from the queue its turn is the earliest
    possible. Among paths arriving at the same turn, the one crossing
    the most priority zones wins.
    """

    def __init__(self, graph: Graph, table: ReservationTable) -> None:
        self.graph = graph
        self.table = table
        self._to_end = self._distances_to_end()

    @property
    def start_distance(self) -> int:
        """Turns needed by a lone drone to go from start to end."""
        return self._to_end[self.graph.start]

    def _distances_to_end(self) -> dict[Zone, int]:
        end = self.graph.end
        dist = {end: 0}
        order = count()
        queue = [(0, next(order), end)]
        while queue:
            d, _, zone = heapq.heappop(queue)
            if d > dist[zone]:
                continue
            for other, _ in self.graph.neighbors(zone):
                # a drone coming from "other" pays the cost of entering zone
                new = d + zone.cost
                if new < dist.get(other, new + 1):
                    dist[other] = new
                    heapq.heappush(queue, (new, next(order), other))
        return dist

    def find(self, limit: int) -> list[Position] | None:
        """Best path arriving no later than turn limit, or None."""
        start, end = self.graph.start, self.graph.end
        best: dict[State, int] = {(start, 0): 0}
        parent: dict[State, tuple[State, Connection | None]] = {}
        order = count()
        queue = [(self._to_end[start], 0, next(order), start, 0)]
        while queue:
            _, neg_priority, _, zone, turn = heapq.heappop(queue)
            priority = -neg_priority
            if best[(zone, turn)] > priority:
                continue
            if zone is end:
                return self._build_path((zone, turn), parent)
            for target, arrival, link, gain in self._moves(zone, turn, limit):
                state = (target, arrival)
                new_priority = priority + gain
                if state in best and best[state] >= new_priority:
                    continue
                best[state] = new_priority
                parent[state] = ((zone, turn), link)
                estimate = arrival + self._to_end[target]
                heapq.heappush(
                    queue,
                    (estimate, -new_priority, next(order), target, arrival))
        return None

    def _moves(self, zone: Zone, turn: int, limit: int) -> Iterator[Move]:
        """Everything a drone can do from zone at the end of turn."""
        if turn + 1 <= limit and self.table.zone_free(zone, turn + 1):
            yield zone, turn + 1, None, 0
        for target, link in self.graph.neighbors(zone):
            arrival = turn + target.cost
            if arrival > limit or target not in self._to_end:
                continue
            crossing = range(turn + 1, arrival + 1)
            if not all(self.table.link_free(link, t) for t in crossing):
                continue
            if not self.table.zone_free(target, arrival):
                continue
            gain = 1 if target.zone_type is ZoneType.PRIORITY else 0
            yield target, arrival, link, gain

    def _build_path(
            self, goal: State,
            parent: dict[State, tuple[State, Connection | None]]
    ) -> list[Position]:
        steps: list[Position] = []
        state = goal
        while state in parent:
            (prev_zone, prev_turn), link = parent[state]
            zone, turn = state
            if link is None:
                steps.append(Position(zone))
            else:
                steps.append(Position(zone, link))
                if turn - prev_turn == 2:
                    steps.append(Position(zone, link, True))
            state = (prev_zone, prev_turn)
        steps.append(Position(self.graph.start))
        steps.reverse()
        return steps
