"""Pure, deterministic transitions; contains the private mechanics."""
from dataclasses import dataclass
from .levels import Level

ACTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

@dataclass(frozen=True)
class State:
    x: int
    y: int
    color: str = "neutral"
    completed: bool = False
    pending_gate: tuple[int, int] | None = None

@dataclass(frozen=True)
class Result:
    state: State
    moved: bool
    feedback: str
    # For private logs only, not participant observations.
    blocked_by: str | None = None

def initial_state(level: Level) -> State:
    for y, row in enumerate(level.rows):
        x = row.find('S')
        if x >= 0:
            return State(x, y)
    raise ValueError('Level has no starting tile')

def step(level: Level, state: State, action: str) -> Result:
    if action not in ACTIONS:
        raise ValueError(f"Unsupported action: {action}")
    if state.completed:
        return Result(state, False, "already_complete", "complete")
    cleared_state = State(state.x, state.y, state.color, state.completed, None)
    dx, dy = ACTIONS[action]
    x, y = state.x + dx, state.y + dy
    if not (0 <= x < level.width and 0 <= y < level.height):
        return Result(cleared_state, False, "blocked", "boundary")
    tile = level.tile(x, y)
    if tile == '#':
        return Result(cleared_state, False, "blocked", "wall")
    if tile in ('r', 'b') and state.color != {'r': 'red', 'b': 'blue'}[tile]:
        return Result(cleared_state, False, "blocked", "gate")
    if tile == 'n' and state.pending_gate != (x, y):
        primed_state = State(state.x, state.y, state.color, state.completed, (x, y))
        return Result(primed_state, False, "blocked", "gate")
    color = {'R': 'red', 'B': 'blue'}.get(tile, state.color)
    completed = tile == 'G'
    return Result(State(x, y, color, completed, None), True,
                  "completed" if completed else "moved")

DISPLAY_TILES = {
    '#': 'wall', '.': 'floor', 'S': 'floor', 'G': 'goal',
    'R': 'red_tile', 'B': 'blue_tile',
    'r': 'red_barrier', 'b': 'blue_barrier', 'n': 'neutral_barrier',
}

def observe(level: Level, state: State) -> dict:
    """Sole view that player-facing integrations should receive."""
    return {
        "level_id": level.identifier,
        "width": level.width,
        "height": level.height,
        "grid": [[DISPLAY_TILES[c] for c in row] for row in level.rows],
        "player": {"x": state.x, "y": state.y, "color": state.color},
        "completed": state.completed,
        "available_actions": list(ACTIONS),
    }
