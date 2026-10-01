# tAIger(1위) 분석에서 얻은 스위치 두 개(국지 열세 할인·깃발병 급증)와 비교 시험

- 날짜: 2026-10-01
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`) → 같은 세션에서 Claude Fable 5.1 (`claude-fable-5-1`)로 바뀜, Claude Code CLI
  (Claude in Chrome 확장으로 대회 사이트 조회)
- PR: 없음 (테마 브랜치 방식 — 브랜치 `moonwon/taiger-lessons`, `moonwon/loss-1001` `8722c0d`에서 만듦)

## 프롬프트 (원문 그대로)

1. > tAIger가 강한이유 분석해봐
2. > 도서관으로 얻은 이점도 큰가? 이번 리더보드 갱신됐으니까 확인해줘. taiger랑 또 붙었어
3. > 그건 다른 세션에서 진행중이니까 파악한 내용 바탕으로 개선 고민해보고 구현해서 검증해봐
4. > 좀 더 결과 빨리 내주라
5. > ee4ea4b 상대로 우세를 보이는건  flag escape 때문인가
6. > strong_wide 결과 나오면 문서에 채우고 커밋해줘
7. > 그냥 완료해줘

## 목적

- 리더보드 1위 tAIger가 왜 강한지 우리 리플레이로 파악하고, 거기서 우리 봇에 넣을 수 있는 규칙을 찾아 시험한다

## 범위 — LLM이 한 것

- 분석 (저장소 파일 수정 없음, 결과는 `docs/benchmarks.md` "tAIger 분석" 절에 정리)
  - `data/server-replays/`의 tAIger전 3판(9/27·9/28·10/1 10:00)을 `scripts/profile_opponents.py --team tAIger [--us|--economy|--tactics]`와
    일회용 턴별 집계(10턴 단위 점수·자원·병력·건물, 소유 변경, 중립화 시점의 반경 2 병력, 10턴 단위 지출)로 비교
  - 10/1 17:00 회차 순위표와 tAIger전 리플레이는 대회 사이트 API(`/api/leaderboard`, `/api/matches/history`, `/api/matches/<id>/replay-url`)로
    브라우저 안에서 읽어 같은 집계를 돌림(파일로 받지 않음 — 받기는 다른 세션이 진행 중)
  - 도서관 이점: 서버 리플레이 108판에서 "도서관 보유 중 점령 단계 수 = 아낀 자원"을 세어 수입과 비교
- `agent/strategy.py`: 스위치 두 개 추가(기본 끔)
  - `LOCAL_DISCOUNT`·`LOCAL_RADIUS`: `capture_tasks`에서 목표 건물 체비쇼프 `LOCAL_RADIUS` 안 적 전투병 > 우리 전투병이면 점령 가치 × `LOCAL_DISCOUNT`
    (전투병이 뽑아 주거나 호위가 가는 건물은 제외). 인원 세기는 새 순수 함수 `nearby`
  - `FLAG_SURGE`·`FLAG_SURGE_FROM`·`FLAG_SURGE_RATIO`·`FLAG_SURGE_MARGIN`·`FLAG_SURGE_FLAGS`: `produce`에서 전투병이 적 × 비율 + 여유 이상이면
    깃발병 총원 상한을 `FLAG_SURGE_FLAGS`로
- `docs/benchmarks.md`: "tAIger 분석" 절(관찰 표·도서관 이점·스위치 시험 표)
- 시험: `scripts/h2h.py`로 기준 + 후보 7개(`LOCAL_DISCOUNT` 0.1·0.3·0.5, `FLAG_SURGE` 기본·이른 조건, `DEPOT_VALUE` 6, `SPARE_FLAGS` 0)를
  `ee4ea4b`·`337ab49`·`strong_wide` 상대 새 시드 80000~80239 240판씩

## 사람이 한 것

- 분석·개선·검증을 지시. 다른 세션이 같은 작업 폴더(`loss-1001`)에서 실험 중이라 LLM이 새 브랜치·작업 폴더를 만들고 8작업으로 돌림
- 중간 결과를 보고 시험을 조기에 마감하고 문서에 채워 커밋하라고 지시(`strong_wide` 상대는 155판에서 중단)
- 5번 질문(제출본 `ee4ea4b` 상대 우세의 원인)은 파일 수정 없이 답함: 기준 봇과 `ee4ea4b`의 켠 차이는 `FLAG_ESCAPE`뿐이고, 10/1 진 경기 분석
  스위치 표(같은 봇끼리 50.0% → 켜면 64~69%, `FLAG_ESCAPE_GAIN`을 올리면 60.9%로 내려감)가 근거

## 검증

- `pytest tests/test_strategy.py tests/test_main.py` 39개 통과 (스위치 끈 기본값은 동작이 같음)
- 4판 연기 시험: 세 후보 모두 몰수 0, 최대 응답 24~30 ms
- 10/1 10:00 tAIger전 리플레이 재실행(`scripts/rerun_replay.py`): `LOCAL_DISCOUNT=0.3`은 9턴부터 94턴의 명령이 바뀜(기준 16턴 — 스위치가
  실제로 판단에 끼어듦), `FLAG_SURGE`는 그 판에서 조건이 한 번도 성립하지 않아 기준과 같음
- 비교 시험(`runs/h2h/20261001-172915.jsonl`, 시드 80000~80239): 대 `337ab49` / `ee4ea4b` / `strong_wide`(155판) 기준 76.2 / 64.4 / 82.6,
  `LOCAL_DISCOUNT` 0.1 73.8 / 57.5 / 80.5 · 0.3 71.7 / 65.0 / 83.1 · 0.5 78.3 / 64.2 / 85.7, `FLAG_SURGE` 76.2 / 64.4 / 82.5 · 이른 조건
  74.6 / 65.6 / 81.8, `DEPOT_VALUE` 6 74.2 / 65.4 / 81.8, `SPARE_FLAGS` 0 76.7 / 64.4 / 81.8 → **모두 흔들림(±3%p) 안, 무효.** 스위치는 끈 채 남김
