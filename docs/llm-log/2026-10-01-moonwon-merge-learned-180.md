# 학습 봇(180세대 + 성혁 기능)을 main으로 옮김

- 날짜: 2026-10-01
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: (번호는 PR을 만든 뒤 채움) — 브랜치 `moonwon/merge-learned-180`, 테마 브랜치 `moonwon/eval-tuning` `074803e`에서 옮김

## 프롬프트 (원문 그대로)

1. > 이제 메인에 이 버전으로 머지하자

## 목적

- 테마 브랜치에서 키운 봇(`daa1888` + ES 학습 층 + 성혁 기능 선별 조합 + 3차 학습 180세대 W)을 `main`의 봇으로 삼는다.

## 범위 — LLM이 한 것

- `main`(`57cc5dd`)에서 `moonwon/merge-learned-180`을 만들고 `moonwon/eval-tuning` `074803e`를 머지 커밋으로 합침(파일은 `074803e`와 같음).
  바뀌는 것: `agent/strategy.py`·`agent/learned.py`·`agent/forecast.py`(봇), `tests/test_strategy.py`, `scripts/es_*.py`(학습·평가),
  `experiments/`(학습용 봇 복사본 3개), `opponents/strong_wide.py`·`opponents/base_uo/`(흉내 봇), `docs/benchmarks.md`, LLM 기록.
  `main.py`·`agent/adapter.py`·`agent/world.py`·`sim/`은 그대로.
- 머지 전 `git merge-tree`로 테마 브랜치 셋(`hyunjin/defense-econ`·`sunghyuk/attack-expand`·`sunghyuk/decoy-flex`)과 미리 합쳐 봄:
  셋 다 `agent/strategy.py`·`tests/test_strategy.py`에서 충돌(각자 봇을 고친 파일이라 예상된 충돌).
- 이 기록 파일.

## 사람이 한 것

- 180세대 봇을 `main`에 넣기로 결정.

## 검증

- `pytest tests` 857개 통과. 봇 파일이 `074803e`와 같음(`git diff 074803e` 없음). `074803e` 봇의 성적은
  `docs/benchmarks.md` "학습 (진화 전략)" 표(새 시드 570판: 대 `337ab49` 58.1%, 대 `26fa986` 62.5%).
