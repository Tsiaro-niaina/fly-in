*This project has been created as part of the 42 curriculum by rmandimb.*

# Fly-in

## Description

Fly-in routes a fleet of drones from a start zone to an end zone through a
network of connected zones, in as few simulation turns as possible.

The network comes from a text file. Zones have a type (`normal`, `blocked`,
`restricted`, `priority`), an optional color and a capacity (`max_drones`).
Connections are bidirectional and have their own capacity
(`max_link_capacity`). Drones move simultaneously, so the program has to
schedule them: spread them over several paths, make them wait when needed
and never exceed a capacity.

The program:

- parses and validates the map, with a clear message (line and cause) on error;
- plans every drone with a time-aware A*;
- prints the schedule, one line per turn, in the format required by the
  subject;
- checks its own output with an independent validator before printing it;
- shows the simulation in the terminal (colors, zone states, statistics)
  and, optionally, in a Pygame window.

The project is written in Python 3.10+, fully object-oriented, type-hinted
(mypy) and flake8 clean. No graph library is used.

## Instructions

### Requirements

- Python 3.10 or later
- `make` (everything else is installed in a local virtual environment)

### Installation

```
make install
```

This creates `.venv/` and installs `requirements.txt` in it (flake8, mypy,
pytest and `pygame-ce`). The other rules install it automatically if it is
missing, so `make run` is enough on a fresh clone. A virtual environment is
used on purpose: recent Debian/Ubuntu refuse `pip install` outside of one
(PEP 668, `externally-managed-environment`).

`pygame-ce` is a maintained fork of Pygame with the same API (`import
pygame`). It is used because the original `pygame` publishes no wheel for the
newest Python versions.

### Running

```
make run MAP=maps/medium/03_priority_puzzle.txt
make run MAP=maps/hard/02_capacity_hell.txt ARGS="--states"
make gui MAP=maps/hard/03_ultimate_challenge.txt
```

Or directly:

```
.venv/bin/python main.py <map_file> [--color auto|always|never] [--states] [--gui]
```

| Option | Effect |
|---|---|
| `--color auto` (default) | colors only when writing to a terminal, and never if `NO_COLOR` is set |
| `--color always` / `never` | force colors on or off (`always` is useful with `less -R`) |
| `--states` | after each turn, show how many drones are in each zone and in flight |
| `--gui` | after printing the turns, open the Pygame window |

The turns go to **stdout**, the statistics go to **stderr**. When the output
is redirected (`> file`, pipes), it contains no color codes and follows the
subject format exactly.

### Other rules

| Rule | Effect |
|---|---|
| `make debug MAP=...` | runs the program under `pdb` |
| `make test` | runs the unit tests (`tests/`) |
| `make lint` | `flake8 .` and `mypy` with the flags required by the subject |
| `make lint-strict` | `flake8 .` and `mypy --strict` |
| `make clean` | removes `__pycache__`, `.mypy_cache`, `.pytest_cache` |
| `make fclean` | `clean` + removes the virtual environment |

### Map format

```
nb_drones: 4
start_hub: start 0 0 [color=green]
hub: junction 1 0 [color=yellow max_drones=2]
hub: slow 2 1 [zone=restricted]
end_hub: goal 3 0 [color=red]
connection: start-junction [max_link_capacity=2]
connection: junction-slow
connection: slow-goal
```

Comments start with `#`. Zone metadata: `zone` (`normal`, `blocked`,
`restricted`, `priority`), `color` (any single word), `max_drones`.
Connection metadata: `max_link_capacity`. Zones must be declared before the
connections that use them, and names cannot contain dashes or spaces.

## Algorithm choices and implementation strategy

### Why a plain A* is not enough

A classic A* finds one path for one drone. Here all drones share capacity
limited zones and connections, so if each drone takes "the best path" they
block each other (see `hard/02_capacity_hell`). The problem is really about
**time**: a zone that is full at turn 5 may be free at turn 6.

### Time-aware A* with a reservation table (cooperative A*)

1. **Static distances.** A Dijkstra from the end zone gives, for every zone,
   the number of turns a lone drone would need to reach the end (it uses the
   real movement costs: 2 for restricted, 1 otherwise, blocked zones are
   ignored). It is computed once and is the A* heuristic. It never
   overestimates, because congestion can only make a trip longer.
2. **Search space.** A state is `(zone, turn)`. From a state a drone can
   *wait* (`(zone, turn + 1)`) or *move* to a neighbour (`turn + 1`, or
   `turn + 2` for a restricted zone). A move is allowed only if the
   `ReservationTable` says the connection is free during the turns of the
   crossing and the destination zone has room on arrival.
3. **Drone after drone.** Drones are planned one at a time. Each one gets the
   fastest path left by the previous drones, whose paths are then booked in the
   table. Because every path is built against the table, the final schedule
   cannot contain a conflict or a deadlock: there is nothing to repair
   afterwards.
