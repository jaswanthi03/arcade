"""Private correctness oracle; NEVER an evaluated AI player's tool."""
from __future__ import annotations

from collections import deque
from .levels import Level, LEVELS
from .engine import ACTIONS, initial_state, step


def shortest_solution(level: Level) -> list[str] | None:
    """BFS over complete State (x, y, color, completed, pending_gate, switch_countdown, gate_open)."""
    start = initial_state(level)
    q = deque([(start, [])])
    seen = {start}
    while q:
        state, actions = q.popleft()
        if state.completed:
            return actions
        for action in ACTIONS:
            successor = step(level, state, action).state
            if successor not in seen:
                seen.add(successor)
                q.append((successor, actions + [action]))
    return None


if __name__ == '__main__':
    for item in LEVELS.values():
        solution = shortest_solution(item)
        if solution is None:
            raise SystemExit(f"FAIL {item.identifier}: unsolvable")
        state = initial_state(item)
        valid_moves = 0
        for act in solution:
            res = step(item, state, act)
            if res.moved:
                valid_moves += 1
            state = res.state
        if not state.completed:
            raise SystemExit(f"FAIL {item.identifier}: solution did not complete")
        print(f"{item.identifier}: optimal actions={len(solution)} (valid moves={valid_moves}); solution={','.join(solution)}")
