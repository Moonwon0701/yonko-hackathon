# 스타터 예제 봇을 우리 구조로 이식

- 날짜: 2026-09-27
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: #16 (브랜치 `moonwon/port-starter`)
- 기록 시점: `moonwon/rules-and-llm-log` 작업 중 소급 기록 (이 규칙이 생기기 전 작업)

## 프롬프트 (원문 그대로)

이 작업으로 이어진 앞선 질문 (파일 변경 없음, 제출 형식 파악용):

1. > 지금 파이썬, 넘파이 버전은 어때?
2. > 아냐아냐 괜찮아. 제출 형식 어떻게 해야해?
3. > example_lv2로 제출 ZIP 만들려면 어떻게 구성해야하지

이 작업의 요청:

4. > 오늘 오후 3시부터 제출이 가능하네. 우선 스타터에 있던 코드들 가지고 우리 디렉토리 형식으로 만들자.

## 목적

- 15:00 제출 시작에 맞춰, 스타터 예제를 우리 구조(adapter → world → algorithms → strategy)로
  옮겨 각자 담당 파일에서 개선을 시작할 수 있게 하기 위해

## 범위 — LLM이 한 것

- `agent/world.py`: `GameMap`·`Building`·`World`, 규칙 수치 상수, 행동 타입 설계와 작성
- `agent/adapter.py`: 입력 파싱, 행동 → 명령 줄 변환
- `agent/algorithms.py`: 스타터 BFS를 순수 함수 `first_step`으로 이식
- `agent/strategy.py`: `example_lv2` 로직을 동작 변경 없이 이식
- `main.py`: 예외가 나도 매 턴 `END`를 내는 입력 루프
- `scripts/build_submission.py`: 제출 ZIP 생성·검사·스모크 테스트
- `tests/`: 스타터와의 출력 비교, 몰수패 방지 테스트, 무작위 입력 생성기
- 앞선 질문 3에서 `dist/bot-lv2.zip`을 만들다 Git Bash `tar`가 ZIP이 아닌 tar를 만드는 문제를 발견해
  파이썬 `zipfile`로 바꿈

## 사람이 한 것

- 구조와 담당 파일 규칙(이전 PR에서 결정)
- PR 확인 후 문원이 머지

## 검증

- `pytest` 203개 통과, `ruff check .` 통과
- 무작위 입력 200개 × 5턴에서 `example_lv2`와 명령 완전 일치 (SPAWN 1,182 / MOVE 2,174줄 비교).
  전투병 상한·방향 순서를 일부러 바꾸면 테스트가 실패하는 것도 확인
- 서버처럼 한 턴씩 주고받는 테스트: 응답을 빼면 5초 뒤 실패하는 것 확인
- 제출 ZIP을 풀어 160턴 실행, 턴당 평균 약 1 ms
