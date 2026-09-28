# 평가 도구·흉내 봇·리플레이를 main으로 옮기기 (전략 코드 제외)

- 날짜: 2026-09-29
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: #51 (브랜치 `moonwon/eval-tools`)

## 프롬프트 (원문 그대로)

1. > 오늘 내가 작업한 내용 요약해줘
2. > 팀원들 노티 용으로 간단하게 3줄 요약 해주고 실제 전략 수정이 아닌 리그/ 다양한 봇 풀 등의 평가 도구, 추가된 리플레이 메인에 PR올리고 머지해줘.

## 목적

- 테마 브랜치 `moonwon/eval-tuning`에서 만든 평가 도구를 성혁·현진도 자기 테마 브랜치에서 쓸 수 있게 `main`에 옮긴다.
  전략 코드(`agent/`)의 변경(호위·경제 건물 수비·공학관 러시·초소)은 옮기지 않는다.

## 범위 — LLM이 한 것

- 프롬프트 1: 파일을 고치지 않고 오늘 작업을 요약했다.
- 프롬프트 2:
  - `scripts/tune.py`: 기준 봇에 없는 상수는 건너뛰게 고쳤다(탐색 목록에 테마 브랜치에만 있는 스위치 9개가 있어 `main` 기준으로
    돌리면 멈췄다). 테마 브랜치에 먼저 커밋(`6096423`)하고 옮겼다.
  - `main`에서 `moonwon/eval-tools`를 만들고 테마 브랜치에서 파일만 골라 가져왔다: `scripts/profile_opponents.py`·`eval_pool.py`·
    `tune.py`·`league.py`, `opponents/`(고정 기준 봇 + 흉내 봇 4개), `pyproject.toml`(ruff 제외 경로),
    `data/server-replays/2026-09-28_not_faced/`(크아앙 시점 리플레이 5판), `docs/benchmarks.md`, 관련 LLM 기록 8개.
    `agent/`·`main.py`·`tests/`는 가져오지 않았다.
  - `docs/benchmarks.md`는 나중에 테마 브랜치에 `main`을 합칠 때 충돌이 나지 않게 테마 브랜치 파일을 통째로 옮겼다. 그래서
    테마 브랜치의 전략 실험 기록(파라미터 탐색 절 등)도 들어 있다 — 기록일 뿐 해당 코드는 `main`에 없다.
  - 팀원 알림용 3줄 요약을 썼다.

## 사람이 한 것

- 문원: 전략 수정은 빼고 평가 도구와 리플레이만 `main`에 옮기기로 정했다.

## 검증

- PR 브랜치에서 `ruff check .` 통과, `pytest` 815개 통과(테마 브랜치의 전략 테스트 3개는 옮기지 않음).
- PR 브랜치에서 `eval_pool.py`, `league.py`, `profile_opponents.py --economy`, `tune.py --base git:main`(테마 전용 스위치 건너뜀)이 돈다.