4. **Priority zones.** The priority is a second criterion: the queue is
   ordered by `(estimated arrival, -number of priority zones crossed)`. A
   priority zone never makes a path slower, but between two paths arriving
   at the same turn, the one crossing more priority zones is chosen.
5. **Termination.** A drone that waits at the start until all the previous
   drones are delivered can always walk the shortest path alone. So the
   search is bounded by `latest arrival so far + shortest distance`, and a
   path always exists inside that bound. No infinite loop is possible.
6. **Independent validator.** `Validator` replays the printed lines using only
   the map and the rules of the subject (it does not use the planner). A
   schedule that fails it is never printed.

The strategy adapts to the map by itself: more drones than the best path can
carry simply find other paths, or wait, because the table is full on the
shortest one.

### Interpretation choices

The subject leaves a few points open. These are the choices made, so peers
can discuss them:

- **Zone capacity** is counted at the end of each turn. A drone leaving a
  zone frees its place for that same turn (as the subject says), and two
  drones can swap places between two zones if the connection allows it.
- **Connection capacity** counts every drone crossing the connection during a
  turn, in either direction.
- **Restricted zones.** The drone leaves its zone at turn `t`, is on the
  connection at the end of `t` (printed as `D1-origin-destination`) and must
  arrive at `t + 1` (printed as `D1-destination`). It cannot wait on the
  connection. The connection is counted as used during both turns, which is
  the strict reading of "occupies the connection during transit". The zone
  itself is only counted on arrival.
- **Start and end.** `max_drones` is ignored on both (no limit); drones
  delivered to the end are no longer tracked. Connection capacities still
  apply to them.
- **Name of a connection in flight** is written in the direction of travel.

### Complexity

Let `Z` be the number of zones, `C` the number of connections, `N` the number
of drones and `T` the number of turns of the schedule.

- Static Dijkstra: `O((Z + C) log Z)`, done once.
- One drone: at most `Z * T` states, and each time layer has `Z` waits and
  `2C` moves, so `O((Z + C) * T * log(Z * T))` in the worst case. The
  heuristic makes the real number of explored states much smaller.
- All drones: `O(N * (Z + C) * T * log(Z * T))`. `T` grows with `N` when a
  bottleneck limits the flow.
- Caching: the heuristic is computed once and reused by every drone. Paths
  are never recalculated: each drone is planned once, against a table that
  is updated incrementally.
- Memory: `O(N * T)` for the paths and the reservation table, plus `O(Z * T)`
  for the dictionaries of one search, freed after each drone.
- Measured: 500 drones on a small map with bottlenecks run in about 0.3 s.

### Limits

Planning drones one after the other is fast and always valid, but it does not
guarantee the minimum number of turns on every map (the first drones take the
best paths, the last ones adapt). On the provided maps it meets every
reference target. A flow on a time-expanded graph would be the next step if a
map required the true optimum.

## Visual representation

### Terminal

- Each zone name is colored with the `color` of the map. Color names are free
  words, so a table maps common ones (`red`, `orange`, `lime`, `gray`,
  `black`...) to ANSI codes; an unknown word is simply left uncolored.
- A drone flying to a restricted zone colors both ends of the connection.
- With `--states`, each turn is followed by the occupancy of every non-empty
  zone (`slow_path1:1/1`), the drones in flight, and the number of delivered
  drones. A zone that is full is highlighted in red, which makes the
  bottlenecks visible.
- At the end, statistics are printed: total turns, moves per turn, average
  turns per drone and total path cost.

### Pygame window (`--gui`)

- Zones are drawn at their `x, y` coordinates with their color. A red ring
  marks restricted zones, a gold ring marks priority zones, a cross marks
  blocked zones. The name and the type/capacity are written under each zone.
- Connections show their capacity (`x2`), and the ones used during the current
  turn are highlighted, so the flow of drones can be followed.
- Drones are colored and numbered, and glide from one zone to the next. A
  drone going to a restricted zone stops halfway on the connection at the end
  of its first turn. Drones sharing a zone are spread so they do not overlap.
- On dense maps the names would overlap, so they are hidden and shown in a
  tooltip when the mouse is over a zone.
- The top bar shows the turn, the delivered drones and the speed. The counter
  in the end zone shows how many drones arrived.
- Controls: `SPACE` play/pause, `LEFT`/`RIGHT` previous/next turn, `UP`/`DOWN`
  speed, `R` restart, `Q` or `ESC` quit. The window can be resized.
- If there is no display or Pygame is missing, a clear error is printed
  (the terminal output has already been shown).

Both views read the same simulation, so what is drawn is exactly what is
printed.

## Example

Input (`maps/easy/02_simple_fork.txt`):

