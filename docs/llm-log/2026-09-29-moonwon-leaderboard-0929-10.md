# 9/29 10:00 리더보드 순위표·리플레이 받기와 요약

- 날짜: 2026-09-29
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI (Claude in Chrome 확장으로 대회 사이트 조회)
- PR: (올린 뒤 적음, 브랜치 `moonwon/leaderboard-0929-10`)

## 프롬프트 (원문 그대로)

1. > 리더보드랑 리플레이 갱신
2. > 고고
   (Chrome 확장이 연결되지 않아 멈춘 뒤, 문원이 확장을 연결하고 한 답)

## 목적

- 9/29 10:00 회차 결과를 저장소에 남기고, 진 경기의 모습을 요약한다

## 범위 — LLM이 한 것

- 대회 사이트 조회 (문원의 로그인된 Chrome 세션, 읽기만 함)
  - `/api/leaderboard`: 9/29 10:00 회차(공개 2026-09-29 01:00 UTC) 77팀 → `data/leader_board/2026-09-29-10.csv`
    - 이 회차부터 채점 방식이 `SWISS_REGULAR_V1`(팀마다 12경기)이고 사이트 순위표 열이 "승점률"이라, 이전 파일의
      `adj_score`(보정 점수) 대신 `point_rate`(승점률 %)를 넣고, API의 상대 강도 `opponent_strength`를 끝에 더함.
      공동 순위는 API 값 그대로 같은 숫자, 처음 나온 팀의 `rank_change`는 빈칸
  - `/api/matches/history`: 이 회차 우리 경기 12판(8승 4패, 제출 버전 9 = `bot-0f689cd.zip`)
  - 경기마다 `/api/matches/<id>/replay-url`로 리플레이를 받아 `vs_상대_승패.json` 이름으로 저장
    → `data/server-replays/2026-09-29_leaderboard_10/` 12개 + `matches.csv`
  - 경기 기록에서는 우리가 K 칸(`teamK`)인 경기가 9판인데, 리플레이 `side`는 12판 모두 Y이고 우리 건물도 `owner`가 Y.
    리플레이가 우리 시점(Y)으로 맞춰 저장되는 것으로 보고, `matches.csv`의 `our_side`에는 경기 기록 칸(K/Y)을 적음.
    분석 스크립트는 리플레이 안의 `side`를 쓰므로 영향 없음
- `scripts/profile_opponents.py`: `ROUNDS`에 새 회차 폴더 추가 (분석 명령이 이 회차도 읽게)
- 리플레이 요약 (`profile_opponents.py`, `--economy`와 일회용 스크립트, 일회용은 저장소에 넣지 않음)
  → `docs/benchmarks.md` "서버 리더보드" 표에 한 줄
  - 10위(22:00 19위에서 +9). 진 4판: 치명ㄷ(2위), 저게되네;(13위), 렛츠고(21위), 신촌도 우리땅(32위)
  - 서버 응답: 첫 턴 496~753 ms, 둘째 턴부터 최대 99 ms
- 제출 버전 9가 어느 커밋인지(`moonwon/eval-tuning` `0f689cd`)를 사이트의 제출 파일 이름에서 확인해 같은 줄에 적음
- `data/leader_board/*.html`(문원이 저장한 페이지)과 `dev_tool.zip`은 지난번처럼 커밋하지 않음

## 사람이 한 것

- 갱신을 요청하고, Chrome 확장을 연결함

## 검증

- 받은 리플레이 12개의 `gameId`가 서버 경기 ID와 같고, 파일 크기가 브라우저에서 받은 응답 길이와 같음
- 파일 이름의 승패가 리플레이 `result.winner`(우리 `side`와 비교)와 같음
- 순위표 우리 줄(10위, 8승 4패, 12경기)이 경기 기록 12판과 맞음. 모든 팀의 `points` = 승 + 무/2
