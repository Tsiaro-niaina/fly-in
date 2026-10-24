"""Plans every drone and turns the plan into the turn-by-turn output."""

from typing import NamedTuple

from models import Graph, Position, Zone
from pathfinder import Pathfinder
from reservations import ReservationTable

# (drone number, destination, origin when the drone takes off for a
# restricted zone, None otherwise)
Movement = tuple[int, Zone, Zone | None]


class SimulationError(Exception):
    """The drones cannot be routed."""


class Statistics(NamedTuple):
    turns: int
    moves_per_turn: float
    turns_per_drone: float
    total_cost: int


class Simulation:
    """Routes the drones one after the other.

    Each drone gets the fastest path left by the drones planned before
    it, so the final schedule never breaks a capacity rule.
    """

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.paths: list[list[Position]] = []

    def run(self) -> None:
        if not self.graph.end_is_reachable():
            raise SimulationError("end_hub cannot be reached from start_hub")
        table = ReservationTable()
        finder = Pathfinder(self.graph, table)
        self.paths = []
        latest = 0
        for number in range(1, self.graph.nb_drones + 1):
            # A drone that waits for everybody else to be delivered can
            # always walk the shortest path alone, so this limit is safe.
            limit = latest + finder.start_distance
            path = finder.find(limit)
            if path is None:
                raise SimulationError(f"no path found for drone D{number}")
            table.reserve(path)
            self.paths.append(path)
            latest = max(latest, len(path) - 1)

    @property
    def turns(self) -> int:
        return max((len(path) - 1 for path in self.paths), default=0)

    def movements(self, turn: int) -> list[Movement]:
        """Every drone that moves during the given turn (starting at 1)."""
        result = []
        for number, path in enumerate(self.paths, start=1):
            if turn >= len(path) or path[turn].link is None:
                continue
            here = path[turn]
            origin = path[turn - 1].zone if here.flying else None
            result.append((number, here.zone, origin))
        return result

    def output_lines(self) -> list[str]:
        """One line per turn: 'D1-zone D2-origin-destination ...'."""
        lines = []
        for turn in range(1, self.turns + 1):
            moves = []
            for number, zone, origin in self.movements(turn):
                if origin is None:
                    moves.append(f"D{number}-{zone.name}")
                else:
                    moves.append(f"D{number}-{origin.name}-{zone.name}")
            lines.append(" ".join(moves))
        return lines

    def statistics(self) -> Statistics:
        moves = 0
        cost = 0
        for path in self.paths:
            for position in path:
                if position.link is not None:
                    moves += 1
                    if not position.flying:
                        cost += position.zone.cost
        nb = len(self.paths)
        arrivals = sum(len(path) - 1 for path in self.paths)
        return Statistics(
            turns=self.turns,
            moves_per_turn=moves / self.turns if self.turns else 0.0,
            turns_per_drone=arrivals / nb if nb else 0.0,
            total_cost=cost)
