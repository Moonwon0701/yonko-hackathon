# Day 1 checklist / 1일차 체크리스트

The order matters. The goal of day 1 is not a clever agent - it is a **submittable** one,
plus a shared understanding of the rules and a way to measure changes.

순서가 중요합니다. 1일차의 목표는 똑똑한 에이전트가 아니라 **제출 가능한** 에이전트, 그리고
규칙에 대한 공통 이해와 변경을 측정할 수단을 확보하는 것입니다.

## 1. Read the rules together / 규칙을 함께 읽기

- [ ] All three of us read the published rules and API docs end to end.
  / 세 명 모두 공개된 규칙과 API 문서를 처음부터 끝까지 읽습니다.
- [ ] Talk through anything ambiguous *before* writing code. Disagreements about the rules
  are much cheaper now than after three sessions have built on them.
  / 애매한 부분은 코드를 쓰기 *전에* 이야기해 정리합니다. 규칙에 대한 이견은 세 세션이 그
  위에 코드를 쌓은 뒤보다 지금 해결하는 편이 훨씬 쌉니다.
- [ ] Note the hard constraints explicitly: **per-decision time limit**, action legality,
  submission format, and the penalty for a timeout or an invalid action.
  / 확실한 제약을 명시적으로 적어 둡니다: **판단 1회당 시간 제한**, 행동의 합법성, 제출
  형식, 시간 초과나 잘못된 행동에 대한 페널티.

## 2. Fill in `## Game Rules` in `CLAUDE.md` / `CLAUDE.md`의 게임 규칙 채우기

- [ ] Write the rules into the `## Game Rules` section of `CLAUDE.md`, using the checklist
  already in that section.
  / `CLAUDE.md`의 `## Game Rules` 절에 이미 들어 있는 체크리스트를 따라 규칙을 적습니다.
- [ ] **Merge this first, before any other work.** It is the one file every Claude Code
  session reads, so all three sessions must be working from the same filled-in copy.
  / **다른 어떤 작업보다 이것을 먼저 머지합니다.** 모든 Claude Code 세션이 읽는 유일한
  파일이므로, 세 세션 모두 같은 내용으로 채워진 사본을 보고 있어야 합니다.
- [ ] Everyone pulls and re-reads `CLAUDE.md` after it lands.
  / 머지된 뒤에는 모두가 pull 받아 `CLAUDE.md`를 다시 읽습니다.

## 3. Implement the adapter / 어댑터 구현

- [ ] IO implements `agent/adapter.py` against the real API: connect, authenticate, fetch
  state, send an action.
  / IO 담당이 실제 API에 맞춰 `agent/adapter.py`를 구현합니다: 접속, 인증, 상태 조회,
  행동 전송.
- [ ] Define `agent/world.py` alongside it - our own vocabulary, no API field names.
  Announce the shape to the team; it is the contract everything else builds on.
  / 함께 `agent/world.py`를 정의합니다. API 필드명이 아니라 우리 용어로 씁니다. 그 형태를
  팀에 공유하세요. 나머지 모든 코드가 이 계약 위에 세워집니다.
- [ ] Prove a full round trip: raw payload -> `World` -> action -> accepted by the API.
  / 전체 왕복을 확인합니다: 원시 페이로드 -> `World` -> 행동 -> API가 수락.

## 4. Get a minimal submittable agent onto `main` / 최소 제출 가능 에이전트를 `main`에 올리기

- [ ] `decide(world)` returns *some* legal action - random or trivially greedy is fine.
  / `decide(world)`가 *아무거나* 합법적인 행동을 반환하게 합니다. 무작위나 단순 탐욕도
  괜찮습니다.
- [ ] Play one complete game without crashing, without an invalid action, and inside the
  time limit.
  / 크래시 없이, 잘못된 행동 없이, 시간 제한 안에서 한 판을 끝까지 플레이합니다.
- [ ] Merge it. From this point on we always have something to submit, and every later
  change is an improvement on a known-working baseline rather than a gamble.
  / 머지합니다. 이 시점부터는 언제나 제출할 것이 있고, 이후의 모든 변경은 도박이 아니라
  동작이 확인된 기준선을 개선하는 일이 됩니다.

## 5. Stand up the arena / 아레나 구축

- [ ] IO implements `arena.py`: run N matches between two versions, report win rate.
  / IO 담당이 `arena.py`를 구현합니다: 두 버전 간 N판을 돌려 승률을 보고.
- [ ] Record the baseline agent's result as the first row of `experiments.md`.
  / 기준 에이전트의 결과를 `experiments.md`의 첫 행으로 기록합니다.
- [ ] From here, no strategy change merges on vibes - it merges on an arena result.
  / 이후로 전략 변경은 감으로 머지하지 않고 아레나 결과로 머지합니다.

## 6. Split the work by ownership / 소유권에 따라 업무 분담

- [ ] Fill the real GitHub handles into `.github/CODEOWNERS`.
  / `.github/CODEOWNERS`에 실제 GitHub 계정을 채워 넣습니다.

- [ ] Work in parallel along the ownership lines:
  / 소유권 경계를 따라 병렬로 작업합니다:

  - **IO** - adapter, world, arena, CI
  - **ALGO** - pathfinding / 경로 탐색
  - **STRATEGY** - behavior tree and the agent's behavior / 행동 트리와 에이전트의 행동

- [ ] One feature per branch, PR into `main`, CI green before merge.
  / 브랜치 하나에 기능 하나, `main`으로 PR, CI 통과 후 머지.

- [ ] Agree on a re-sync point (e.g. end of day) to review what landed and pick the next
  targets together.
  / 다시 모일 시점(예: 하루 마무리)을 정해 머지된 내용을 함께 점검하고 다음 목표를
  정합니다.
