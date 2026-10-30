"""Private level definitions. Do not expose this module to evaluated AI agents."""
from dataclasses import dataclass
from .rules import MAP_CHARS

@dataclass(frozen=True)
class Level:
    identifier: str
    name: str
    phase: str
    rows: tuple[str, ...]

    @property
    def width(self) -> int:
        return len(self.rows[0])

    @property
    def height(self) -> int:
        return len(self.rows)

    def tile(self, x: int, y: int) -> str:
        return self.rows[y][x]

# Private legend: # wall, . floor, S start, G goal, R/B pads, r/b gates, n stubborn gate.
LEVELS = {
    "discovery": Level("discovery", "Room 1 · Discovery", "discovery", (
        "#########",
        "#S..r..G#",
        "#.#.###.#",
        "#R..#...#",
        "#########",
    )),
    "practice": Level("practice", "Room 2 · Practice", "practice", (
        "###########",
        "#S..r..b.G#",
        "#.#.#.#.#.#",
        "#R..#B..#.#",
        "###########",
    )),
    "transfer": Level("transfer", "Room 3 · Transfer", "transfer", (
        "###########",
        "#S...b...G#",
        "#.#.#.#.#.#",
        "#B...#....#",
        "#.##.#.##.#",
        "#....#....#",
        "###########",
    )),
    "discovery_2": Level("discovery_2", "Room 4 · Discovery", "discovery", (
        "#########",
        "#S..n..G#",
        "#.#.###.#",
        "#...#...#",
        "#########",
    )),
    "transfer_2": Level("transfer_2", "Room 5 · Transfer", "transfer", (
        "###########",
        "#S..n..r.G#",
        "#.#.#.#.#.#",
        "#...#R..#.#",
        "###########",
    )),
    "discovery_3": Level("discovery_3", "Room 6 · Discovery", "discovery", (
        "#########",
        "#S..d..G#",
        "#.#T#.###",
        "#...#...#",
        "#########",
    )),
    "practice_3": Level("practice_3", "Room 7 · Practice", "practice", (
        "###########",
        "#S..d....G#",
        "#.#.#.###.#",
        "#..T..#...#",
        "###########",
    )),
    "transfer_3": Level("transfer_3", "Room 8 · Transfer", "transfer", (
        "###########",
        "#S....d..G#",
        "#.###.#.#.#",
        "#...T.#...#",
        "#.###.###.#",
        "#.........#",
        "###########",
    )),
}

def validate_level(level: Level) -> None:
    if not level.rows or any(len(row) != level.width for row in level.rows):
        raise ValueError(f"{level.identifier}: layout must be rectangular")
    chars = ''.join(level.rows)
    if set(chars) - MAP_CHARS:
        raise ValueError(f"{level.identifier}: unexpected map character")
    if chars.count('S') != 1 or chars.count('G') != 1:
        raise ValueError(f"{level.identifier}: expected one start and one goal")
    if any(c != '#' for c in (level.rows[0] + level.rows[-1])) or any(
        row[0] != '#' or row[-1] != '#' for row in level.rows
    ):
        raise ValueError(f"{level.identifier}: border must be walled")

for _level in LEVELS.values():
    validate_level(_level)
