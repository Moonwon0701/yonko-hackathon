# 9/30 10:00 리더보드 순위표·리플레이 받기와 요약

- 날짜: 2026-09-30
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI (Claude in Chrome 확장으로 대회 사이트 조회)
- PR: #55 (브랜치 `moonwon/leaderboard-0930-10`)

## 프롬프트 (원문 그대로)

1. > 오늘 10시 기준 리더보드 업데이트
2. (리플레이 12개를 Chrome 다운로드로 받아도 되는지 묻자) > 응 다운로드로 받아

## 목적

- 9/30 10:00 회차 결과를 저장소에 남기고, 진 경기의 모습을 요약한다

## 범위 — LLM이 한 것

- 대회 사이트 조회 (문원의 로그인된 Chrome 세션, 읽기만 함)
  - `/api/leaderboard`: 9/30 10:00 회차(공개 2026-09-30 01:00 UTC, `SWISS_REGULAR_V1`, 492경기) 83팀
    → `data/leader_board/2026-09-30-10.csv` (지난 파일과 같은 열. 55위 팀 이름 `占쏙옙`은 API 값 그대로)
  - `/api/submissions`: 이번 회차 제출 버전 11 = `bot-7b8b67e.zip`(`hyunjin/defense-econ` `7b8b67e`, 9/30 02:08 업로드)
  - `/api/matches/history`: 이 회차 우리 경기 12판(7승 5패)
  - 경기마다 `/api/matches/<id>/replay-url`로 리플레이를 읽고, 문원 승인으로 Chrome 다운로드(`vs_상대_승패.json`) 뒤
    `data/server-replays/2026-09-30_leaderboard_10/`로 옮김 + `matches.csv`(지난 회차와 같은 열)
- `scripts/profile_opponents.py`: `ROUNDS`에 새 회차 폴더 추가
- 리플레이 요약(일회용 스크립트, 저장소에 넣지 않음) → `docs/benchmarks.md` "서버 리더보드" 표에 한 줄
  - 22위(22:00 36위에서 +14). 진 5판은 모두 우리보다 위 팀(6·7·12·14·16위)
  - 20턴 전에 우리 공학관·광장을 잃은 세 경기(페이커·참새튀김기·ACE)는 모두 짐
- `data/leader_board/*.html`과 `dev_tool.zip`은 지난번처럼 커밋하지 않음

## 사람이 한 것

- 결과 확인을 요청하고, 리플레이 다운로드를 승인
- 08:00 회차에 현진 봇 ZIP을 업로드·선택(팀 결정)

## 검증

- 순위표 CSV의 SHA-256(`e21d3834…`)이 브라우저에서 만든 CSV 문자열의 SHA-256과 같음
- 받은 리플레이 12개의 `gameId`가 서버 경기 ID와 같고, 크기·마지막 턴 번호가 브라우저에서 읽은 값과 같음
- 파일 이름의 승패가 리플레이 `result.winner`(우리 `side`와 비교)와 같음
- 순위표 우리 줄(22위, 7승 5패, 12경기)이 경기 기록 12판과 맞음
- `pytest tests/test_sim_server_maps.py` 88개 통과(새 리플레이 맵 포함)
