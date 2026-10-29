# Hidden-Rule Arcade — Python MVP 0.1

A small, deterministic research prototype for studying rule discovery in puzzle environments. This first milestone implements **The Color Lab** with three levels, a browser-based human interface, a terminal fallback, an action API, and JSONL logging. The engine is independent of the interfaces and has no third-party dependencies.

## Requirements

- Python **3.10+**.
- A browser for the visual interface, if your development environment can preview a local web server.
- No `pip install` required.

## Run locally or in Optimus

From the project directory:

```bash
python -m unittest discover -s tests -v
python -m arcade.solver
python -m arcade.server
```

Open `http://127.0.0.1:8000` in a browser. Use arrow keys, WASD, or the on-screen arrow buttons. Use **Reset room**, **Save hypothesis**, and **Next room** as you explore.

Optimus is an **AI agent execution platform running arkenOS**, not an ordinary local IDE. If Optimus supports executing Python and showing a preview of a local server, run the above commands there and open its port preview. We have **not validated** what networking/port-preview capabilities your Optimus deployment offers; there is no assumed Optimus-specific SDK in this prototype. If the platform does not expose port 8000, use the terminal mode:

```bash
python -m arcade.cli
```

You can override the default local bind/port with `ARCADE_HOST` and `ARCADE_PORT` environment variables. **Do not expose this prototype server on the public internet.** It has no authentication and in-memory sessions.

## Project structure

```text
hidden-rule-arcade/
├── arcade/
│   ├── engine.py      # Pure deterministic transitions + player observation function
│   ├── levels.py      # Private puzzle layouts
│   ├── solver.py      # Private BFS correctness oracle
│   ├── server.py      # Local HTTP UI, action API, and event logs
│   └── cli.py         # Terminal fallback
├── web/index.html     # Visual interface; no game rules in browser code
├── tests/             # Unit tests for transitions, solvability, logs
└── README.md
```

## Puzzle design

Players must reach the gold goal. There are colored circular tiles and striped barriers whose behavior is not explained. Three levels exercise the same rule family:

| Level | Role | Verified shortest successful movements |
|---|---|---:|
| `discovery` | Explore | 10 |
| `practice` | Apply discovered rule | 16 |
| `transfer` | Held-out layout prototype | 12 |

The **private** engine and solver know the mechanics. Optimal path lengths were calculated with breadth-first search over the complete state `(x, y, color, completed)`, and replay-validated. Invalid attempts do not count toward *successful-move* path length but do count toward attempts in research logging. The BFS oracle is not an AI baseline and should not be accessible to an evaluated agent.

## Player-facing JSON API

The same action interface can later be wrapped as tools for an Optimus agent. All endpoints are local and return JSON. The server owns private states and refuses invalid action names.

Start a session:

```bash
curl -s -X POST http://127.0.0.1:8000/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"level_id":"discovery","role":"ai","participant_id":"model_demo_01"}'
```

Save the returned `session_id` and supply it on subsequent calls:

```bash
curl -s -X POST http://127.0.0.1:8000/api/actions \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION_ID_HERE","action":"down"}'
```

Other endpoints:

- `GET /api/levels` — public level names and phases (not layouts/solutions).
- `POST /api/reset` — `{"session_id":"..."}`.
- `POST /api/explain` — `{"session_id":"...","explanation":"I think..."}`.

The action response contains an observation, a generic `feedback` (`moved`, `blocked`, or `completed`), and cumulative attempt statistics. It **does not** include the rule definition, solver, or private reason for a blocked action. `observe()` provides visual tile labels, a player position/color, and four available actions. Agent prompts/tool schemas must avoid presenting the internal Python files as context.

## Logs and reproducibility

The API and human interface both record events to `logs/events.jsonl`, created automatically on first use. Set `ARCADE_LOG` to use a different file. The `.gitignore` excludes logs from version control.

Each record has a UTC timestamp, `schema_version`, `session_id`, `participant_id`, `role` (human or ai), `level_id`, `phase`, `sequence`, `episode`, and an `event_type`:

- `session_start`: initial private state.
- `action`: attempted action, valid flag, generic outcome, private blocked reason, state before/after.
- `reset`: episode increment + fresh initial state.
- `explanation`: participant's ungraded free-text hypothesis and whether the room was already solved.

Private event logs should be accessible to researchers, **not participants or evaluated models**. Session identifiers are randomly generated. A reset preserves the session's cumulative statistics and starts a new episode. The same level and action sequence always produce the same outcomes; timestamps/session IDs can differ across runs.

## Test

```bash
python -m unittest discover -s tests -v
python -m arcade.solver
```

Tests check that every level has a solution, solver paths replay successfully, gates block correctly, pad behavior, walls, repeatability, observation filtering, counters, and event-log structure.

## Critical experimental limitations (not yet finished)

1. **Optimus/arkenOS tool integration is not implemented.** Only a local HTTP API is ready. We still need to check the actual tool schema and networking support for this deployment.
2. **Blindness isn't secured just by API response filtering.** If an AI agent can read this project directory, it could inspect `levels.py`, `engine.py`, `solver.py`, or JSONL logs. Controlled experiments need a separate, restricted agent runtime/container or strictly scoped server-side tools with no file read access.
3. **No enforced experimental sequence yet.** Users can choose any of the three levels, and hypothesis submission is not required before advancing. A pilot controller should enforce discovery → explanation/prediction → transfer and freeze held-out levels until ready.
4. **No scoring of explanations/predictions**, no agent policy, and no human-vs-AI results yet. Do not treat solver results as participant data.
5. Human input is visual and AI input is symbolic JSON. That modality difference must be documented when comparing conditions. Browser sessions and counters are memory-only; event logs persist.
6. Single-rule puzzle family and tiny sample. No claims of statistical evidence can be drawn from this prototype alone.

## Next milestone

Connect the Optimus agent with exactly three safe tools (`start_puzzle`, `observe`/action result, `take_action`) plus `submit_explanation`, enforce action budgets and test ordering, and measure held-out transfer with the same event schema.
