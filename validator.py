"""Replays an output against the rules of the subject, from scratch."""

import re

from models import Connection, Graph, Zone

MOVE = re.compile(r"D([0-9]+)-(.+)")


class ValidationError(Exception):
    """The output breaks a rule of the simulation."""


class Validator:
    """Does not use the planner: it only reads the lines it is given."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self._links = {link.key: link for link in graph.connections}

    def check(self, lines: list[str]) -> None:
        nb = self.graph.nb_drones
        at: dict[int, Zone] = {n: self.graph.start for n in range(1, nb + 1)}
        flying: dict[int, tuple[Connection, Zone]] = {}
        delivered: set[int] = set()

        for turn, line in enumerate(lines, start=1):
            if not line.split():
                raise ValidationError(f"turn {turn}: no movement")
            moved: set[int] = set()
            crossings: dict[Connection, int] = {}
            arriving = set(flying)
            for token in line.split():
                number, rest = self._read(token, turn)
                if number in moved:
                    raise ValidationError(
                        f"turn {turn}: D{number} moves twice")
                if number in delivered:
                    raise ValidationError(
                        f"turn {turn}: D{number} is already delivered")
                moved.add(number)
                if number in flying:
                    link, target = flying.pop(number)
                    if rest != target.name:
                        raise ValidationError(
                            f"turn {turn}: D{number} must arrive at "
                            f"{target.name}")
                    at[number] = target
                else:
                    link = self._step(number, rest, at, flying, turn)
                crossings[link] = crossings.get(link, 0) + 1
                if number in at and at[number] is self.graph.end:
                    delivered.add(number)
                    del at[number]

            if not arriving <= moved:
                late = min(arriving - moved)
                raise ValidationError(
                    f"turn {turn}: D{late} cannot wait on a connection")
            self._check_capacities(at, crossings, turn)

        if len(delivered) != nb:
            raise ValidationError(
                f"only {len(delivered)} of {nb} drones were delivered")

    def _read(self, token: str, turn: int) -> tuple[int, str]:
        match = MOVE.fullmatch(token)
        if match is None:
            raise ValidationError(f"turn {turn}: bad move '{token}'")
        number = int(match.group(1))
        if not 1 <= number <= self.graph.nb_drones:
            raise ValidationError(f"turn {turn}: unknown drone in '{token}'")
        return number, match.group(2)

    def _step(self, number: int, rest: str, at: dict[int, Zone],
              flying: dict[int, tuple[Connection, Zone]],
              turn: int) -> Connection:
        """Apply a move of a drone standing in a zone, return the link."""
        origin = at[number]
        names = rest.split("-")
        if len(names) == 1:
            target = self._zone(names[0], turn)
            link = self._link(origin, target, turn)
            if target.cost != 1:
                raise ValidationError(
                    f"turn {turn}: {target.name} takes 2 turns to enter")
            at[number] = target
            return link
        if len(names) != 2 or names[0] != origin.name:
            raise ValidationError(
                f"turn {turn}: D{number} cannot take '{rest}' "
                f"from {origin.name}")
        target = self._zone(names[1], turn)
        link = self._link(origin, target, turn)
        if target.cost != 2:
            raise ValidationError(
                f"turn {turn}: {target.name} is not a restricted zone")
        flying[number] = (link, target)
        del at[number]
        return link

    def _zone(self, name: str, turn: int) -> Zone:
        zone = self.graph.zones.get(name)
        if zone is None:
            raise ValidationError(f"turn {turn}: unknown zone '{name}'")
        if zone.is_blocked:
            raise ValidationError(f"turn {turn}: {name} is blocked")
        return zone

    def _link(self, a: Zone, b: Zone, turn: int) -> Connection:
        link = self._links.get(frozenset((a.name, b.name)))
        if link is None:
            raise ValidationError(
                f"turn {turn}: {a.name} and {b.name} are not connected")
        return link

    def _check_capacities(self, at: dict[int, Zone],
                          crossings: dict[Connection, int],
                          turn: int) -> None:
        count: dict[Zone, int] = {}
        for zone in at.values():
            count[zone] = count.get(zone, 0) + 1
        for zone, drones in count.items():
            if zone is self.graph.start or zone is self.graph.end:
                continue
            if drones > zone.max_drones:
                raise ValidationError(
                    f"turn {turn}: {zone.name} holds {drones} drones "
                    f"(max {zone.max_drones})")
        for link, drones in crossings.items():
            if drones > link.capacity:
                raise ValidationError(
                    f"turn {turn}: {link.a.name}-{link.b.name} carries "
                    f"{drones} drones (max {link.capacity})")
