# CLAUDE.md

Standing brief for every Claude Code session working in this repo. Read this file in
full before writing any code. If something here conflicts with what you were asked in
chat, say so instead of silently picking one.

이 저장소에서 작업하는 모든 Claude Code 세션을 위한 기본 지침서입니다. 코드를 한 줄이라도 쓰기
전에 이 파일을 끝까지 읽으세요. 여기 적힌 내용과 채팅으로 받은 지시가 충돌하면, 조용히 하나를
골라 진행하지 말고 충돌한다는 사실을 먼저 말하세요.

> This file is bilingual on purpose: English first, Korean directly below it. Both say the
> same thing - if you change one, change the other in the same commit.
>
> 이 파일은 의도적으로 이중 언어로 작성되었습니다. 영어가 먼저, 바로 아래에 한국어입니다. 둘은
> 같은 내용이므로 한쪽을 고치면 같은 커밋에서 다른 쪽도 고치세요.

## Project purpose / 프로젝트 목적

This repo holds our team's AI agent for a 3-4 day hackathon built around a
capture-the-flag style game. The game's rules and API are published on day 1, so the
codebase is deliberately split so that the unknown parts (the wire protocol) are
quarantined in one module and the parts we can reason about (pathfinding, behavior
selection) stay pure and testable. Three people work in parallel, each owning different
files, so the highest priority after "the agent plays well" is that `main` is always in a
submittable state and that our three Claude Code sessions never produce conflicting or
inconsistently formatted code.

이 저장소는 캡처 더 플래그(CTF) 형식의 게임을 다루는 3~4일짜리 해커톤용 팀 AI 에이전트를 담고
있습니다. 게임 규칙과 API는 1일차에 공개되므로, 알 수 없는 부분(통신 프로토콜)은 한 모듈에
격리하고 미리 다룰 수 있는 부분(경로 탐색, 행동 선택)은 순수하고 테스트 가능하게 유지하도록
코드베이스를 의도적으로 분리했습니다. 세 명이 서로 다른 파일을 맡아 동시에 작업하므로,
"에이전트가 잘 플레이한다" 다음으로 중요한 목표는 `main`이 항상 제출 가능한 상태를 유지하는
것과, 세 개의 Claude Code 세션이 서로 충돌하거나 서식이 제각각인 코드를 만들어내지 않는
것입니다.

## Game Rules / 게임 규칙

> **TODO (day 1): fill this in the moment the rules are released.**
>
> **TODO (1일차): 규칙이 공개되는 즉시 이 절을 채울 것.**

This section is the single source of truth for the game's rules. Nothing else in the repo
should restate them. Until it is filled in, **do not write game logic, agent logic,
scoring heuristics, pathfinding algorithms, or mock/simulated games** - we do not know the
rules yet and guessed logic is worse than none.

이 절이 게임 규칙에 대한 유일한 기준입니다. 저장소의 다른 어떤 문서도 규칙을 따로 옮겨 적지
마세요. 이 절이 채워지기 전까지는 **게임 로직, 에이전트 로직, 점수 휴리스틱, 경로 탐색 알고리즘,
가짜/모의 게임을 작성하지 마세요.** 아직 규칙을 모르는 상태이고, 추측으로 쓴 로직은 아예 없는
것보다 나쁩니다.

Once the rules drop, record here: / 규칙이 공개되면 여기에 다음을 기록하세요:

- Objective and win condition
  / 목표와 승리 조건
- Map/board representation, coordinate system, and what a "tile" is
  / 맵·보드 표현 방식, 좌표계, "타일"의 정의
- Turn/tick model: is it turn-based or real-time, and what is the **time limit per
  decision**?
  / 턴·틱 모델: 턴제인가 실시간인가, 그리고 **한 번의 판단에 허용되는 시간 제한**은 얼마인가?
- Action space: every legal action and its cost/cooldown
  / 행동 공간: 가능한 모든 합법적 행동과 각각의 비용·쿨다운
- Observability: full map or fog of war? what does the agent actually see?
  / 관측 범위: 전체 맵인가 전장의 안개인가? 에이전트가 실제로 볼 수 있는 것은 무엇인가?
