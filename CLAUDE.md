# CLAUDE.md

Standing brief for every Claude Code session working in this repo. Read this file in
full before writing any code. If something here conflicts with what you were asked in
chat, say so instead of silently picking one.

## Project purpose

This repo holds our team's AI agent for a 3-4 day hackathon built around a
capture-the-flag style game. The game's rules and API are published on day 1, so the
codebase is deliberately split so that the unknown parts (the wire protocol) are
quarantined in one module and the parts we can reason about (pathfinding, behavior
selection) stay pure and testable. Three people work in parallel, each owning different
files, so the highest priority after "the agent plays well" is that `main` is always in a
submittable state and that our three Claude Code sessions never produce conflicting or
inconsistently formatted code.

## Game Rules

> **TODO (day 1): fill this in the moment the rules are released.**

This section is the single source of truth for the game's rules. Nothing else in the repo
should restate them. Until it is filled in, **do not write game logic, agent logic,
scoring heuristics, pathfinding algorithms, or mock/simulated games** - we do not know the
rules yet and guessed logic is worse than none.

Once the rules drop, record here:

- Objective and win condition
- Map/board representation, coordinate system, and what a "tile" is
- Turn/tick model: is it turn-based or real-time, and what is the **time limit per
  decision**?
- Action space: every legal action and its cost/cooldown
- Observability: full map or fog of war? what does the agent actually see?
- Scoring, and any penalties (invalid action, timeout, crash)
- Match format for submission (how many games, against whom)

After this section is filled, every session must re-read it before continuing work.

## Architecture

Dependencies point one way only. A module may import from modules to its left, never to
its right.

```
adapter  ->  world  ->  pathfind / bt + strategy  ->  arena
```

| File | Responsibility | Must NOT contain |
|---|---|---|
| `agent/adapter.py` | The **only** module that knows the raw game API: endpoints, auth, wire/JSON format, serialization. Converts raw payloads into a `World` and converts our actions back into the API's format. | Any strategy, heuristics, or decision-making |
| `agent/world.py` | A clean, engine-agnostic game-state object. Plain dataclasses, our own vocabulary, no JSON keys, no network types. | Any I/O or knowledge of the API's field names |
| `agent/pathfind.py` | Pure pathfinding functions: `(world/grid, start, goal) -> path`. Deterministic, no I/O, no globals, no mutation of inputs. | Strategy decisions, randomness without a seed |
| `agent/bt.py` | Hand-written behavior tree primitives (node types, composites, tick semantics). Generic - knows nothing about our specific game. | Game-specific conditions or actions |
| `agent/strategy.py` | `decide(world) -> actions`. Our actual behavior tree, composed from `bt.py` nodes and `pathfind.py` functions. | Raw API formats, network calls |
| `arena.py` | Runs version-vs-version matches and reports win rate. Our only measure of "is this change better?" | Agent logic |

### `decide(world) -> actions`

`decide()` is the single entry point from the adapter into our brain. Its signature does
not change. It takes a `World` and returns actions in **our** vocabulary; translating
those into the API's format is `adapter.py`'s job.

## Rules

1. **Strategy never touches raw API format.** If `strategy.py`, `bt.py`, or `pathfind.py`
   contains a JSON key, a URL, or a field name copied from the API docs, that is a bug.
   Add the field to `World` instead.
2. **The adapter holds no strategy logic.** No "if health is low, retreat" in
   `adapter.py`. It translates, nothing else.
3. **Every new behavior gets a scenario test.** Construct a `World` by hand, call
   `decide()`, assert on the action. A behavior with no test does not merge.
4. **`decide()` must respect the game's time limit.** Keep a single module-level budget
   constant, check elapsed time inside any loop or search, and always return a legal
   action rather than overrunning. A timeout is worse than a mediocre move. Never write an
   unbounded search.
5. **Small, focused commits.** One concern per commit, imperative subject line
   ("add corridor pathfinding", not "updates"). If you cannot describe the commit in one
   line, split it.
6. **No dead code.** Delete failed experiments rather than commenting them out - that is
   what `experiments.md` and git history are for.
7. **Record every strategy change in `experiments.md`** with its arena result.

## Collaboration

Three people, three Claude Code sessions, one repo.

- **Never commit directly to `main`.** `main` must always be submittable.
- **One feature per branch**, named `<owner>/<topic>` - e.g. `io/adapter-auth`,
  `algo/astar`, `strategy/flag-capture`. Branch from an up-to-date `main`.
- **Every change reaches `main` through a PR** that passes CI.
- **Do not edit files owned by a teammate without coordinating.** Ownership lives in
  `.github/CODEOWNERS`:
  - **IO** - `agent/adapter.py`, `agent/world.py`, `arena.py`, `.github/`
  - **ALGO** - `agent/pathfind.py`
  - **STRATEGY** - `agent/bt.py`, `agent/strategy.py`
  If your change genuinely needs a teammate's file, say so in chat first and keep the edit
  to the minimum; better still, ask them to make it.
- **`CLAUDE.md` is shared.** Change it by agreement, not unilaterally.
- **`World` is the team's contract.** Adding a field to `agent/world.py` affects everyone -
  announce it before you change the shape of existing fields.
- Pull and rebase on `main` often. Long-lived branches cause exactly the conflicts this
  structure exists to prevent.

## Coding style

- **Python 3.12.** Pinned in `.python-version` and `pyproject.toml`.
- **ruff is authoritative** for both formatting and linting. Run `ruff format .` and
  `ruff check --fix .` (pre-commit does this automatically). Never hand-format code and
  never reformat a region you did not otherwise change - formatting noise hides real
  diffs. Do not add `# noqa` without a one-line reason next to it.
- **Type hints on every public function**, including the return type. Use built-in
  generics (`list[int]`, `dict[str, Position]`, `X | None`), not `typing.List`/`Optional`.
- **Naming:** `snake_case` for functions, variables, and modules; `PascalCase` for classes
  and dataclasses; `UPPER_SNAKE_CASE` for module-level constants; a leading underscore for
  module-private helpers.
- **Dataclasses over dicts** for structured state. If it has a fixed set of fields, it is
  a dataclass. Prefer `frozen=True` for anything treated as a value (positions, tiles).
- **Module docstring in every file**, stating that module's responsibility and boundary.
- **No magic numbers** in strategy code - name the constant.
- Line length 100. Tests live in `tests/`, named `test_<module>.py`.

## Running things

```bash
ruff format .        # format
ruff check --fix .   # lint
pytest -q            # tests
```

See `README.md` for first-time setup and `docs/day1-checklist.md` for the day 1 plan.
