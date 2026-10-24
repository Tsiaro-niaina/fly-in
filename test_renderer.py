import re

from map_parser import MapParser
from simulation import Simulation
from terminal_renderer import TerminalRenderer

LINEAR = (
    "nb_drones: 2\nstart_hub: s 0 0 [color=green]\n"
    "hub: a 1 0 [color=blue max_drones=2]\nhub: b 2 0 [color=nocolor]\n"
    "end_hub: g 3 0 [color=red]\nconnection: s-a\nconnection: a-b\n"
    "connection: b-g\n")
RESTRICTED = (
    "nb_drones: 1\nstart_hub: s 0 0\nhub: r 1 0 [zone=restricted color=red]"
    "\nend_hub: g 2 0\nconnection: s-r\nconnection: r-g\n")
ANSI = re.compile(r"\033\[[0-9;]*m")


def simulate(text: str) -> Simulation:
    simulation = Simulation(MapParser().parse_text(text))
    simulation.run()
    return simulation


def test_plain_render_is_the_raw_output() -> None:
    simulation = simulate(LINEAR)
    renderer = TerminalRenderer(simulation, color=False)
    assert renderer.render() == "\n".join(simulation.output_lines())
    assert "\033" not in renderer.render()


def test_color_render_only_adds_escape_codes() -> None:
    simulation = simulate(LINEAR)
    colored = TerminalRenderer(simulation, color=True).render()
    assert "\033[34ma\033[0m" in colored
    assert ANSI.sub("", colored) == "\n".join(simulation.output_lines())


def test_unknown_color_is_left_plain() -> None:
    colored = TerminalRenderer(simulate(LINEAR), color=True).render()
    assert "b\033" not in colored
    assert "D1-b" in colored


def test_flight_colors_both_ends() -> None:
    simulation = simulate(RESTRICTED)
    assert simulation.output_lines()[0] == "D1-s-r"
    colored = TerminalRenderer(simulation, color=True).render()
    assert colored.splitlines()[0] == "D1-s-\033[31mr\033[0m"


def test_state_lines() -> None:
    renderer = TerminalRenderer(simulate(LINEAR), color=False, states=True)
    lines = renderer.render().splitlines()
    assert lines[0] == "D1-a"
    assert lines[1].strip() == "s:1 a:1/2"
    assert lines[-1].strip() == "g:2"
    flight = TerminalRenderer(simulate(RESTRICTED), color=False, states=True)
    assert flight.render().splitlines()[1].strip() == "in flight:1"


def test_full_zone_is_highlighted() -> None:
    text = ("nb_drones: 2\nstart_hub: s 0 0\nhub: a 1 0 [max_drones=2]\n"
            "end_hub: g 2 0\nconnection: s-a [max_link_capacity=2]\n"
            "connection: a-g [max_link_capacity=2]\n")
    renderer = TerminalRenderer(simulate(text), color=True, states=True)
    assert "\033[31m2/2\033[0m" in renderer.render()


def test_statistics() -> None:
    stats = simulate(LINEAR).statistics()
    assert stats.turns == 4
    assert stats.moves_per_turn == 1.5
    assert stats.turns_per_drone == 3.5
    assert stats.total_cost == 6
    assert simulate(RESTRICTED).statistics().total_cost == 3


def test_summary_text() -> None:
    summary = TerminalRenderer(simulate(LINEAR)).summary()
    assert "Total turns: 4" in summary
    assert "Total path cost: 6" in summary
