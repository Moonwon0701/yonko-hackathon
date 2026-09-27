# 파일별 기능 구분 정리: 행동 트리 노드 분리, 규칙 계산을 World로

- 날짜: 2026-09-28
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: (올린 뒤 번호 기록) (브랜치 `moonwon/restructure`)

## 프롬프트 (원문 그대로)

1. > 지금 각 파일 별로 기능 구분이 잘 되어있어?
2. > 아직 지금까지는 단독 작업 가능해. 머지하고 구조 개편 시작하자

## 목적

- `agent/strategy.py`(809줄, 에이전트 코드의 약 65%)에 전략이 아닌 코드가 섞여 있어, 구조 규칙대로 제자리로 옮긴다.
  공동 작업 때 한 파일에서 충돌이 잦아지는 것도 줄인다. 동작은 바꾸지 않는다.

## 범위 — LLM이 한 것

- 진단(1번 프롬프트, 파일 변경 없음): 네 파일의 역할과 의존 방향은 지켜지고 있고, strategy.py에 ① 범용 행동 트리
  엔진 ② 규칙 계산 ③ 순수 기하가 섞여 있다고 정리
- `agent/bt.py`(새 파일): `Node`·`Selector`·`Sequence`·`Condition`·`Act`·`Latch`를 strategy.py에서 그대로 옮김.
  `tree_text()`는 트리 조립 옆(strategy.py 끝)으로
- `agent/world.py`: `World.warrior_cost(team)`(공학관 할인), `World.stage_cost(b, team)`(도서관 할인) 추가 —
  strategy.py의 `warrior_cost`·`stage_cost`를 옮김
- `agent/algorithms.py`: `manhattan` 추가(strategy.py에서 옮김)
- `agent/strategy.py`: 위를 가져다 씀. `stages(b)`는 `assign` 안의 한 줄 식으로(목표는 우리 건물이 아니므로 중립 1,
  상대 2). 쓰이지 않게 된 규칙 수치 import 제거. 역·중앙 건물 판별(`is_center`·`campus_stations`)은 점수 추측용
  휴리스틱이라 그대로 둠
- `CLAUDE.md`·`README.md`·`onboarding.md`: 구조 그림·파일 설명·담당 표에 `bt.py` 추가(담당은 strategy.py와 같게 현진)

## 사람이 한 것

- 단독 작업 기간이 9/28에도 이어진다고 알려 줌, 구조 개편 결정
- PR #38 머지 지시

## 검증

- `python -m sim diff . git:main`: 단계마다 확인. 60경기(9,600턴) 명령이 모두 같음, 달라진 경기 0
- `tests/test_strategy.py`·`tests/test_main.py` 통과. 전체 실패 10개는 이번 변경과 무관(커밋 안 한 리더보드
  리플레이가 공개 시드가 아님 9개, `devtool/bots/dist/` 누락 1개)
- `scripts/build_submission.py`: ZIP에 `agent/bt.py` 포함, 스모크 테스트 160턴 모두 END
- strategy.py 809 → 688줄
