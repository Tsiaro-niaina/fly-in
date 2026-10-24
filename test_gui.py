import os
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from gui_renderer import GuiError, PygameRenderer  # noqa: E402
from map_parser import MapParser  # noqa: E402
from simulation import Simulation  # noqa: E402

RESTRICTED = (
    "nb_drones: 1\nstart_hub: s 0 0\nhub: r 1 0 [zone=restricted]\n"
    "end_hub: g 2 0\nconnection: s-r\nconnection: r-g\n")


def make_renderer(text: str) -> PygameRenderer:
    simulation = Simulation(MapParser().parse_text(text))
    simulation.run()
    pygame.font.init()
    return PygameRenderer(simulation)


MAPS = sorted(Path("maps").rglob("*.txt"))


@pytest.mark.parametrize("path", MAPS, ids=lambda p: p.stem)
def test_every_frame_can_be_drawn(path: Path) -> None:
    renderer = make_renderer(path.read_text())
    surface = pygame.Surface((900, 600))
    total = renderer.total
    for moment in (0.0, 0.5, total / 2, total - 0.2, float(total)):
        renderer.draw(surface, moment, True, 1.0, (450.0, 300.0))


def test_flying_drone_is_halfway() -> None:
    renderer = make_renderer(RESTRICTED)
    renderer.draw(pygame.Surface((800, 600)), 0.0)
    path = renderer.paths[0]
    middle = renderer._to_screen(0.5, 0)
    assert renderer._screen_position(1, path, 1) == middle
    assert renderer._screen_position(1, path, 2) == renderer._to_screen(1, 0)


def test_drones_sharing_a_zone_do_not_overlap() -> None:
    renderer = make_renderer(
        "nb_drones: 3\nstart_hub: s 0 0\nend_hub: g 1 0\n"
        "connection: s-g [max_link_capacity=3]\n")
    renderer.draw(pygame.Surface((800, 600)), 0.0)
    points = {renderer._screen_position(n, renderer.paths[n - 1], 0)
              for n in (1, 2, 3)}
    assert len(points) == 3


def test_zone_under_the_mouse() -> None:
    renderer = make_renderer(RESTRICTED)
    renderer.draw(pygame.Surface((800, 600)), 0.0)
    zone = renderer.graph.zones["r"]
    assert renderer._zone_at(renderer._to_screen(zone.x, zone.y)) is zone
    assert renderer._zone_at((0.0, 0.0)) is None


def test_unknown_color_gets_the_default(monkeypatch: pytest.MonkeyPatch
                                        ) -> None:
    renderer = make_renderer(
        "nb_drones: 1\nstart_hub: s 0 0 [color=nonsense]\n"
        "end_hub: g 1 0 [color=lime]\nconnection: s-g\n")
    colors = renderer._zone_colors
    assert colors[renderer.graph.start] == (120, 125, 140)
    assert colors[renderer.graph.end] != (120, 125, 140)


def test_no_display_gives_a_clear_error(monkeypatch: pytest.MonkeyPatch
                                        ) -> None:
    renderer = make_renderer(RESTRICTED)
    monkeypatch.setenv("SDL_VIDEODRIVER", "no_such_driver")
    with pytest.raises(GuiError, match="cannot open a window"):
        renderer.run()
