# 10/1 00:30 리더보드(9/30 20:00 마감 회차) 순위표·리플레이 받기와 요약

- 날짜: 2026-10-01
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI (Claude in Chrome 확장으로 대회 사이트 조회)
- PR: #58 (브랜치 `moonwon/leaderboard-0930-22`)

## 프롬프트 (원문 그대로)

1. > 리플레이 파일이랑 리더보드 전부 다운로드해서 올려줘.

## 목적

- 9/30 20:00 마감 회차(사이트 이름 "10월 1일 00:30 리더보드") 결과를 저장소에 남기고, 진 경기의 모습을 요약한다

## 범위 — LLM이 한 것

- 대회 사이트 조회 (문원의 로그인된 Chrome 세션, 읽기만 함)
  - `/api/matches/history`: 리더보드 7회차 우리 경기 84판. 지난 6회차(7·13·16·12·12·12판)는 이미 저장소에 모두 있어서
    새 회차 12판(8승 4패)만 받음
  - `/api/leaderboard`: 새 회차(공개 2026-09-30 15:09 UTC, `SWISS_REGULAR_V1`, 516경기) 87팀
    → `data/leader_board/2026-10-01-00-30.csv` (지난 파일과 같은 열·형식. 사이트 회차 이름을 따라 파일 이름을 정함)
  - `/api/submissions`: 이번 회차 제출 버전 12 = `bot-337ab49.zip`(`moonwon/eval-tuning` `337ab49`, 9/30 10:46 UTC 업로드)
  - 경기마다 `/api/matches/<id>/replay-url`로 리플레이를 읽어 Chrome 다운로드(`vs_상대_승패.json`) 뒤
    `data/server-replays/2026-10-01_leaderboard_0030/`로 옮김 + `matches.csv`(지난 회차와 같은 열)
- `scripts/profile_opponents.py`: `ROUNDS`에 새 회차 폴더 추가
- 리플레이 요약(일회용 스크립트, 저장소에 넣지 않음) → `docs/benchmarks.md` "서버 리더보드" 표의 9/30 20:00 줄에 결과 기입
  - 12위(10:00 22위에서 +10), 8-0-4. 진 4판 중 3판이 우리보다 위 팀(치명ㄷ 6위·ACE 8위·모든상금은… 10위)
  - 탈락도 락이다(37위)전은 160턴 건물 8:8 동점에서 누적 점령-턴(`occupation_turns`)으로 짐 — 이 판정은 처음
- `data/leader_board/*.html`과 `dev_tool.zip`은 지난번처럼 커밋하지 않음

## 사람이 한 것

- 결과 받기를 요청(다운로드 포함)
- 9/30 20:00 회차에 `337ab49` 봇을 내기로 결정(문원)

## 검증

- 순위표 CSV의 SHA-256(`73b98a89…`)이 브라우저에서 만든 CSV 문자열의 SHA-256과 같음
- 받은 리플레이 12개의 SHA-256 앞 16자리가 브라우저에서 읽은 내용의 해시와 모두 같음
- 리플레이 `gameId`가 서버 경기 ID와 같고, 파일 이름의 승패가 리플레이 `result.winner`(우리 `side`와 비교)와 같음
- 순위표 우리 줄(12위, 8승 4패, 12경기)이 경기 기록 12판과 맞음
- `pytest tests/test_sim_server_maps.py` 100개 통과(새 리플레이 맵 12개 포함)
- `scripts/profile_opponents.py --team 치명ㄷ`가 새 회차 경기를 읽음
