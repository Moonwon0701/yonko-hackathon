# BT 재구성: 국면 = 이번 턴 과제 구성 (1단계 행동 유지) + 2단계 실험

- 날짜: 2026-09-28
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: (올린 뒤 번호 기록) (브랜치 `moonwon/bt-tasks`)

## 프롬프트 (원문 그대로)

1. > 우리 BT 구조에 대해서 설명해봐
2. > 잘 설계된 트리라고 할 수 있나
3. > 좀 너무 중구난방이라는 생각이 들어서 BT 구조로 다시 손보고 싶어. 너무 지금 따로 논다고 생각해. 다른 구조가 나을 것 같다면 추천해도 좋아. 이미 PR로 수정했던 내용이지만 만족스럽지 않네
4. > 1단계 부터 해보자
5. > 1,2,3 다 테스트 해봐

## 목적

- 기존 BT는 모양만 트리였다(1·2번 상담에서 진단). 국면 가지는 `Profile` 숫자 4개만 골라 국면마다 하는 일이
  트리에 보이지 않았고, 깃발병(건물)과 전투병(`Task`)의 목표 표현이 달랐고, 생산은 배정과 따로 공식으로 계산했으며,
  한 턴은 서로 모르는 함수 다섯 개를 차례로 부르는 `Sequence`였다.
- 3번 상담에서 LLM이 "BT는 유지하되 BT가 가중치 대신 이번 턴 과제 구성을 고르게" 하는 방향을 추천했고
  (순수 효용 AI·GOAP·HTN은 보고서 설명력·300 ms 제한·일정 때문에 비추천), 두 단계로 나눴다:
  1단계 구조만 바꾸고 행동은 그대로 → 2단계 행동 변경을 대전으로 검증. 이번 PR은 1단계.

## 범위 — LLM이 한 것

- `agent/strategy.py`
  - `Task`를 모든 과제의 공통 표현으로: `kind`(점령·처치·호위·지키기), `unit`(F/W), `building`, `stages` 추가
  - `Profile`·`PROFILES`·`PHASE_ORDER` 삭제. 국면 가지 = [Latch 조건] → [국면 기록] → 과제 구성 잎
    (`capture`·`kill`·`escort`·`guard`·`warriors`). 잎이 `Turn.makers`에 과제 만들기 함수를 넣고, 가중치는 노드 이름에 드러낸다
  - 과제 만들기 함수 `capture_tasks`·`kill_tasks`·`escort_tasks`·`guard_tasks`(기존 `assign`의 가치 계산과
    `warrior_tasks`·`guard_tasks`를 옮김), 깃발병 배정기 `assign` → `assign_flags`(점령 과제를 받음)
  - 한 턴의 단계를 의존 순서대로 나눔: `plan_flags` → `reserve_capture_cost` → `plan_warrior_tasks` → `produce` →
    `plan_warriors` → `move_warriors` → `replan_flags` → `move_flags` → `set_priority`
  - `select_phase`(테스트용)가 과제 구성 잎을 위한 칸을 함께 만든다
- `docs/roadmap.md`: M3 절에 "구조 정리 2" 추가(바뀐 트리, 검증 수치, 2단계 할 일)

## 사람이 한 것

- 기존 BT가 "중구난방이고 따로 논다"고 문제를 제기하고, 다른 구조 추천도 열어 둠
- 추천안(과제 통일 BT) 중 1단계(행동 유지 재구성)부터 진행하기로 결정

## 검증

- `python -m sim diff . git:main --vs <상대> --seeds 100`: 상대 5종(main, starter lv1, lv2, M3 `c561771`,
  M4 `f564d8b`) 1,000경기, A가 둔 약 98,000턴의 명령이 모두 같음(달라진 경기 0)
- `python -m sim arena . git:main --seeds 30`: 60경기 모두 무승부, 최대 응답 12 ms(main 13 ms)
- 전체 테스트 791 통과, 실패 10개는 main과 동일(커밋 안 한 리더보드 리플레이 9, `devtool` 누락 1 — 이번 변경과 무관)
- `scripts/build_submission.py` 스모크 테스트: 160턴 모두 END, 턴 계산 최대 2.8 ms

## 이어서: 2단계 실험 (5번 프롬프트, 모두 반영 안 함)

- LLM이 한 것: 실험 봇을 저장소 밖(세션 임시 폴더)에 변형별로 만들어 대전. 저장소 코드는 바꾸지 않음.
  `docs/benchmarks.md`에 결과 7줄, `docs/roadmap.md` M3 "구조 정리 2"에 결론 추가
  - 국면 분포 측정: THREAT 84~94%(lv2 상대 52%)
  - 3번 THREAT 조건: 끄기 44%, 우리 점수 대비 0.25 → 51% / 0.4 → 52%·49.5%(다른 시드), 막고 있는 건물 빼기 44%
  - 2번 생산 = 배정 부족분: 35%, 기존 규칙 + 부족분 41%
  - 1번 국면별 과제 구성: THREAT에서 상대 건물 점령 끄기 0%, 드문 국면 구성 바꾸기 51.5%(거의 같은 경기),
    THREAT 조건 0.4와 함께 47%·37%
- 결론: 모두 `main`보다 낫지 않아 반영하지 않음. 1단계 구조만 남긴다
- 사람이 한 것: 세 가지를 모두 시험하라고 결정

### 검증

- 변형마다 `python -m sim arena <변형> git:main --seeds 100`(200경기), 후보는 다른 시드 100~199와 M4·M3 상대로 다시 확인
- 기준: 같은 조건에서 지금 봇은 M4 상대 71%, M3 상대 92%
