"""Pure, deterministic game state and transitions."""
from __future__ import annotations

from dataclasses import dataclass
from .levels import Level
from .rules import (
    DISPLAY_TILES,
    advance_color_state,
    advance_delayed_gate_state,
    evaluate_target_tile,
    render_tile,
)

ACTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


@dataclass(frozen=True)
class State:
    x: int
    y: int
    color: str = "neutral"
    completed: bool = False
    pending_gate: tuple[int, int] | None = None
    switch_countdown: int | None = None
    gate_open: bool = False


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

    # Any blocked action clears pending stubborn-gate state, while preserving
    # delayed-gate countdown (invalid/blocked moves do not advance countdown).
    blocked_fallback = State(
        state.x,
        state.y,
        state.color,
        state.completed,
        None,
        state.switch_countdown,
        state.gate_open,
    )

    dx, dy = ACTIONS[action]
    x, y = state.x + dx, state.y + dy
    if not (0 <= x < level.width and 0 <= y < level.height):
        return Result(blocked_fallback, False, "blocked", "boundary")

    tile = level.tile(x, y)
    if tile == '#':
        return Result(blocked_fallback, False, "blocked", "wall")

    gate_check = evaluate_target_tile(
        tile, (x, y), state.color, state.pending_gate, state.gate_open
    )
    if not gate_check.allowed:
        blocked_state = State(
            state.x,
            state.y,
            state.color,
            state.completed,
            gate_check.pending_gate,
            state.switch_countdown,
            state.gate_open,
        )
        return Result(blocked_state, False, "blocked", gate_check.blocked_by)

    color = advance_color_state(tile, state.color)
    switch_countdown, gate_open = advance_delayed_gate_state(
        tile, state.switch_countdown, state.gate_open
    )
    completed = tile == 'G'
    next_state = State(
        x,
        y,
        color,
        completed,
        None,
        switch_countdown,
        gate_open,
    )
    return Result(next_state, True, "completed" if completed else "moved")


def observe(level: Level, state: State) -> dict:
    """Sole view that player-facing integrations should receive."""
    return {
        "level_id": level.identifier,
        "width": level.width,
        "height": level.height,
        "grid": [
            [render_tile(c, state.gate_open) for c in row] for row in level.rows
        ],
        "player": {"x": state.x, "y": state.y, "color": state.color},
        "completed": state.completed,
        "available_actions": list(ACTIONS),
    }