- Scoring, and any penalties (invalid action, timeout, crash)
  / 점수 계산과 페널티(잘못된 행동, 시간 초과, 크래시)
- Match format for submission (how many games, against whom)
  / 제출 시 경기 형식(몇 판을, 누구를 상대로)

After this section is filled, every session must re-read it before continuing work.

이 절이 채워진 뒤에는, 모든 세션이 작업을 이어가기 전에 이 파일을 다시 읽어야 합니다.

## Architecture / 아키텍처

Dependencies point one way only. A module may import from modules to its left, never to
its right.

의존성은 한 방향으로만 흐릅니다. 각 모듈은 자기 왼쪽에 있는 모듈만 import할 수 있고, 오른쪽은
절대 import할 수 없습니다.

```
adapter  ->  world  ->  pathfind / bt + strategy  ->  arena
```

| File / 파일 | Responsibility / 책임 | Must NOT contain / 들어가면 안 되는 것 |
|---|---|---|
| `agent/adapter.py` | The **only** module that knows the raw game API: endpoints, auth, wire/JSON format, serialization. Converts raw payloads into a `World` and converts our actions back into the API's format.<br><br>원시 게임 API를 아는 **유일한** 모듈. 엔드포인트, 인증, 통신·JSON 형식, 직렬화를 담당. 원시 페이로드를 `World`로 바꾸고, 우리 행동을 다시 API 형식으로 되돌림. | Any strategy, heuristics, or decision-making<br><br>전략, 휴리스틱, 의사결정 일체 |
| `agent/world.py` | A clean, engine-agnostic game-state object. Plain dataclasses, our own vocabulary, no JSON keys, no network types.<br><br>엔진에 종속되지 않는 깔끔한 게임 상태 객체. 평범한 dataclass, 우리만의 용어, JSON 키나 네트워크 타입 없음. | Any I/O or knowledge of the API's field names<br><br>모든 I/O, API 필드명에 대한 지식 |
| `agent/pathfind.py` | Pure pathfinding functions: `(world/grid, start, goal) -> path`. Deterministic, no I/O, no globals, no mutation of inputs.<br><br>순수한 경로 탐색 함수. 결정적이며 I/O·전역 변수·입력 변형이 없음. | Strategy decisions, randomness without a seed<br><br>전략적 판단, 시드 없는 난수 |
| `agent/bt.py` | Hand-written behavior tree primitives (node types, composites, tick semantics). Generic - knows nothing about our specific game.<br><br>직접 작성한 행동 트리 기본 요소(노드 종류, 조합 노드, 틱 동작). 범용이며 우리 게임을 전혀 모름. | Game-specific conditions or actions<br><br>게임에 특화된 조건이나 행동 |
| `agent/strategy.py` | `decide(world) -> actions`. Our actual behavior tree, composed from `bt.py` nodes and `pathfind.py` functions.<br><br>`decide(world) -> actions`. `bt.py`의 노드와 `pathfind.py`의 함수로 조립한 실제 행동 트리. | Raw API formats, network calls<br><br>원시 API 형식, 네트워크 호출 |
| `arena.py` | Runs version-vs-version matches and reports win rate. Our only measure of "is this change better?"<br><br>버전 대 버전 대전을 돌려 승률을 보고. "이 변경이 정말 나은가?"를 판단하는 유일한 척도. | Agent logic<br><br>에이전트 로직 |

### `decide(world) -> actions`

`decide()` is the single entry point from the adapter into our brain. Its signature does
not change. It takes a `World` and returns actions in **our** vocabulary; translating
those into the API's format is the adapter's job.

`decide()`는 어댑터에서 우리 두뇌로 들어오는 유일한 진입점입니다. 이 시그니처는 바뀌지 않습니다.
`World`를 받아 **우리** 용어로 된 행동을 반환하며, 그것을 API 형식으로 번역하는 일은 어댑터의
몫입니다.

## Rules / 규칙

