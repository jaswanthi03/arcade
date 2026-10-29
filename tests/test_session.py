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


if __name__ == '__main__':
    unittest.main()
