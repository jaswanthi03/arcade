"""Private modular rule definitions and rule-specific state transitions.

Each rule mechanic is isolated here so `arcade/engine.py` handles generic grid
movement and public observations while keeping private mechanics modular.
"""
from __future__ import annotations

from dataclasses import dataclass

# Base and rule-specific map characters allowed in level layouts.
MAP_CHARS = frozenset('#.SGRBrbnTd')

# Static tile display labels for public observations.
DISPLAY_TILES = {
    '#': 'wall',
    '.': 'floor',
    'S': 'floor',
    'G': 'goal',
    'R': 'red_tile',
    'B': 'blue_tile',
    'r': 'red_barrier',
    'b': 'blue_barrier',
    'n': 'neutral_barrier',
    'T': 'switch_tile',
    'd': 'locked_barrier',
}


@dataclass(frozen=True)
class GateCheck:
    allowed: bool
    blocked_by: str | None = None
    pending_gate: tuple[int, int] | None = None


def check_color_barrier(tile: str, color: str) -> GateCheck:
    """Color-matching barrier rule: 'r' requires red, 'b' requires blue."""
    if tile in ('r', 'b') and color != {'r': 'red', 'b': 'blue'}[tile]:
        return GateCheck(False, 'gate', None)
    return GateCheck(True)


def check_stubborn_gate(
    tile: str, target: tuple[int, int], pending_gate: tuple[int, int] | None
) -> GateCheck:
    """Stubborn gate rule: 'n' blocks first attempt and succeeds on immediate repeat."""
    if tile == 'n' and pending_gate != target:
        return GateCheck(False, 'gate', target)
    return GateCheck(True)


def check_delayed_gate(tile: str, gate_open: bool) -> GateCheck:
    """Delayed-action gate rule: 'd' blocks movement until opened by switch countdown."""
    if tile == 'd' and not gate_open:
        return GateCheck(False, 'gate', None)
    return GateCheck(True)


def evaluate_target_tile(
    tile: str,
    target: tuple[int, int],
    color: str,
    pending_gate: tuple[int, int] | None,
    gate_open: bool,
) -> GateCheck:
    """Run all active gate rules against the target tile."""
    for check in (
        check_color_barrier(tile, color),
        check_stubborn_gate(tile, target, pending_gate),
        check_delayed_gate(tile, gate_open),
    ):
        if not check.allowed:
            return check
    return GateCheck(True)


def advance_color_state(tile: str, current_color: str) -> str:
    """Update player color when stepping onto a colored pad ('R' or 'B')."""
    return {'R': 'red', 'B': 'blue'}.get(tile, current_color)


def advance_delayed_gate_state(
    tile: str, switch_countdown: int | None, gate_open: bool
) -> tuple[int | None, bool]:
    """Update delayed-action gate activation on a successful movement action.

    - Stepping onto switch 'T' starts activation (`switch_countdown = 2`).
    - The gate opens after exactly two subsequent successful movement actions.
    - Invalid/blocked moves do not call this function and never advance the counter.
    - Once opened (`gate_open=True`), the gate remains open.
    """
    if gate_open:
        return 0, True
    if switch_countdown is not None:
        remaining = switch_countdown - 1
        if remaining <= 0:
            return 0, True
        return remaining, False
    if tile == 'T':
        return 2, False
    return None, False


def render_tile(tile: str, gate_open: bool = False) -> str:
    """Map an internal map character to its public observation tile label."""
    if tile == 'd' and gate_open:
        return 'open_barrier'
    return DISPLAY_TILES[tile]
