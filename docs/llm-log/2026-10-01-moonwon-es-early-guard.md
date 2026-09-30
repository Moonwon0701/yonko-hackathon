# 선제 수비 봇(e30333c) 제출본 빌드 + 선제 수비 상수까지 넣은 ES 4차 학습

- 날짜: 2026-10-01
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: 없음 — 브랜치 `moonwon/defense-intercept`

## 프롬프트 (원문 그대로)

1. > 아까 직전까지 돌아가고 있던 거 있는데 확인해줘
2. > 그러면 이번 추가된 기능 가지고 튜닝 돌려볼까? 일단 제출본은 하나 만들어줘
3. > 몇세대 돌릴 계획 세운거야?
4. > 성혁 브랜치 수정사항 들어가있어?
5. > 제출본에서는 제외해주고 학습에는 추가해줘.

## 목적

- 성혁 `sunghyuk/hunters` 가치 측정(400판 × 상대 3개)이 끝난 것을 확인하고, 이번에 넣은 선제 수비(`EARLY_GUARD`) 봇을 제출본으로
  만들어 둔 뒤, 선제 수비 상수까지 학습 층에 넣어 ES로 이어서 학습한다.

## 범위 — LLM이 한 것

- 실행 중이던 `scripts/h2h.py`(성혁 hunters 스위치 빼 보기)의 진행·최종 결과 확인 및 짝 비교(같은 시드끼리 차이) 계산
- `scripts/build_submission.py`로 `dist/bot-e30333c.zip` 빌드(가짜 입력 160턴 통과). 제출 ZIP은 저장소에 넣지 않음
- `agent/learned.py`: KNOBS에 선제 수비 상수 3개 추가(`EARLY_GUARD_WEIGHT`, `EARLY_GUARD` 정수 하한 0, `EARLY_SLACK` 정수 하한 0).
  W에는 아직 없으므로 봇 행동은 그대로
- `experiments/learned_eg/`(새 폴더): 학습할 봇 = 위 변경을 넣은 현재 봇(`main.py` + `agent/*.py`) 복사본
- `scripts/es_train.py`: 상대 풀 `early_guard` 추가(`e30333c` 4 · `strong_wide` 3 · `074803e` 2 · `337ab49`·hunters `efb71da`·
  `26fa986`·`daa1888`·공학관 러시 각 1)
- 학습 시작: 180세대 W(`runs/es/start_eg_g180.json`)에서 이어서, 3차와 같은 설정(잡음 16쌍, 세대당 16맵, σ 0.2, 학습률 0.015,
  20세대마다 풀 비중대로 검증), 300세대 상한. 300은 넉넉한 상한이고 중간 저장 세대(20세대마다)를 새 시드로 비교해 고른다
- 성혁 브랜치 확인: `attack-expand`·`decoy-flex` 기능은 이미 `337ab49`에서 스위치로 옮겨져 있고, `sunghyuk/hunters` `efb71da`(10/1 02:13)는
  빠져 있음을 확인
- 성혁 hunters를 **학습 봇에만** 추가(제출본 `e30333c`·루트 `agent/`는 그대로): `efb71da`의 `agent/strategy.py` 변경을
  `experiments/learned_eg/agent/strategy.py`에 적용(hunters 바탕 봇 코드가 `074803e`와 같아 그대로 얹힘). 스위치는 가치 측정에서 유일하게
  모든 상대에 +였던 기동대 수정(`MOBILE_FLIPS` 2, `MOBILE_WINDOW` 80, `MOBILE_CALM` 30, `MOBILE_DEPTH` 3)만 켜고, 조건부 암살
  (`ASSASSIN_COND`)·소탕(`SWEEP`)은 끔. 사냥조·양동 기대값은 hunters에서도 꺼져 있던 그대로
- 첫 학습(hunters 없이)은 12세대에서 멈추고(`runs/es/early_guard_stopped_g12.log`) 같은 설정으로 다시 시작. 로그 `runs/es/early_guard.log`

## 사람이 한 것

- 선제 수비 봇을 제출본으로 만들고, 이번에 추가한 기능으로 튜닝을 돌리기로 결정했다.
- 성혁 hunters 변경을 제출본에서는 빼고 학습 봇에만 넣기로 결정했다.

## 검증

- `experiments/learned_eg`(새 상수 3개, W 그대로) 대 `git:e30333c` 새 시드 43000~43019 20판: 모두 무승부(행동 동일)
- hunters를 얹은 `experiments/learned_eg` 대 `git:e30333c` 새 시드 43000~43023 24판: 12승 2무 10패, 몰수 0, 최대 응답 8 ms(행동이
  달라졌고 정상 동작)