```
nb_drones: 4
start_hub: start 0 0 [color=green]
hub: junction 1 0 [color=yellow max_drones=2]
hub: path_a 2 1 [color=blue]
hub: path_b 2 -1 [color=blue]
end_hub: goal 3 0 [color=red]
connection: start-junction [max_link_capacity=2]
connection: junction-path_a
connection: junction-path_b
connection: path_a-goal
connection: path_b-goal
```

Output (4 turns, reference target: 8):

```
D1-junction D2-junction
D1-path_a D2-path_b D3-junction D4-junction
D1-goal D2-goal D3-path_a D4-path_b
D3-goal D4-goal
```

With a restricted zone (`maps/medium/02_circular_loop.txt`, 6 drones, 15
turns), a drone in flight is printed with the connection, then with its
destination on the next turn:

```
D1-loop_b-exit_point D3-loop_b D5-loop_a
D1-exit_point
D1-goal D2-loop_b-exit_point D4-loop_b D6-loop_a
```

Statistics (stderr) for the first example:

```
Total turns: 4
Moves per turn: 3.00
Average turns per drone: 3.50
Total path cost: 12
```

An invalid map stops the program with the line and the cause:

```
$ python3 main.py bad_map.txt
Error: line 3: zone name 'a-b' contains a dash
```

### Results on the provided maps

| Map | Drones | Turns | Reference target |
|---|---|---|---|
| easy / linear path | 2 | 4 | 6 |
| easy / simple fork | 4 | 4 | 8 |
| easy / basic capacity | 4 | 4 | 6 |
| medium / dead end trap | 5 | 8 | 12 |
| medium / circular loop | 6 | 15 | 15 |
| medium / priority puzzle | 5 | 7 | 12 |
| hard / maze nightmare | 8 | 13 | 30 |
| hard / capacity hell | 12 | 16 | 35 |
| hard / ultimate challenge | 15 | 26 | 45 |
| challenger / impossible dream | 25 | 43 | record: 45 |

## Parser and error handling

The parser stops at the first error with `line N: cause`. It checks, among
other things: the first useful line is `nb_drones: <positive integer>`; exactly
one `start_hub` and one `end_hub`; unique zone names without dashes or spaces;
integer coordinates (negative values allowed); valid zone types; positive
capacities; well-formed `[key=value]` blocks (unknown or repeated keys are
errors); connections between known zones only, no self-loop, no duplicate
(`a-b` and `b-a` are the same). A missing, unreadable or non UTF-8 file, and
an end zone that cannot be reached from the start, also give a clear message
and a non-zero exit code. `main.py` also catches any unexpected exception so
the program never ends with a raw traceback.

## Project structure

```
main.py               entry point, command line, error handling
models.py             Zone, Connection, Graph, Position
map_parser.py         MapParser and ParseError
reservations.py       ReservationTable (zone / connection occupancy per turn)
pathfinder.py         Pathfinder: Dijkstra heuristic and time-aware A*
simulation.py         Simulation: plans all drones, output lines, statistics
validator.py          Validator: replays the output against the rules
terminal_renderer.py  colored terminal view
gui_renderer.py       Pygame window
tests/                unit tests (pytest)
Makefile              install, run, gui, debug, test, clean, fclean, lint, lint-strict
```

## Resources

- P. Hart, N. Nilsson, B. Raphael, *A Formal Basis for the Heuristic
  Determination of Minimum Cost Paths* (1968), the original A*.
- E. W. Dijkstra, *A note on two problems in connexion with graphs* (1959).
- D. Silver, *Cooperative Pathfinding* (AIIDE 2005): planning agents one
  after the other against a reservation table, the idea used here.
- A* search algorithm: https://en.wikipedia.org/wiki/A*_search_algorithm
- Python documentation: `heapq`, `typing`, `argparse`, `enum`
  (https://docs.python.org/3/)
- PEP 257 (docstrings), PEP 484 (type hints), PEP 668 (externally managed
  environments): https://peps.python.org/
- flake8 https://flake8.pycqa.org, mypy https://mypy.readthedocs.io,
  pytest https://docs.pytest.org
- pygame-ce documentation: https://pyga.me/docs/

### Use of AI

An AI assistant (Claude) was used as a pair-programming and review tool:

- **Design:** discussing the approach (why a plain A* is not enough, A* in
  space-time with a reservation table versus a flow on a time-expanded
  graph), reading the subject and the provided maps, and listing the parser
  edge cases and the ambiguities of the subject.
- **Code:** writing a first version of the modules (parser, models,
  pathfinder, simulation, validator, renderers), of the Makefile and of the
  unit tests.
- **Environment:** fixing the `externally-managed-environment` pip error
  with a virtual environment, and choosing `pygame-ce` for recent Python.
- **Checks:** all generated code was run, linted (flake8, mypy and
  `--strict`) and tested; the outputs of every provided map are replayed by
  the independent validator; the Pygame rendering was checked on screenshots.
  The code was then read and discussed to be explained during the review.
