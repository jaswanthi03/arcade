import json
import tempfile
import unittest
from pathlib import Path

from arcade.server import GameService


class SessionTests(unittest.TestCase):
    def test_attempts_invalid_moves_explanation_and_reset_are_logged(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.jsonl'
            service = GameService(path)
            opened = service.start(participant_id='pilot_h01')
            session_id = opened['session_id']
            blocked = service.act(session_id, 'up')
            self.assertFalse(blocked['moved'])
            self.assertEqual(blocked['feedback'], 'blocked')
            self.assertEqual(blocked['stats']['invalid_moves'], 1)
            moved = service.act(session_id, 'down')
            self.assertTrue(moved['moved'])
            self.assertEqual(moved['stats']['valid_moves'], 1)
            self.assertTrue(service.explain(session_id, 'My first hypothesis.')['saved'])
            reset = service.reset(session_id)
            self.assertEqual(reset['stats']['resets'], 1)
            self.assertEqual(reset['stats']['episode'], 2)
            self.assertEqual(reset['stats']['attempts'], 2)
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([e['event_type'] for e in events],
                             ['session_start', 'action', 'action', 'explanation', 'reset'])
            self.assertEqual([e['sequence'] for e in events], [1, 2, 3, 4, 5])
            self.assertEqual(events[1]['blocked_by'], 'wall')
            self.assertEqual(events[3]['text'], 'My first hypothesis.')
            self.assertTrue(all(e['participant_id'] == 'pilot_h01' for e in events))

    def test_api_returns_no_private_move_failure_details(self):
        with tempfile.TemporaryDirectory() as d:
            service = GameService(Path(d) / 'events.jsonl')
            session_id = service.start()['session_id']
            response = service.act(session_id, 'up')
            self.assertNotIn('blocked_by', str(response))
            self.assertNotIn('solution', str(response))
            self.assertNotIn('pending_gate', str(response))

    def test_stubborn_gate_reset_clears_pending_state_and_logs_attempts(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'stubborn.jsonl'
            service = GameService(path)
            opened = service.start(level_id='discovery_2', participant_id='dev_test')
            session_id = opened['session_id']

            # Move to (3, 1) in front of the neutral barrier at (4, 1)
            self.assertTrue(service.act(session_id, 'right')['moved'])
            self.assertTrue(service.act(session_id, 'right')['moved'])

            # 1st attempt into stubborn gate is blocked (primes pending_gate)
            first_try = service.act(session_id, 'right')
            self.assertFalse(first_try['moved'])
            self.assertEqual(first_try['feedback'], 'blocked')
            self.assertNotIn('pending_gate', str(first_try))

            # Reset clears pending_gate and returns player to start (1, 1)
            reset_resp = service.reset(session_id)
            self.assertEqual(reset_resp['stats']['resets'], 1)
            self.assertIsNone(service.sessions[session_id].state.pending_gate)

            # Return to (3, 1); first attempt after reset is blocked again, second succeeds
            self.assertTrue(service.act(session_id, 'right')['moved'])
            self.assertTrue(service.act(session_id, 'right')['moved'])
            after_reset_first = service.act(session_id, 'right')
            self.assertFalse(after_reset_first['moved'])
            after_reset_second = service.act(session_id, 'right')
            self.assertTrue(after_reset_second['moved'])
            self.assertEqual(after_reset_second['observation']['player']['x'], 4)

            events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            gate_events = [e for e in events if e['event_type'] == 'action' and e['state_before']['x'] == 3]
            self.assertEqual([e['valid'] for e in gate_events], [False, False, True])
            self.assertEqual([e['blocked_by'] for e in gate_events], ['gate', 'gate', None])

    def test_delayed_gate_logging_completion_and_human_ai_parity(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'delayed.jsonl'
            service = GameService(path)
            seq = ['right', 'right', 'right', 'down', 'up', 'right', 'left', 'right', 'right', 'right', 'right', 'right']

            human_session = service.start(level_id='discovery_3', role='human', participant_id='h_test')
            ai_session = service.start(level_id='discovery_3', role='ai', participant_id='ai_test')

            h_outcomes = []
            a_outcomes = []
            for action in seq:
                h_res = service.act(human_session['session_id'], action)
                a_res = service.act(ai_session['session_id'], action)
                self.assertNotIn('switch_countdown', str(h_res))
                self.assertNotIn('blocked_by', str(h_res))
                h_outcomes.append((h_res['moved'], h_res['feedback'], h_res['observation']))
                a_outcomes.append((a_res['moved'], a_res['feedback'], a_res['observation']))

            # Human and AI use identical authoritative transition logic
            self.assertEqual(h_outcomes, a_outcomes)
            self.assertTrue(h_outcomes[-1][2]['completed'])
            self.assertEqual(h_outcomes[-1][1], 'completed')

            events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            ai_actions = [e for e in events if e['role'] == 'ai' and e['event_type'] == 'action']
            self.assertEqual(len(ai_actions), len(seq))
            self.assertEqual(ai_actions[2]['valid'], False)
            self.assertEqual(ai_actions[2]['blocked_by'], 'gate')
            self.assertEqual(ai_actions[5]['valid'], False)
            self.assertEqual(ai_actions[5]['blocked_by'], 'gate')
            self.assertEqual(ai_actions[-1]['outcome'], 'completed')
            self.assertTrue(ai_actions[-1]['state_after']['completed'])

    def test_action_budget_and_runaway_loop_protection(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'budget.jsonl'
            service = GameService(
                path,
                max_episode_actions=6,
                max_session_actions=10,
                max_resets=2,
                max_consecutive_blocked=4,
                max_repeated_blocked_action=2,
            )
            session_id = service.start(level_id='discovery_3', role='ai')['session_id']

            # Repeated identical blocked action ('up' into wall) stops after 2 blocked attempts
            self.assertFalse(service.act(session_id, 'up')['moved'])
            self.assertFalse(service.act(session_id, 'up')['moved'])
            with self.assertRaisesRegex(ValueError, 'Runaway loop detected'):
                service.act(session_id, 'up')

            # Event log did not record the rejected 3rd runaway call
            events_after_loop = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(events_after_loop), 3)  # 1 session_start + 2 blocked actions

            # Valid moves reset consecutive/repeated blocked counters, up to episode budget (6)
            self.assertTrue(service.act(session_id, 'right')['moved'])  # attempt 3
            self.assertTrue(service.act(session_id, 'left')['moved'])   # attempt 4
            self.assertTrue(service.act(session_id, 'right')['moved'])  # attempt 5
            self.assertTrue(service.act(session_id, 'left')['moved'])   # attempt 6
            with self.assertRaisesRegex(ValueError, 'Episode action budget'):
                service.act(session_id, 'right')

            # Reset clears episode_attempts, allowing up to max_session_actions (10)
            reset_resp = service.reset(session_id)
            self.assertEqual(reset_resp['stats']['episode_attempts'], 0)
            for action in ('right', 'left', 'right', 'left'):
                self.assertTrue(service.act(session_id, action)['moved'])
            with self.assertRaisesRegex(ValueError, 'Session action budget'):
                service.act(session_id, 'right')


if __name__ == '__main__':
    unittest.main()
