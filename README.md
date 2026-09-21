# yonko-hackathon

Our team's AI agent for a capture-the-flag style hackathon game. The game's rules and API
are released on day 1; until then this repo contains only the shared environment -
structure, tooling and conventions - with no game logic.

**Read [`CLAUDE.md`](CLAUDE.md) before writing any code.** It is the team brief: the layer
boundaries, the rules, file ownership, and the coding style. Every Claude Code session in
this repo is expected to follow it.

## Setup

Python **3.12** (pinned in `.python-version`).

```bash
git clone https://github.com/Moonwon0701/yonko-hackathon.git
cd yonko-hackathon
```

Create and activate a virtual environment:

```powershell
# Windows / PowerShell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
python3.12 -m venv .venv
source .venv/bin/activate
```

> On Windows, a bare `python` may open the Microsoft Store instead of running Python.
> Use `py -3.12` to create the venv; after activating, `python` inside the venv is fine.

Install the project and the dev tools, then install the git hooks:

```bash
pip install -e ".[dev]"
pre-commit install
```

`pre-commit install` is not optional - it is what makes all three of our machines format
code identically. Without it your PRs will fail CI on formatting.

## Everyday commands

```bash
pytest               # run the tests
ruff format .        # format
ruff check --fix .   # lint and autofix
pre-commit run --all-files   # everything the hooks would do
```

## Workflow

`main` is protected and must always be submittable. Nothing is committed to it directly.

```bash
git switch main && git pull
git switch -c <owner>/<topic>     # e.g. algo/astar
# ... work, commit in small focused steps ...
git push -u origin <owner>/<topic>
gh pr create                      # fills in the PR template
```

CI runs `ruff format --check`, `ruff check` and `pytest` on every PR; all three must pass
before merging. Reviewers are auto-requested from `.github/CODEOWNERS`.

## Layout

| Path | Contents |
|---|---|
| `agent/adapter.py` | The only module that knows the raw game API |
| `agent/world.py` | Clean, engine-agnostic game state |
| `agent/pathfind.py` | Pure pathfinding functions |
| `agent/bt.py` | Hand-written behavior tree primitives |
| `agent/strategy.py` | `decide(world) -> actions` |
| `arena.py` | Version-vs-version win rate |
| `tests/` | Scenario tests |
| `docs/day1-checklist.md` | What we do the moment the rules drop |
| `experiments.md` | Log of every strategy change and its arena result |
