"""Pygame window that replays a finished simulation."""

import math

import pygame

from models import Position, Zone, ZoneType
from simulation import Simulation

Point = tuple[float, float]

BACKGROUND = (24, 26, 32)
TEXT = (230, 230, 235)
DIM = (140, 145, 155)
LINK = (70, 75, 90)
LINK_ACTIVE = (240, 200, 80)
DEFAULT_ZONE = (120, 125, 140)
RING = {
    ZoneType.RESTRICTED: (225, 70, 70),
    ZoneType.PRIORITY: (255, 215, 0),
}
TURN_SECONDS = 1.0
FPS = 60
MARGIN = 90
LABEL_MIN_SCALE = 60  # below this many pixels per unit, names overlap
HUD_HEIGHT = 60
HELP = ("SPACE play/pause   LEFT/RIGHT step   UP/DOWN speed   "
        "R restart   Q quit")


class GuiError(Exception):
    """The window could not be opened."""


class PygameRenderer:
    """Draws the network and moves the drones from turn to turn.

    Time is a float: 2.5 means halfway between the end of turn 2 and the
    end of turn 3. A drone flying to a restricted zone sits in the middle
    of the connection at the end of its first turn.
    """

    def __init__(self, simulation: Simulation) -> None:
        self.simulation = simulation
        self.graph = simulation.graph
        self.paths = simulation.paths
        self.total = simulation.turns
        self._fonts: dict[int, pygame.font.Font] = {}
        self._zone_colors = {z: self._zone_color(z)
                             for z in self.graph.zones.values()}
        self._slots = self._compute_slots()
        xs = [zone.x for zone in self.graph.zones.values()]
        ys = [zone.y for zone in self.graph.zones.values()]
        self._min = (min(xs), min(ys))
        self._span = (max(max(xs) - min(xs), 1), max(max(ys) - min(ys), 1))
        self._scale = 1.0
        self._origin = (0.0, 0.0)
        self._radius = 20

    def run(self) -> None:
        """Open the window and loop until it is closed."""
        try:
            pygame.display.init()
            pygame.font.init()
            pygame.display.set_mode((1100, 720), pygame.RESIZABLE)
            pygame.display.set_caption("Fly-in")
        except pygame.error as err:
            pygame.quit()
            raise GuiError(f"cannot open a window: {err}")
        try:
            self._loop()
        finally:
            pygame.quit()

    def _loop(self) -> None:
        clock = pygame.time.Clock()
        now = 0.0
        playing = True
        speed = 1.0
        running = True
        while running:
            seconds = clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    key = event.key
                    if key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif key == pygame.K_SPACE:
                        if now >= self.total:
                            now = 0.0
                        playing = not playing
                    elif key == pygame.K_RIGHT:
                        playing = False
                        now = min(self.total, math.floor(now) + 1)
                    elif key == pygame.K_LEFT:
                        playing = False
                        now = max(0, math.ceil(now) - 1)
                    elif key == pygame.K_UP:
                        speed = min(8.0, speed * 1.5)
                    elif key == pygame.K_DOWN:
                        speed = max(0.25, speed / 1.5)
                    elif key == pygame.K_r:
                        now = 0.0
                        playing = True
            if playing:
                now = min(self.total, now + seconds * speed / TURN_SECONDS)
                if now >= self.total:
                    playing = False
            surface = pygame.display.get_surface()
            if surface is None:
                break
            mouse = None
            if pygame.mouse.get_focused():
                mouse = pygame.mouse.get_pos()
            self.draw(surface, now, playing, speed, mouse)
            pygame.display.flip()

    def draw(self, surface: pygame.Surface, now: float,
             playing: bool = False, speed: float = 1.0,
             mouse: Point | None = None) -> None:
        """Paint one frame of the simulation at the given time."""
        self._layout(surface.get_size())
        surface.fill(BACKGROUND)
        self._draw_links(surface, math.ceil(now))
        for zone in self.graph.zones.values():
            self._draw_zone(surface, zone)
        delivered = sum(1 for p in self.paths if now >= len(p) - 1)
        self._draw_text(surface, str(delivered), 28, TEXT,
                        self._to_screen(self.graph.end.x, self.graph.end.y))
        for number, path in enumerate(self.paths, start=1):
            if now < len(path) - 1:
                self._draw_drone(surface, number, path, now)
        self._draw_hud(surface, now, delivered, playing, speed)
        hovered = self._zone_at(mouse) if mouse else None
        if hovered is not None and mouse is not None:
            self._draw_tooltip(surface, hovered, mouse)

    # layout

    def _layout(self, size: tuple[int, int]) -> None:
        width, height = size
        usable_w = max(width - 2 * MARGIN, 1)
        usable_h = max(height - HUD_HEIGHT - MARGIN, 1)
        self._scale = min(usable_w / self._span[0], usable_h / self._span[1])
        self._radius = int(max(10, min(26, self._scale * 0.3)))
        # center the drawing in the free area
        self._origin = (
            (width - self._span[0] * self._scale) / 2,
            HUD_HEIGHT + (usable_h - self._span[1] * self._scale) / 2)

    def _to_screen(self, x: float, y: float) -> Point:
        return (self._origin[0] + (x - self._min[0]) * self._scale,
                self._origin[1] + (y - self._min[1]) * self._scale)

    # drawing

    def _draw_links(self, surface: pygame.Surface, turn: int) -> None:
        active = set()
        for path in self.paths:
            if turn < len(path) and path[turn].link is not None:
                active.add(path[turn].link)
        for link in self.graph.connections:
            a = self._to_screen(link.a.x, link.a.y)
            b = self._to_screen(link.b.x, link.b.y)
            if link in active:
                pygame.draw.line(surface, LINK_ACTIVE, a, b, 4)
            else:
                pygame.draw.line(surface, LINK, a, b, 2)
            if link.capacity > 1:
                middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                self._draw_text(surface, f"x{link.capacity}", 16, DIM, middle)

    def _draw_zone(self, surface: pygame.Surface, zone: Zone) -> None:
        center = self._to_screen(zone.x, zone.y)
        radius = self._radius
        if zone.is_blocked:
            pygame.draw.circle(surface, (50, 50, 56), center, radius)
            offset = radius * 0.6
            for sign in (1, -1):
                pygame.draw.line(
                    surface, (150, 60, 60),
                    (center[0] - offset, center[1] - sign * offset),
                    (center[0] + offset, center[1] + sign * offset), 3)
        else:
            pygame.draw.circle(
                surface, self._zone_colors[zone], center, radius)
        ring = RING.get(zone.zone_type, (200, 200, 205))
        width = 3 if zone.zone_type in RING else 1
        pygame.draw.circle(surface, ring, center, radius, width)

        if self._scale >= LABEL_MIN_SCALE:
            below = (center[0], center[1] + radius + 10)
            self._draw_text(surface, zone.name, 18, TEXT, below)
            tags = self._tags(zone)
            if tags:
                self._draw_text(surface, tags, 15, DIM,
                                (below[0], below[1] + 14))

    def _draw_tooltip(self, surface: pygame.Surface, zone: Zone,
                      mouse: Point) -> None:
        text = zone.name
        tags = self._tags(zone)
        if tags:
            text += f"  ({tags})"
        image = self._font(20).render(text, True, TEXT)
        box = image.get_rect(topleft=(mouse[0] + 14, mouse[1] + 14))
        box.inflate_ip(12, 8)
        box.clamp_ip(surface.get_rect())
        pygame.draw.rect(surface, (45, 49, 60), box)
        pygame.draw.rect(surface, DIM, box, 1)
        surface.blit(image, image.get_rect(center=box.center))

    def _draw_drone(self, surface: pygame.Surface, number: int,
                    path: list[Position], now: float) -> None:
        turn = int(now)
        progress = now - turn
        progress = progress * progress * (3 - 2 * progress)
        before = self._screen_position(number, path, turn)
        after = self._screen_position(number, path, turn + 1)
        point = (before[0] + (after[0] - before[0]) * progress,
                 before[1] + (after[1] - before[1]) * progress)
        size = max(4, int(self._radius * 0.32))
        color = pygame.Color(0)
        color.hsva = ((number * 137) % 360, 55, 100, 100)
        pygame.draw.circle(surface, color, point, size)
        pygame.draw.circle(surface, (10, 10, 10), point, size, 1)
        if size >= 7:
            self._draw_text(surface, str(number), size + 5, (10, 10, 10),
                            point)

    def _draw_hud(self, surface: pygame.Surface, now: float, delivered: int,
                  playing: bool, speed: float) -> None:
        state = "playing" if playing else "paused"
        shown = min(self.total, math.ceil(now))
        status = (f"Turn {shown} / {self.total}    "
                  f"Delivered {delivered} / {len(self.paths)}    "
                  f"Speed x{speed:.2f}    {state}")
        font = self._font(22)
        surface.blit(font.render(status, True, TEXT), (16, 14))
        height = surface.get_height()
        surface.blit(self._font(18).render(HELP, True, DIM), (16, height - 28))

    def _draw_text(self, surface: pygame.Surface, text: str, size: int,
                   color: tuple[int, int, int], center: Point) -> None:
        image = self._font(size).render(text, True, color)
        surface.blit(image, image.get_rect(center=center))

    # positions

    def _screen_position(self, number: int, path: list[Position],
                         turn: int) -> Point:
        """Where drone number is drawn at the end of the given turn."""
        turn = min(turn, len(path) - 1)
        position = path[turn]
        zone = position.zone
        x, y = float(zone.x), float(zone.y)
        if position.flying:
            origin = path[turn - 1].zone
            x, y = (x + origin.x) / 2, (y + origin.y) / 2
        sx, sy = self._to_screen(x, y)
        dx, dy = self._slot_offset(*self._slots[min(turn, self.total)][number])
        return sx + dx, sy + dy

    def _slot_offset(self, rank: int, count: int) -> Point:
        """Spread the drones that share a place so they do not overlap."""
        if count == 1:
            return 0.0, 0.0
        if count <= 6:
            angle = 2 * math.pi * rank / count
            radius = self._radius * 0.5
        else:
            angle = rank * 2.4
            radius = self._radius * 0.8 * math.sqrt((rank + 0.5) / count)
        return radius * math.cos(angle), radius * math.sin(angle)

    def _compute_slots(self) -> list[dict[int, tuple[int, int]]]:
        """For each turn, the rank of every drone among those sharing its
        place, as (rank, number of drones there)."""
        slots = []
        for turn in range(self.total + 1):
            groups: dict[tuple[Zone, bool], list[int]] = {}
            for number, path in enumerate(self.paths, start=1):
                position = path[min(turn, len(path) - 1)]
                key = (position.zone, position.flying)
                groups.setdefault(key, []).append(number)
            ranks = {}
            for members in groups.values():
                for rank, number in enumerate(members):
                    ranks[number] = (rank, len(members))
            slots.append(ranks)
        return slots

    # helpers

    def _tags(self, zone: Zone) -> str:
        if zone is self.graph.start:
            return "start"
        if zone is self.graph.end:
            return "end"
        tags = []
        if zone.zone_type is not ZoneType.NORMAL:
            tags.append(zone.zone_type.value)
        if zone.max_drones > 1:
            tags.append(f"max {zone.max_drones}")
        return ", ".join(tags)

    def _zone_at(self, point: Point) -> Zone | None:
        for zone in self.graph.zones.values():
            x, y = self._to_screen(zone.x, zone.y)
            if math.hypot(point[0] - x, point[1] - y) <= self._radius:
                return zone
        return None

    def _zone_color(self, zone: Zone) -> tuple[int, int, int]:
        if zone.color:
            try:
                color = pygame.Color(zone.color)
                return color.r, color.g, color.b
            except ValueError:
                pass
        return DEFAULT_ZONE

    def _font(self, size: int) -> pygame.font.Font:
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]
