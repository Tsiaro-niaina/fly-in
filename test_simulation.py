from pathlib import Path

import pytest

from map_parser import MapParser
from models import Graph
from simulation import Simulation, SimulationError
from validator import ValidationError, Validator


def solve(text: str) -> tuple[Graph, list[str]]:
    graph = MapParser().parse_text(text)
    simulation = Simulation(graph)
    simulation.run()
    return graph, simulation.output_lines()


def test_linear_path() -> None:
    _, lines = solve(
        "nb_drones: 2\nstart_hub: s 0 0\nhub: a 1 0\nhub: b 2 0\n"
        "end_hub: g 3 0\nconnection: s-a\nconnection: a-b\n"
        "connection: b-g\n")
    assert lines == ["D1-a", "D1-b D2-a", "D1-g D2-b", "D2-g"]


def test_restricted_zone_takes_two_turns() -> None:
    _, lines = solve(
        "nb_drones: 1\nstart_hub: s 0 0\nhub: r 1 0 [zone=restricted]\n"
        "end_hub: g 2 0\nconnection: s-r\nconnection: r-g\n")
    assert lines == ["D1-s-r", "D1-r", "D1-g"]


def test_blocked_zone_is_avoided() -> None:
    _, lines = solve(
        "nb_drones: 1\nstart_hub: s 0 0\nhub: x 1 0 [zone=blocked]\n"
        "hub: a 1 1\nhub: b 2 1\nend_hub: g 3 0\n"
        "connection: s-x\nconnection: x-g\nconnection: s-a\n"
        "connection: a-b\nconnection: b-g\n")
    assert lines == ["D1-a", "D1-b", "D1-g"]


def test_priority_zone_wins_a_tie() -> None:
    _, lines = solve(
        "nb_drones: 1\nstart_hub: s 0 0\nhub: n 1 0\n"
        "hub: p 1 1 [zone=priority]\nend_hub: g 2 0\n"
        "connection: s-n\nconnection: n-g\nconnection: s-p\n"
        "connection: p-g\n")
    assert lines == ["D1-p", "D1-g"]


def test_drones_share_a_narrow_link_in_turns() -> None:
    _, lines = solve(
        "nb_drones: 3\nstart_hub: s 0 0\nhub: a 1 0 [max_drones=3]\n"
        "end_hub: g 2 0\nconnection: s-a\nconnection: a-g\n")
    assert len(lines) == 4


def test_unreachable_end() -> None:
    graph = MapParser().parse_text(
        "nb_drones: 1\nstart_hub: s 0 0\nhub: a 1 0\nend_hub: g 2 0\n"
        "connection: s-a\n")
    with pytest.raises(SimulationError, match="cannot be reached"):
        Simulation(graph).run()


GRAPH = (
    "nb_drones: 2\nstart_hub: s 0 0\nhub: a 1 0\nhub: r 2 0 "
    "[zone=restricted]\nhub: b 1 1 [zone=blocked]\nend_hub: g 3 0\n"
    "connection: s-a\nconnection: a-r\nconnection: r-g\n"
    "connection: s-b\nconnection: b-g\nconnection: s-g\n")

BAD_OUTPUTS = [
    (["D1-a", "D1-r"], "takes 2 turns"),
    (["D1-a", "D1-a-r", "D1-a"], "must arrive at r"),
    (["D1-a", "D1-a-r", "D2-a"], "cannot wait on a connection"),
    (["D1-a D2-a"], "holds 2 drones"),
    (["D1-b"], "blocked"),
    (["D1-r"], "not connected"),
    (["D3-a"], "unknown drone"),
    (["D1-a D1-g"], "moves twice"),
    (["D1-nowhere"], "unknown zone"),
    (["Dx-a"], "bad move"),
    ([""], "no movement"),
    (["D1-a"], "delivered"),
    (["D1-g", "D1-a"], "already delivered"),
]


@pytest.mark.parametrize("lines, expected", BAD_OUTPUTS)
def test_validator_rejects(lines: list[str], expected: str) -> None:
    graph = MapParser().parse_text(GRAPH)
    with pytest.raises(ValidationError, match=expected):
        Validator(graph).check(lines)


def test_validator_link_capacity() -> None:
    graph = MapParser().parse_text(
        "nb_drones: 2\nstart_hub: s 0 0\nend_hub: g 1 0\n"
        "connection: s-g\n")
    with pytest.raises(ValidationError, match="carries 2 drones"):
        Validator(graph).check(["D1-g D2-g"])


# turns obtained must stay under the targets of the subject
TARGETS = {
    "01_linear_path": 6, "02_simple_fork": 8, "03_basic_capacity": 6,
    "01_dead_end_trap": 12, "02_circular_loop": 15,
    "03_priority_puzzle": 12, "01_maze_nightmare": 30,
    "02_capacity_hell": 35, "03_ultimate_challenge": 45,
    "01_the_impossible_dream": 45,
}
MAPS = sorted(Path("maps").rglob("*.txt"))


@pytest.mark.parametrize("path", MAPS, ids=lambda p: p.stem)
def test_provided_maps(path: Path) -> None:
    graph, lines = solve(path.read_text())
    Validator(graph).check(lines)
    assert len(lines) <= TARGETS[path.stem]
