import unittest
from arcade.levels import LEVELS, validate_level
from arcade.engine import State, initial_state, observe, step
from arcade.solver import shortest_solution


class EngineTests(unittest.TestCase):
    def test_levels_are_solvable_and_solutions_replay(self):
        for level in LEVELS.values():
            with self.subTest(level=level.identifier):
                validate_level(level)
                actions = shortest_solution(level)
                self.assertIsNotNone(actions)
                state = initial_state(level)
                for action in actions:
                    result = step(level, state, action)
                    self.assertTrue(result.moved or result.state.pending_gate is not None)
                    state = result.state
                self.assertTrue(state.completed)

    def test_rooms_1_to_3_preserve_existing_optimal_lengths(self):
        expected = {'discovery': 10, 'practice': 16, 'transfer': 12}
        for level_id, length in expected.items():
            with self.subTest(level=level_id):
                actions = shortest_solution(LEVELS[level_id])
                self.assertEqual(len(actions), length)

    def test_stubborn_gate_requires_two_consecutive_attempts(self):
        level = LEVELS['discovery_2']
        state = State(3, 1)
        first = step(level, state, 'right')
        self.assertFalse(first.moved)
        self.assertEqual(first.feedback, 'blocked')
        self.assertEqual(first.blocked_by, 'gate')
        self.assertEqual((first.state.x, first.state.y), (3, 1))
        self.assertEqual(first.state.pending_gate, (4, 1))

        second = step(level, first.state, 'right')
        self.assertTrue(second.moved)
        self.assertEqual(second.feedback, 'moved')
        self.assertIsNone(second.blocked_by)
        self.assertEqual((second.state.x, second.state.y), (4, 1))
        self.assertIsNone(second.state.pending_gate)

    def test_stubborn_gate_intervening_action_clears_pending_attempt(self):
        level = LEVELS['discovery_2']
        primed = step(level, State(3, 1), 'right').state
        self.assertEqual(primed.pending_gate, (4, 1))

        # Intervening blocked wall attempt clears pending_gate
        after_wall = step(level, primed, 'up')
        self.assertFalse(after_wall.moved)
        self.assertEqual(after_wall.blocked_by, 'wall')
        self.assertIsNone(after_wall.state.pending_gate)
        retry_after_wall = step(level, after_wall.state, 'right')
        self.assertFalse(retry_after_wall.moved)
        self.assertEqual(retry_after_wall.state.pending_gate, (4, 1))

        # Intervening valid move away and back also clears pending_gate
        moved_away = step(level, retry_after_wall.state, 'left')
        self.assertTrue(moved_away.moved)
        self.assertIsNone(moved_away.state.pending_gate)
        moved_back = step(level, moved_away.state, 'right')
        self.assertEqual((moved_back.state.x, moved_back.state.y), (3, 1))
        self.assertIsNone(moved_back.state.pending_gate)
        retry_after_move = step(level, moved_back.state, 'right')
        self.assertFalse(retry_after_move.moved)
        self.assertEqual(retry_after_move.state.pending_gate, (4, 1))

    def test_delayed_gate_opens_after_two_subsequent_valid_moves_and_stays_open(self):
        level = LEVELS['discovery_3']
        state = initial_state(level)

        # Move to (3, 1) in front of locked delayed gate at (4, 1)
        state = step(level, state, 'right').state
        state = step(level, state, 'right').state
        self.assertEqual((state.x, state.y), (3, 1))

        # Gate is initially locked
        blocked_initial = step(level, state, 'right')
        self.assertFalse(blocked_initial.moved)
        self.assertEqual(blocked_initial.feedback, 'blocked')
        self.assertEqual(blocked_initial.blocked_by, 'gate')
        self.assertFalse(blocked_initial.state.gate_open)

        # Stepping down onto switch 'T' at (3, 2) starts activation (countdown=2, still closed)
        on_switch = step(level, state, 'down')
        self.assertTrue(on_switch.moved)
        self.assertEqual((on_switch.state.x, on_switch.state.y), (3, 2))
        self.assertEqual(on_switch.state.switch_countdown, 2)
        self.assertFalse(on_switch.state.gate_open)

        # Invalid/blocked move into wall at (4, 2) does NOT advance countdown
        wall_bump = step(level, on_switch.state, 'right')
        self.assertFalse(wall_bump.moved)
        self.assertEqual(wall_bump.blocked_by, 'wall')
        self.assertEqual(wall_bump.state.switch_countdown, 2)
        self.assertFalse(wall_bump.state.gate_open)

        # 1st subsequent valid move: up to (3, 1) -> countdown=1, gate still locked
        move_one = step(level, wall_bump.state, 'up')
        self.assertTrue(move_one.moved)
        self.assertEqual((move_one.state.x, move_one.state.y), (3, 1))
        self.assertEqual(move_one.state.switch_countdown, 1)
        self.assertFalse(move_one.state.gate_open)

        # Trying to enter the gate after only 1 subsequent valid move is blocked and does not advance counter
        early_gate_try = step(level, move_one.state, 'right')
        self.assertFalse(early_gate_try.moved)
        self.assertEqual(early_gate_try.blocked_by, 'gate')
        self.assertEqual(early_gate_try.state.switch_countdown, 1)
        self.assertFalse(early_gate_try.state.gate_open)

        # 2nd subsequent valid move: left to (2, 1) -> countdown=0, gate opens!
        move_two = step(level, early_gate_try.state, 'left')
        self.assertTrue(move_two.moved)
        self.assertEqual(move_two.state.switch_countdown, 0)
        self.assertTrue(move_two.state.gate_open)
        self.assertEqual(observe(level, move_two.state)['grid'][1][4], 'open_barrier')

        # Return to (3, 1) and cross (4, 1); gate remains open permanently
        back_to_gate = step(level, move_two.state, 'right')
        self.assertTrue(back_to_gate.moved)
        self.assertTrue(back_to_gate.state.gate_open)
        crossed = step(level, back_to_gate.state, 'right')
        self.assertTrue(crossed.moved)
        self.assertEqual((crossed.state.x, crossed.state.y), (4, 1))
        self.assertTrue(crossed.state.gate_open)

    def test_delayed_gate_observations_hide_countdown_and_rule(self):
        level = LEVELS['discovery_3']
        state = step(level, step(level, initial_state(level), 'right').state, 'right').state
        activated = step(level, state, 'down').state
        obs = observe(level, activated)
        self.assertNotIn('switch_countdown', str(obs))
        self.assertNotIn('countdown', str(obs).lower())
        self.assertNotIn('delayed', str(obs).lower())
        self.assertEqual(obs['grid'][1][4], 'locked_barrier')

    def test_inaccessible_gate_is_blocked_without_moving(self):
        level = LEVELS['discovery']
        state = State(3, 1)
        result = step(level, state, 'right')
        self.assertEqual(result.state, state)
        self.assertEqual(result.feedback, 'blocked')
        self.assertEqual(result.blocked_by, 'gate')

    def test_colored_pad_unlocks_matching_gate(self):
        level = LEVELS['discovery']
        state = step(level, State(1, 2), 'down').state
        self.assertEqual(state.color, 'red')
        result = step(level, State(3, 1, 'red'), 'right')
        self.assertTrue(result.moved)
        self.assertEqual((result.state.x, result.state.y), (4, 1))

    def test_wall_is_not_a_move(self):
        level = LEVELS['discovery']
        state = initial_state(level)
        self.assertEqual(step(level, state, 'up').state, state)

    def test_observation_does_not_include_hidden_rule(self):
        level = LEVELS['discovery_2']
        primed = step(level, State(3, 1), 'right').state
        result = observe(level, primed)
        self.assertNotIn('rule', result)
        self.assertNotIn('solution', result)
        self.assertNotIn('blocked_by', result)
        self.assertNotIn('pending_gate', str(result))
        self.assertNotIn('stubborn', str(result).lower())
        self.assertEqual(result['player']['color'], 'neutral')

    def test_replay_is_deterministic(self):
        level = LEVELS['practice']
        sequence = ['down', 'down', 'up', 'up', 'right', 'right']
        def run():
            state = initial_state(level)
            history = []
            for action in sequence:
                outcome = step(level, state, action)
                history.append(outcome)
                state = outcome.state
            return history
        self.assertEqual(run(), run())


if __name__ == '__main__':
    unittest.main()