1. **Strategy never touches raw API format.** If `strategy.py`, `bt.py`, or `pathfind.py`
   contains a JSON key, a URL, or a field name copied from the API docs, that is a bug.
   Add the field to `World` instead.

   **전략은 원시 API 형식을 절대 건드리지 않습니다.** `strategy.py`, `bt.py`, `pathfind.py`에
   JSON 키, URL, API 문서에서 복사한 필드명이 들어 있다면 그건 버그입니다. 대신 `World`에
   필드를 추가하세요.

2. **The adapter holds no strategy logic.** No "if health is low, retreat" in
   `adapter.py`. It translates, nothing else.

   **어댑터에는 전략 로직이 없습니다.** `adapter.py`에 "체력이 낮으면 후퇴" 같은 코드를 두지
   마세요. 어댑터는 번역만 합니다.

3. **Every new behavior gets a scenario test.** Construct a `World` by hand, call
   `decide()`, assert on the action. A behavior with no test does not merge.

   **새로운 행동에는 반드시 시나리오 테스트를 붙입니다.** `World`를 손으로 만들고 `decide()`를
   호출해 반환된 행동을 단언하세요. 테스트 없는 행동은 머지하지 않습니다.

4. **`decide()` must respect the game's time limit.** Keep a single module-level budget
   constant, check elapsed time inside any loop or search, and always return a legal
   action rather than overrunning. A timeout is worse than a mediocre move. Never write an
   unbounded search.

   **`decide()`는 게임의 시간 제한을 반드시 지켜야 합니다.** 모듈 수준에 예산 상수를 하나 두고,
   모든 루프와 탐색 안에서 경과 시간을 확인하며, 시간을 넘기느니 합법적인 행동을 반환하세요.
   시간 초과는 평범한 수보다 나쁩니다. 상한 없는 탐색은 절대 작성하지 마세요.

5. **Small, focused commits.** One concern per commit, imperative subject line
   ("add corridor pathfinding", not "updates"). If you cannot describe the commit in one
   line, split it.

   **작고 집중된 커밋.** 커밋 하나에 관심사 하나, 제목은 명령형으로("updates"가 아니라
   "add corridor pathfinding"). 한 줄로 설명할 수 없는 커밋이라면 쪼개세요.

6. **No dead code.** Delete failed experiments rather than commenting them out - that is
   what `experiments.md` and git history are for.

   **죽은 코드 금지.** 실패한 실험은 주석 처리하지 말고 삭제하세요. 그러라고 `experiments.md`와
   git 히스토리가 있습니다.

7. **Record every strategy change in `experiments.md`** with its arena result.

   **모든 전략 변경은 아레나 결과와 함께 `experiments.md`에 기록**하세요.

## Collaboration / 협업

Three people, three Claude Code sessions, one repo.

세 사람, 세 개의 Claude Code 세션, 하나의 저장소.

- **Never commit directly to `main`.** `main` must always be submittable.

  **`main`에 직접 커밋하지 마세요.** `main`은 항상 제출 가능한 상태여야 합니다.

- **One feature per branch**, named `<owner>/<topic>` - e.g. `io/adapter-auth`,
  `algo/astar`, `strategy/flag-capture`. Branch from an up-to-date `main`.

  **브랜치 하나에 기능 하나**, 이름은 `<owner>/<topic>` 형식(예: `io/adapter-auth`,
  `algo/astar`, `strategy/flag-capture`). 항상 최신 `main`에서 분기하세요.

- **Every change reaches `main` through a PR** that passes CI.

  **모든 변경은 CI를 통과한 PR을 거쳐** `main`에 들어갑니다.

- **Do not edit files owned by a teammate without coordinating.** Ownership lives in
  `.github/CODEOWNERS`:

  **팀원이 소유한 파일을 조율 없이 수정하지 마세요.** 소유권은 `.github/CODEOWNERS`에 정의되어
  있습니다:

  - **IO** - `agent/adapter.py`, `agent/world.py`, `arena.py`, `.github/`
  - **ALGO** - `agent/pathfind.py`
  - **STRATEGY** - `agent/bt.py`, `agent/strategy.py`

  If your change genuinely needs a teammate's file, say so in chat first and keep the edit
  to the minimum; better still, ask them to make it.

  정말로 팀원의 파일을 건드려야 한다면 먼저 팀 채팅에 알리고 수정은 최소한으로 하세요. 가능하면
  그 사람에게 직접 수정해 달라고 부탁하는 편이 더 낫습니다.

