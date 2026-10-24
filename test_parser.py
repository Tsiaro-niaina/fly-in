from pathlib import Path

import pytest

from map_parser import MapParser, ParseError
from models import Graph, ZoneType

HEADER = "nb_drones: 2\nstart_hub: s 0 0\nend_hub: g 3 0\n"


def parse(text: str) -> Graph:
    return MapParser().parse_text(text)


def test_minimal_map() -> None:
    graph = parse(HEADER + "connection: s-g\n")
    assert graph.nb_drones == 2
    assert graph.start.name == "s"
    assert graph.end.name == "g"
    assert len(graph.connections) == 1
    assert graph.end_is_reachable()


def test_metadata_and_defaults() -> None:
    graph = parse(
        "# comment\n\nnb_drones: 3\n"
        "start_hub: s 0 0 [color=green max_drones=9]\n"
        "hub: a 1 -1 [max_drones=2 zone=restricted color=red]  # inline\n"
        "hub: b 2 0\n"
        "end_hub: g 3 0\n"
        "connection: s-a [max_link_capacity=3]\n"
        "connection: a-b\n"
        "connection: b-g\n")
    a, b = graph.zones["a"], graph.zones["b"]
    assert (a.x, a.y) == (1, -1)
    assert a.zone_type is ZoneType.RESTRICTED and a.cost == 2
    assert a.max_drones == 2 and a.color == "red"
    assert b.max_drones == 1 and b.color is None and b.cost == 1
    assert graph.start.max_drones == 3
    assert graph.connections[0].capacity == 3
    assert graph.connections[1].capacity == 1


def test_blocked_zone_is_not_a_neighbor() -> None:
    graph = parse(HEADER + "hub: x 1 0 [zone=blocked]\n"
                  "connection: s-x\nconnection: x-g\n")
    assert graph.neighbors(graph.start) == []
    assert not graph.end_is_reachable()


BAD_MAPS = [
    ("", "empty"),
    ("start_hub: s 0 0\n", "first line"),
    ("nb_drones: 0\n", "positive"),
    ("nb_drones: -2\n", "positive"),
    ("nb_drones: abc\n", "positive"),
    ("nb_drones: 2\nend_hub: g 1 0\n", "no start_hub"),
    ("nb_drones: 2\nstart_hub: s 0 0\n", "no end_hub"),
    (HEADER + "start_hub: t 5 5\n", "twice"),
    (HEADER + "end_hub: t 5 5\n", "twice"),
    (HEADER + "hub: s 1 1\n", "twice"),
    (HEADER + "hub: a-b 1 1\n", "dash"),
    (HEADER + "hub: a 1.5 1\n", "integers"),
    (HEADER + "hub: a 1\n", "expected"),
    (HEADER + "hub: a 1 1 [zone=fast]\n", "invalid zone type"),
    (HEADER + "hub: a 1 1 [max_drones=0]\n", "positive"),
    (HEADER + "hub: a 1 1 [max_drones=x]\n", "positive"),
    (HEADER + "hub: a 1 1 [color]\n", "key=value"),
    (HEADER + "hub: a 1 1 [color=red\n", "']'"),
    (HEADER + "hub: a 1 1 [color=red]]\n", "bracket"),
    (HEADER + "hub: a 1 1 [speed=3]\n", "unknown zone metadata"),
    (HEADER + "hub: a 1 1 [color=red color=blue]\n", "twice"),
    (HEADER + "connection: s-nope\n", "unknown zone"),
    (HEADER + "connection: s-g\nconnection: g-s\n", "twice"),
    (HEADER + "connection: s-s\n", "itself"),
    (HEADER + "connection: s g\n", "expected"),
    (HEADER + "connection: s-g [max_link_capacity=0]\n", "positive"),
    (HEADER + "connection: s-g [zone=normal]\n", "unknown connection"),
    (HEADER + "connection: g-s\nhub: late 1 1\nconnection: late-x\n",
     "unknown zone"),
    (HEADER + "wall: a b\n", "unknown keyword"),
    (HEADER + "just some text\n", "expected"),
    ("nb_drones: 1\nstart_hub: s 0 0 [zone=blocked]\n", "blocked"),
]


@pytest.mark.parametrize("text, expected", BAD_MAPS)
def test_invalid_maps(text: str, expected: str) -> None:
    with pytest.raises(ParseError) as err:
        parse(text)
    assert expected in str(err.value)


def test_error_reports_line_number() -> None:
    with pytest.raises(ParseError, match="line 4"):
        parse(HEADER + "hub: a-b 1 1\n")


def test_ignored_capacity_on_start_and_end() -> None:
    graph = parse("nb_drones: 4\nstart_hub: s 0 0 [max_drones=0]\n"
                  "end_hub: g 1 0 [max_drones=abc]\nconnection: s-g\n")
    assert graph.start.max_drones == 4


def test_parser_can_be_reused() -> None:
    parser = MapParser()
    parser.parse_text(HEADER + "connection: s-g\n")
    with pytest.raises(ParseError):
        parser.parse_text("nb_drones: 1\n")


def test_missing_and_unreadable_files(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="No such file"):
        MapParser().parse_file(str(tmp_path / "nope.txt"))
    with pytest.raises(ParseError):
        MapParser().parse_file(str(tmp_path))
    binary = tmp_path / "bin.txt"
    binary.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ParseError, match="UTF-8"):
        MapParser().parse_file(str(binary))


MAPS = sorted(Path("maps").rglob("*.txt"))


@pytest.mark.parametrize("path", MAPS, ids=lambda p: p.stem)
def test_provided_maps(path: Path) -> None:
    graph = MapParser().parse_file(str(path))
    assert graph.end_is_reachable()
