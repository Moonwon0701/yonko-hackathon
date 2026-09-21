## What changed / 무엇을 바꿨나

<!-- One or two sentences. Which layer does this touch, and why?
     한두 문장으로. 어느 계층을 건드렸고, 왜 그랬는지. -->

## How tested / 어떻게 테스트했나

<!-- Commands you ran and what they showed. Every new behavior needs a scenario test
     (CLAUDE.md > Rules).
     실행한 명령과 그 결과. 새로운 행동에는 반드시 시나리오 테스트가 필요합니다
     (CLAUDE.md의 Rules 절). -->

- [ ] `ruff format .` and `ruff check .` clean / 서식·린트 통과
- [ ] `pytest` passes / 테스트 통과
- [ ] New/updated scenario test covering this behavior / 이 행동을 덮는 시나리오 테스트 추가·수정
      — or N/A because / 또는 해당 없음, 이유:

## Arena result vs main / main 대비 아레나 결과

<!-- Win rate of this branch against main, and over how many games.
     이 브랜치가 main을 상대로 몇 판에서 몇 퍼센트 승률을 냈는지. -->

| | |
|---|---|
| Games played / 경기 수 | |
| Win rate vs `main` / `main` 대비 승률 | |
| Verdict / 판정 | keep / revert / needs more games<br>채택 / 되돌림 / 더 돌려봐야 함 |

- [ ] Logged in `experiments.md` / `experiments.md`에 기록함
- [ ] Not applicable (no behavior change — docs/tooling/refactor only) / 해당 없음(행동 변화
      없음 — 문서·도구·리팩터링만), because / 이유:

## Checklist / 점검 목록

- [ ] Stays inside my layer's boundary (CLAUDE.md > Architecture)
      / 내 계층의 경계를 벗어나지 않음 (CLAUDE.md의 Architecture 절)
- [ ] No files owned by a teammate touched without coordinating
      / 조율 없이 팀원 소유 파일을 건드리지 않음
- [ ] `main` stays submittable if this merges
      / 이 PR이 머지되어도 `main`은 제출 가능한 상태로 유지됨
