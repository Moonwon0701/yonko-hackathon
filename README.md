# yonko-hackathon

Our team's AI agent for a capture-the-flag style hackathon game. The game's rules and API
are released on day 1; until then this repo contains only the shared environment -
structure, tooling and conventions - with no game logic.

캡처 더 플래그(CTF) 형식의 해커톤 게임을 위한 우리 팀 AI 에이전트입니다. 게임 규칙과 API는
1일차에 공개되며, 그 전까지 이 저장소에는 공용 환경(구조, 도구, 규약)만 있고 게임 로직은
없습니다.

**Read [`CLAUDE.md`](CLAUDE.md) before writing any code.** It is the team brief: the layer
boundaries, the rules, file ownership, and the coding style. Every Claude Code session in
this repo is expected to follow it.

**코드를 쓰기 전에 [`CLAUDE.md`](CLAUDE.md)를 먼저 읽으세요.** 계층 경계, 규칙, 파일 소유권,
코딩 스타일이 담긴 팀 지침서이며, 이 저장소의 모든 Claude Code 세션이 이를 따릅니다.

## Setup / 환경 설정

Python **3.12** (pinned in `.python-version`).
Python **3.12**을 사용합니다(`.python-version`에 고정).

```bash
git clone https://github.com/Moonwon0701/yonko-hackathon.git
cd yonko-hackathon
```

Create and activate a virtual environment: / 가상환경을 만들고 활성화합니다:

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
>
> 윈도우에서는 그냥 `python`을 치면 Python이 실행되는 대신 Microsoft Store가 열릴 수 있습니다.
> 가상환경을 만들 때는 `py -3.12`를 쓰고, 활성화한 뒤에는 venv 안의 `python`을 써도 됩니다.

Install the project and the dev tools, then install the git hooks:

프로젝트와 개발 도구를 설치한 뒤 git 훅을 설치합니다:

```bash
pip install -e ".[dev]"
pre-commit install
```

`pre-commit install` is not optional - it is what makes all three of our machines format
code identically. Without it your PRs will fail CI on formatting.

`pre-commit install`은 선택이 아닙니다. 세 사람의 컴퓨터가 코드를 똑같은 서식으로 만들어 주는
장치이며, 하지 않으면 PR이 서식 때문에 CI에서 떨어집니다.

## Everyday commands / 자주 쓰는 명령

```bash
pytest                       # run the tests / 테스트 실행
ruff format .                # format / 서식 정리
ruff check --fix .           # lint and autofix / 린트 및 자동 수정
pre-commit run --all-files   # everything the hooks would do / 훅이 하는 모든 검사
```

## Workflow / 작업 흐름

`main` must always be submittable. Nothing is committed to it directly - every change goes
through a PR. This is a team convention right now, not an enforced branch protection rule,
so it holds only as long as all three of us keep to it.

`main`은 항상 제출 가능한 상태여야 합니다. 여기에 직접 커밋하지 않고 모든 변경은 PR을 거칩니다.
현재 이것은 GitHub가 강제하는 브랜치 보호 규칙이 아니라 팀 내부 규약이므로, 세 사람이 지켜야만
유지됩니다.

```bash
git switch main && git pull
git switch -c <owner>/<topic>     # e.g. algo/astar
# ... work, commit in small focused steps ...
# ... 작업하고, 작고 집중된 단위로 커밋 ...
git push -u origin <owner>/<topic>
gh pr create                      # fills in the PR template / PR 템플릿이 채워집니다
```

CI runs `ruff format --check`, `ruff check`, `mdformat --check` and `pytest` on every PR;
all of them must pass before merging. Reviewers are auto-requested from
`.github/CODEOWNERS`.

CI는 모든 PR에서 `ruff format --check`, `ruff check`, `mdformat --check`, `pytest`를
실행하며, 전부 통과해야 머지할 수 있습니다. 리뷰어는 `.github/CODEOWNERS`에 따라 자동
지정됩니다.

**New to this loop?** [`docs/workflow.md`](docs/workflow.md) walks through one change from
branch to merge, and what to do when CI goes red or a merge conflicts.

**이 방식이 처음이라면** [`docs/workflow.md`](docs/workflow.md)에 브랜치부터 머지까지 한
바퀴가 단계별로 적혀 있고, CI가 빨간불이거나 충돌이 났을 때의 대처법도 있습니다.

## Layout / 구조

| Path / 경로              | Contents / 내용                                                                        |
| ------------------------ | -------------------------------------------------------------------------------------- |
| `agent/adapter.py`       | The only module that knows the raw game API<br>원시 게임 API를 아는 유일한 모듈        |
| `agent/world.py`         | Clean, engine-agnostic game state<br>엔진에 종속되지 않는 깔끔한 게임 상태             |
| `agent/pathfind.py`      | Pure pathfinding functions<br>순수한 경로 탐색 함수                                    |
| `agent/bt.py`            | Hand-written behavior tree primitives<br>직접 작성한 행동 트리 기본 요소               |
| `agent/strategy.py`      | `decide(world) -> actions`                                                             |
| `arena.py`               | Version-vs-version win rate<br>버전 대 버전 승률 측정                                  |
| `tests/`                 | Scenario tests<br>시나리오 테스트                                                      |
| `docs/workflow.md`       | How a change goes from idea to `main`<br>변경 하나가 `main`까지 가는 과정              |
| `docs/day1-checklist.md` | What we do the moment the rules drop<br>규칙이 공개되는 순간 해야 할 일                |
| `experiments.md`         | Log of every strategy change and its arena result<br>모든 전략 변경과 아레나 결과 기록 |
