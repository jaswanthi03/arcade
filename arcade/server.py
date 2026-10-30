"""Local browser UI + minimal JSON action API, without third-party dependencies.

Run: python -m arcade.server
API documentation: README.md. Do NOT expose this experimental server publicly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from threading import Lock
from uuid import uuid4

from .engine import ACTIONS, State, initial_state, observe, step
from .levels import LEVELS, Level

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / 'web'
LOG_PATH = Path(os.environ.get('ARCADE_LOG', str(BASE_DIR / 'logs' / 'events.jsonl')))


@dataclass
class Session:
    session_id: str
    participant_id: str
    role: str
    level: Level
    state: State
    sequence: int = 0
    attempts: int = 0
    valid_moves: int = 0
    invalid_moves: int = 0
    resets: int = 0
    episode: int = 1
    explanations: list[str] = field(default_factory=list)

    def public(self, feedback: str = 'ready', moved: bool | None = None) -> dict:
        return {
            'session_id': self.session_id,
            'observation': observe(self.level, self.state),
            'level_name': self.level.name,
            'phase': self.level.phase,
            'feedback': feedback,
            'moved': moved,
            'stats': {
                'attempts': self.attempts,
                'valid_moves': self.valid_moves,
                'invalid_moves': self.invalid_moves,
                'resets': self.resets,
                'episode': self.episode,
            },
        }


class GameService:
    def __init__(self, log_path: Path = LOG_PATH):
        self.sessions: dict[str, Session] = {}
        self.log_path = log_path
        self.lock = Lock()

    def _event(self, session: Session, event_type: str, **fields):
        session.sequence += 1
        event = {
            'schema_version': 1,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'session_id': session.session_id,
            'participant_id': session.participant_id,
            'role': session.role,
            'level_id': session.level.identifier,
            'phase': session.level.phase,
            'sequence': session.sequence,
            'episode': session.episode,
            'event_type': event_type,
            **fields,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('a', encoding='utf-8') as file:
            file.write(json.dumps(event, ensure_ascii=False) + '\n')

    def start(self, level_id='discovery', role='human', participant_id=None) -> dict:
        if level_id not in LEVELS:
            raise ValueError('Unknown level_id')
        if role not in ('human', 'ai'):
            raise ValueError('role must be human or ai')
        if participant_id is not None and (
            not isinstance(participant_id, str) or not 1 <= len(participant_id) <= 64
        ):
            raise ValueError('participant_id must be 1-64 characters')
        with self.lock:
            session_id = uuid4().hex
            s = Session(session_id, participant_id or ('anon-' + session_id[:8]), role,
                        LEVELS[level_id], initial_state(LEVELS[level_id]))
            self.sessions[session_id] = s
            self._event(s, 'session_start', initial_state=vars(s.state))
            return s.public()

    def _get(self, session_id) -> Session:
        if not isinstance(session_id, str) or session_id not in self.sessions:
            raise ValueError('Unknown session_id (sessions are memory-only)')
        return self.sessions[session_id]

    def act(self, session_id, action) -> dict:
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError('Action must be one of: up, down, left, right')
        with self.lock:
            s = self._get(session_id)
            if s.state.completed:
                raise ValueError('Level already complete; start another session')
            before = s.state
            result = step(s.level, s.state, action)
            s.state = result.state
            s.attempts += 1
            if result.moved:
                s.valid_moves += 1
            else:
                s.invalid_moves += 1
            self._event(s, 'action', action=action, valid=result.moved,
                        outcome=result.feedback, blocked_by=result.blocked_by,
                        state_before=vars(before), state_after=vars(result.state))
            return s.public(result.feedback, result.moved)

    def reset(self, session_id) -> dict:
        with self.lock:
            s = self._get(session_id)
            s.resets += 1
            s.episode += 1
            s.state = initial_state(s.level)
            self._event(s, 'reset', initial_state=vars(s.state))
            return s.public('reset')

    def explain(self, session_id, explanation) -> dict:
        if not isinstance(explanation, str) or not 1 <= len(explanation.strip()) <= 1000:
            raise ValueError('Explanation must be 1-1000 characters')
        with self.lock:
            s = self._get(session_id)
            s.explanations.append(explanation.strip())
            self._event(s, 'explanation', text=explanation.strip(),
                        is_complete=s.state.completed)
            return {'saved': True, 'explanation_number': len(s.explanations)}


SERVICE = GameService()


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path not in ('/', '/index.html', '/api/levels'):
            self._send_json({'error': 'Not found'}, 404)
            return
        if self.path == '/api/levels':
            self._send_json({'levels': [
                {'id': l.identifier, 'name': l.name, 'phase': l.phase}
                for l in LEVELS.values()]})
            return
        body = (WEB_DIR / 'index.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        handlers = {
            '/api/sessions': lambda d: SERVICE.start(d.get('level_id', 'discovery'),
                                                     d.get('role', 'human'),
                                                     d.get('participant_id')),
            '/api/actions': lambda d: SERVICE.act(d.get('session_id'), d.get('action')),
            '/api/reset': lambda d: SERVICE.reset(d.get('session_id')),
            '/api/explain': lambda d: SERVICE.explain(d.get('session_id'),
                                                     d.get('explanation')),
        }
        if self.path not in handlers:
            self._send_json({'error': 'Not found'}, 404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 8192:
                raise ValueError('Request body too large')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object')
            result = handlers[self.path](data)
            self._send_json(result)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({'error': str(exc)}, 400)


def main():
    host = os.environ.get('ARCADE_HOST', '127.0.0.1')
    port = int(os.environ.get('ARCADE_PORT', '8000'))
    with ThreadingHTTPServer((host, port), Handler) as server:
        print(f'Hidden-Rule Arcade at http://{host}:{port} (Ctrl+C to stop)', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
