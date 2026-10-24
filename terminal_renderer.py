"""Colored terminal view of a finished simulation."""

from models import Zone
from simulation import Simulation

# Zone colors are free words in the map files. Unknown words are simply
# not colored. "black" is drawn on a white background to stay readable.
ANSI_CODES = {
    "red": "31", "green": "32", "yellow": "33", "blue": "34",
    "magenta": "35", "purple": "35", "cyan": "36", "white": "37",
    "gray": "90", "grey": "90", "black": "30;47",
    "orange": "38;5;208", "brown": "38;5;130", "lime": "38;5;118",
    "pink": "38;5;213", "gold": "38;5;220", "maroon": "38;5;88",
    "navy": "38;5;18", "teal": "38;5;30", "violet": "38;5;99",
}
RED = "31"
RESET = "\033[0m"


class TerminalRenderer:
    """Builds the text shown in the terminal, with or without colors."""

    def __init__(self, simulation: Simulation, color: bool = True,
                 states: bool = False) -> None:
        self.simulation = simulation
        self.color = color
        self.states = states

    def render(self) -> str:
        """The turn lines, each followed by the zone states if asked."""
        lines = []
        for turn in range(1, self.simulation.turns + 1):
            lines.append(self._turn_line(turn))
            if self.states:
                lines.append("    " + self._state_line(turn))
        return "\n".join(lines)

    def summary(self) -> str:
        stats = self.simulation.statistics()
        return (f"Total turns: {stats.turns}\n"
                f"Moves per turn: {stats.moves_per_turn:.2f}\n"
                f"Average turns per drone: {stats.turns_per_drone:.2f}\n"
                f"Total path cost: {stats.total_cost}")

    def _wrap(self, text: str, code: str | None) -> str:
        if not self.color or code is None:
            return text
        return f"\033[{code}m{text}{RESET}"

    def _zone_name(self, zone: Zone) -> str:
        code = ANSI_CODES.get(zone.color.lower()) if zone.color else None
        return self._wrap(zone.name, code)

    def _turn_line(self, turn: int) -> str:
        moves = []
        for number, zone, origin in self.simulation.movements(turn):
            target = self._zone_name(zone)
            if origin is not None:
                target = f"{self._zone_name(origin)}-{target}"
            moves.append(f"D{number}-{target}")
        return " ".join(moves)

    def _state_line(self, turn: int) -> str:
        """Who is where at the end of the turn (empty zones are omitted)."""
        graph = self.simulation.graph
        counts: dict[Zone, int] = {}
        flying = 0
        for path in self.simulation.paths:
            position = path[min(turn, len(path) - 1)]
            if position.flying:
                flying += 1
            else:
                counts[position.zone] = counts.get(position.zone, 0) + 1

        parts = []
        for zone in graph.zones.values():
            number = counts.get(zone, 0)
            if number == 0:
                continue
            text = str(number)
            if zone is not graph.start and zone is not graph.end:
                text += f"/{zone.max_drones}"
                if number == zone.max_drones:
                    text = self._wrap(text, RED)
            parts.append(f"{self._zone_name(zone)}:{text}")
        if flying:
            parts.append(f"in flight:{flying}")
        return " ".join(parts)
