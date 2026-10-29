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