- **`CLAUDE.md` is shared.** Change it by agreement, not unilaterally.

  **`CLAUDE.md`는 공동 소유입니다.** 독단이 아니라 합의로 고치세요.

- **`World` is the team's contract.** Adding a field to `agent/world.py` affects everyone -
  announce it before you change the shape of existing fields.

  **`World`는 팀의 계약입니다.** `agent/world.py`에 필드를 추가하면 모두에게 영향이 갑니다. 기존
  필드의 형태를 바꾸기 전에는 반드시 공지하세요.

- Pull and rebase on `main` often. Long-lived branches cause exactly the conflicts this
  structure exists to prevent.

  `main`을 자주 pull하고 rebase하세요. 오래 묵은 브랜치는 이 구조가 막으려는 바로 그 충돌을
  일으킵니다.

## Coding style / 코딩 스타일

- **Python 3.12.** Pinned in `.python-version` and `pyproject.toml`.

  **Python 3.12.** `.python-version`과 `pyproject.toml`에 고정되어 있습니다.

- **ruff is authoritative** for both formatting and linting. Run `ruff format .` and
  `ruff check --fix .` (pre-commit does this automatically). Never hand-format code and
  never reformat a region you did not otherwise change - formatting noise hides real
  diffs. Do not add `# noqa` without a one-line reason next to it.

  **서식과 린트는 ruff가 기준입니다.** `ruff format .`과 `ruff check --fix .`를 사용하세요
  (pre-commit이 자동으로 실행합니다). 손으로 서식을 맞추지 말고, 어차피 건드릴 일 없는 영역을
  재포맷하지 마세요. 서식 잡음은 진짜 변경 사항을 가립니다. `# noqa`를 붙일 때는 바로 옆에 한
  줄짜리 이유를 반드시 적으세요.

- **Type hints on every public function**, including the return type. Use built-in
  generics (`list[int]`, `dict[str, Position]`, `X | None`), not `typing.List`/`Optional`.

  **모든 공개 함수에 타입 힌트**를 반환 타입까지 붙이세요. `typing.List`나 `Optional` 대신 내장
  제네릭(`list[int]`, `dict[str, Position]`, `X | None`)을 사용하세요.

- **Naming:** `snake_case` for functions, variables, and modules; `PascalCase` for classes
  and dataclasses; `UPPER_SNAKE_CASE` for module-level constants; a leading underscore for
  module-private helpers.

  **명명 규칙:** 함수·변수·모듈은 `snake_case`, 클래스와 dataclass는 `PascalCase`, 모듈 수준
  상수는 `UPPER_SNAKE_CASE`, 모듈 내부 전용 헬퍼는 밑줄로 시작.

- **Dataclasses over dicts** for structured state. If it has a fixed set of fields, it is
  a dataclass. Prefer `frozen=True` for anything treated as a value (positions, tiles).

  구조화된 상태에는 **dict 대신 dataclass**를 쓰세요. 필드 집합이 고정되어 있다면 dataclass가
  맞습니다. 값처럼 다루는 것(좌표, 타일)은 `frozen=True`를 권장합니다.

- **Module docstring in every file**, stating that module's responsibility and boundary.

  **모든 파일에 모듈 독스트링**을 두고, 그 모듈의 책임과 경계를 적으세요.

- **No magic numbers** in strategy code - name the constant.

  전략 코드에 **매직 넘버 금지** - 상수에 이름을 붙이세요.

- Line length 100. Tests live in `tests/`, named `test_<module>.py`.

  줄 길이는 100자. 테스트는 `tests/`에 `test_<module>.py` 이름으로 둡니다.

## Running things / 실행 명령

```bash
ruff format .        # format / 서식 정리
ruff check --fix .   # lint / 린트
pytest -q            # tests / 테스트
```

See `README.md` for first-time setup and `docs/day1-checklist.md` for the day 1 plan.

최초 환경 설정은 `README.md`, 1일차 계획은 `docs/day1-checklist.md`를 보세요.
