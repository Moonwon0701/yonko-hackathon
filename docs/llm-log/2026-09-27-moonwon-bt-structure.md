# 전략 구조를 행동 트리(BT)로 통일 (행동은 그대로)

- 날짜: 2026-09-27
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: #33 (브랜치 `moonwon/bt-structure`)

## 프롬프트 (원문 그대로)

1. > 32 머지 했어. 우선 궁금한 점은  지금 구조가 BT가 맞는지야. 상태 머신에 좀 더 가깝지 않아?
2. > 그러면 전반적인 코드에서도 BT와 상태머신을 혼용한 것 같으니 둘중에 하나로 대폭 수정하자. BT가 낫겠어 아니면 상태머신이 낫겠어. 앞으로의 발전도 고려해
3. > 응 1번부터 시작해.

(1번 질문에 LLM은 "위층은 히스테리시스가 있는 우선순위 상태 머신이고, BT의 특징(트리 계층, 성공·실패 반환,
대체 가지)은 없다"고 답했다. 2번에 BT를 추천했고, 1번 = "행동을 바꾸지 않는 구조 변경" PR이다.)

## 목적

- 이름만 BT이던 국면 선택(상태 머신)과, if-else로 적힌 BT 모양의 깃발병 이동을 하나의 BT로 통일한다
- 앞으로 중반 대응을 가지로 추가하기 쉽게 하고, 보고서에 판단 트리를 그대로 옮길 수 있게 한다

## 범위 — LLM이 한 것

- `agent/strategy.py`
  - BT 뼈대: `Selector`, `Sequence`, `Condition`, `Act`, `Latch`(예전 히스테리시스), `tree_text()`
  - `decide`를 `TURN_TREE`(Sequence) 실행으로 바꾸고, 긴 함수 본문을 단계 함수(`read_situation`,
    `plan_captures`, `produce`, `move_warriors`, `move_flags`, `set_priority`)와 칠판 `Turn`으로 나눴다
  - `select_phase`는 `PHASE_TREE`를 실행하는 함수로, `flag_step`은 `FLAG_TREE`를 실행하는 함수로 바꿨다
  - 계산식·상수·효용 배정기는 그대로. 첫 배정 결과를 생산 단계가 다시 쓰도록 칠판에 저장
- `sim/diff.py`, `sim/__main__.py`: 새 명령 `python -m sim diff A B [--vs C]` — 두 봇이 같은 상대에게 매 턴
  같은 명령을 내는지 비교하고, 처음 달라진 턴을 보여 준다
- `docs/roadmap.md`: M3 절에 "상태 머신 → 행동 트리" 정리와 트리 그림. `docs/simulator.md`: `diff` 사용법

## 사람이 한 것

- 지금 구조가 BT가 아니라 상태 머신에 가깝다는 문제 제기
- BT와 상태 머신 중 하나로 통일하기로 결정, LLM 추천(BT)과 2단계 진행(구조 먼저, 새 가지는 다음) 승인

## 검증

- `python -m sim diff . git:main` 800경기·115,286턴에서 명령이 모두 같음: 상대 `main`(시드 0~99, 100~199),
  `starter:example_lv2`, M3(`c561771`), M4(`f564d8b`)
- `diff` 도구가 차이를 잡는지: `SPARE_FLAGS`를 잠깐 2로 바꾸면 4경기 모두 11턴·48턴에서 달라짐을 보고
- `python -m sim arena . git:main --seeds 50`: 100무, 최대 응답 10 ms로 `main`과 같음
- `pytest` 784 통과 (`test_devtool_is_unmodified`는 #30부터 `.gitignore` 문제로 실패, 이번 변경과 무관)
