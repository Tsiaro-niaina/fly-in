"""Reads a map file and builds the Graph, with clear error messages."""

import re

from models import Connection, Graph, Zone, ZoneType

POSITIVE_INT = re.compile(r"[0-9]+")
COORDINATE = re.compile(r"-?[0-9]+")

ZONE_KEYS = {"zone", "color", "max_drones"}
LINK_KEYS = {"max_link_capacity"}


class ParseError(Exception):
    """Invalid map file. Carries the line number when there is one."""

    def __init__(self, message: str, line: int | None = None) -> None:
        if line is not None:
            message = f"line {line}: {message}"
        super().__init__(message)


class MapParser:
    """Parses one map. Zones must be declared before their connections."""

    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._nb_drones: int | None = None
        self._zones: dict[str, Zone] = {}
        self._connections: list[Connection] = []
        self._link_keys: set[frozenset[str]] = set()
        self._start: Zone | None = None
        self._end: Zone | None = None

    def parse_file(self, path: str) -> Graph:
        try:
            with open(path, encoding="utf-8") as file:
                text = file.read()
        except UnicodeDecodeError:
            raise ParseError(f"'{path}' is not a valid UTF-8 text file")
        except OSError as err:
            reason = err.strerror or "cannot be read"
            raise ParseError(f"'{path}': {reason}")
        return self.parse_text(text)

    def parse_text(self, text: str) -> Graph:
        self._reset()
        for number, raw in enumerate(text.splitlines(), start=1):
            line = raw.split("#", 1)[0].strip()
            if line:
                self._parse_line(line, number)
        return self._build()

    def _parse_line(self, line: str, number: int) -> None:
        keyword, colon, rest = line.partition(":")
        keyword = keyword.strip()
        rest = rest.strip()
        if not colon:
            raise ParseError("expected '<keyword>: <value>'", number)

        if self._nb_drones is None:
            if keyword != "nb_drones":
                raise ParseError(
                    "the first line must be 'nb_drones: <number>'", number)
            self._nb_drones = self._positive(rest, "nb_drones", number)
        elif keyword in ("start_hub", "end_hub", "hub"):
            self._parse_zone(keyword, rest, number)
        elif keyword == "connection":
            self._parse_connection(rest, number)
        else:
            raise ParseError(f"unknown keyword '{keyword}'", number)

    def _parse_zone(self, keyword: str, rest: str, number: int) -> None:
        head, meta = self._split_metadata(rest, number)
        parts = head.split()
        if len(parts) != 3:
            raise ParseError("expected '<name> <x> <y> [metadata]'", number)
        name, raw_x, raw_y = parts
        if "-" in name:
            raise ParseError(f"zone name '{name}' contains a dash", number)
        if name in self._zones:
            raise ParseError(f"zone '{name}' is defined twice", number)
        for raw in (raw_x, raw_y):
            if not COORDINATE.fullmatch(raw):
                raise ParseError(
                    f"coordinates must be integers, got '{raw}'", number)
        self._check_keys(meta, ZONE_KEYS, "zone", number)

        type_name = meta.get("zone", "normal")
        try:
            zone_type = ZoneType(type_name)
        except ValueError:
            valid = ", ".join(t.value for t in ZoneType)
            raise ParseError(
                f"invalid zone type '{type_name}' (valid: {valid})", number)

        is_hub = keyword == "hub"
        if not is_hub and zone_type is ZoneType.BLOCKED:
            raise ParseError(f"{keyword} cannot be a blocked zone", number)
        if is_hub and "max_drones" in meta:
            capacity = self._positive(meta["max_drones"], "max_drones", number)
        elif is_hub:
            capacity = 1
        else:
            # start and end have no limit, max_drones is ignored there
            capacity = self._nb_drones or 1

        zone = Zone(name, int(raw_x), int(raw_y), zone_type,
                    meta.get("color"), capacity)
        if keyword == "start_hub":
            if self._start is not None:
                raise ParseError("start_hub is defined twice", number)
            self._start = zone
        elif keyword == "end_hub":
            if self._end is not None:
                raise ParseError("end_hub is defined twice", number)
            self._end = zone
        self._zones[name] = zone

    def _parse_connection(self, rest: str, number: int) -> None:
        head, meta = self._split_metadata(rest, number)
        names = head.split("-")
        if len(head.split()) != 1 or len(names) != 2 or not all(names):
            raise ParseError("expected '<zone1>-<zone2> [metadata]'", number)
        self._check_keys(meta, LINK_KEYS, "connection", number)
        for name in names:
            if name not in self._zones:
                raise ParseError(f"unknown zone '{name}'", number)
        if names[0] == names[1]:
            raise ParseError(f"'{names[0]}' cannot connect to itself", number)

        key = frozenset(names)
        if key in self._link_keys:
            raise ParseError(f"connection '{head}' is defined twice", number)
        capacity = 1
        if "max_link_capacity" in meta:
            capacity = self._positive(
                meta["max_link_capacity"], "max_link_capacity", number)

        self._link_keys.add(key)
        self._connections.append(
            Connection(self._zones[names[0]], self._zones[names[1]], capacity))

    def _split_metadata(self, rest: str,
                        number: int) -> tuple[str, dict[str, str]]:
        """Separate 'head [k=v k=v]' into the head and a dict."""
        opening = rest.find("[")
        if opening == -1:
            head, inner = rest, ""
        else:
            if not rest.endswith("]"):
                raise ParseError("metadata must end with ']'", number)
            head, inner = rest[:opening], rest[opening + 1:-1]
        if "]" in head or "[" in inner or "]" in inner:
            raise ParseError("misplaced bracket in metadata", number)

        meta: dict[str, str] = {}
        for token in inner.split():
            key, equal, value = token.partition("=")
            if not equal or not key or not value:
                raise ParseError(
                    f"invalid metadata '{token}' (expected key=value)",
                    number)
            if key in meta:
                raise ParseError(f"metadata '{key}' given twice", number)
            meta[key] = value
        return head.strip(), meta

    def _check_keys(self, meta: dict[str, str], allowed: set[str],
                    what: str, number: int) -> None:
        for key in meta:
            if key not in allowed:
                raise ParseError(f"unknown {what} metadata '{key}'", number)

    def _positive(self, value: str, what: str, number: int) -> int:
        if not POSITIVE_INT.fullmatch(value) or int(value) == 0:
            raise ParseError(
                f"{what} must be a positive integer, got '{value}'", number)
        return int(value)

    def _build(self) -> Graph:
        if self._nb_drones is None:
            raise ParseError("empty file: 'nb_drones' is missing")
        if self._start is None:
            raise ParseError("no start_hub defined")
        if self._end is None:
            raise ParseError("no end_hub defined")
        return Graph(self._nb_drones, self._zones, self._connections,
                     self._start, self._end)
