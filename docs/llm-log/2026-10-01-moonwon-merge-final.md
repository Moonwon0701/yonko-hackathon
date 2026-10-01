# 최종 봇(포위된 깃발병 탈출 + 성혁 막판 광장)을 main으로 옮기기

- 날짜: 2026-10-01
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: (브랜치 `moonwon/merge-final`)

## 프롬프트 (원문 그대로)

1. > 합친 봇 메인에 머지해줘
2. (`docs/benchmarks.md` 충돌 설명과 "main 쪽 줄을 남기자"는 제안에) > 어 그렇게 해

이 봇을 만든 분석·실험·병합의 프롬프트는 `docs/llm-log/2026-10-01-moonwon-loss-1001.md`(같이 옮겨 옴)에 있다.

## 목적

- 최종 제출 후보인 합친 봇(`moonwon/loss-1001` `e5cbeb7`)과 그 근거 기록을 `main`에 남긴다

## 범위 — LLM이 한 것

- `main`에서 `moonwon/merge-final`을 만들고 `moonwon/loss-1001` `ff150a5`(합친 봇 `e5cbeb7` + 기록)를 합침
- 충돌 1곳 해결(문원 승인): `docs/benchmarks.md` "서버 리더보드" 표 끝 — main 쪽(9/30 20:00 결과 기입, 10/1 08:00, 10/1 17:00 줄)을
  남기고 브랜치 쪽(9/30 20:00 "(결과 대기)" 옛 줄, 08:00 같은 줄)은 버림. 브랜치에서 새로 더한 절(진 경기 분석 스위치 · 오후 반복 ·
  ES 5차 · 최종 병합)은 충돌 없이 들어옴
- 옮겨 오는 봇 변경(`agent/strategy.py`): `FLAG_ESCAPE` 1(포위된 깃발병 탈출, 켬), 성혁 `PLAZA_LATE_TURN` 130 · `PLAZA_LATE_BONUS` +8 ·
  `RAID_ENG_BOOST` 3 · `RAID_ENG_SURPLUS` 15(켬), 그 밖 새 스위치는 모두 끔(역 차단, `RETAKE_KINDS`, `RESCUE_VALUE`, `HOLD_POST`,
  `FLAG_ESCAPE_GAIN`, 학생회관 조기 경보, 막판 저격). 학습 가중치(`agent/learned.py`)는 main과 같음(ES 4차 180세대)
- 그 밖에 옮겨 오는 것: `scripts/rerun_replay.py`, `scripts/es_train.py` 풀 `flag_escape`, `experiments/learned_fe`, 리플레이 데이터(main과 같은 파일)

## 사람이 한 것

- 합친 봇을 최종 후보로 main에 옮기기로 결정, 충돌 해결 방법 승인

## 검증

- 합친 뒤 `agent/`·`main.py`·`submission.json`이 `e5cbeb7`과 같음(`git diff` 차이 0)
- `pytest tests` 917개 통과
- 근거 수치: `docs/benchmarks.md` "최종 병합" 절(합친 봇 대 `0a15a9e` 54.2%, 대 `ee4ea4b` 71.0%, 대 `strong_wide` 84.8%, 400판씩)
