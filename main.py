"""Entry point: loads a map, routes the drones and prints each turn."""

import argparse
import os
import sys

from map_parser import MapParser, ParseError
from simulation import Simulation, SimulationError
from terminal_renderer import TerminalRenderer
from validator import ValidationError, Validator


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Route a fleet of drones through a network of zones.")
    parser.add_argument("map_file", help="path of the map to load")
    parser.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto",
        help="color the zone names (auto: only when writing to a terminal)")
    parser.add_argument(
        "--gui", action="store_true",
        help="after the turns are printed, open the Pygame window")
    parser.add_argument(
        "--states", action="store_true",
        help="show where every drone is after each turn")
    return parser


def use_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never" or "NO_COLOR" in os.environ:
        return False
    return sys.stdout.isatty()


def main(argv: list[str]) -> int:
    args = make_parser().parse_args(argv[1:])
    try:
        graph = MapParser().parse_file(args.map_file)
        simulation = Simulation(graph)
        simulation.run()
        Validator(graph).check(simulation.output_lines())
    except (ParseError, SimulationError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except ValidationError as err:
        print(f"Internal error, invalid schedule: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Unexpected error: {err!r}", file=sys.stderr)
        return 1

    renderer = TerminalRenderer(
        simulation, color=use_color(args.color), states=args.states)
    try:
        print(renderer.render())
        sys.stdout.flush()
    except BrokenPipeError:
        # reader closed the pipe (e.g. "| head"): stop quietly
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    print(renderer.summary(), file=sys.stderr)
    if args.gui:
        return open_window(simulation)
    return 0


def open_window(simulation: Simulation) -> int:
    try:
        from gui_renderer import GuiError, PygameRenderer
    except ImportError:
        print("Error: pygame is not installed (run 'make install')",
              file=sys.stderr)
        return 1
    try:
        PygameRenderer(simulation).run()
    except GuiError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
