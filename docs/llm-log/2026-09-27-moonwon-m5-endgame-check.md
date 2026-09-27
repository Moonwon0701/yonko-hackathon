# M5 시작: 막판 운영 실험 2개와 결과 기록

- 날짜: 2026-09-27
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: #32 (브랜치 `moonwon/m5-endgame-check`)

## 프롬프트 (원문 그대로)

1. > 이제 다음 마일스톤으로 넘어가야하 할 차례인가
2. > 응 브랜치 정리하고 M5 시작해.

## 목적

- M4가 끝났는지 확인하고, M5(후반 운영)의 첫 개선점을 대전 데이터로 골라 실험한다

## 범위 — LLM이 한 것

- 판단: 로드맵·벤치마크·코드를 읽고 M4 계획 항목이 모두 시험됐음을 확인. 서버 모의 전투가 M3 이후
  없다는 점(특히 TELE가 들어간 뒤 응답 시간)을 먼저 확인하라고 제안
- 분석: 최근 로컬 대전 3,260경기의 결정 사유를 셌다. 누적 점령-턴으로 갈린 경기 2% → 로드맵의
  "누적 점령-턴 가중치" 대신 막판 운영부터 실험
- 실험 1 (`agent/strategy.py`, 되돌림): 경기 끝까지 점령을 마칠 수 없는 깃발병 목표를 배정하지 않기.
  `main` 상대 31.5%. 명령이 처음 달라지는 턴을 찾는 스크립트로 원인 확인 — 못 마칠 목표로 가던 깃발병이
  경합으로 상대 점령을 막고 있었다
- 실험 2 (`agent/strategy.py`, `tests/test_strategy.py`, 되돌림): BT에 마무리(FINISH) 국면 추가.
  이전 M4 상대 승패가 `main`과 완전히 같음
- 진 경기 분석: 76패 중 3점 차 이하 2경기뿐 → 지는 원인은 중반
- 기록: `docs/benchmarks.md`에 실험 2줄, `docs/roadmap.md`에 M4 완료·M5 확인 내용
- 브랜치 정리: 머지된 `moonwon/tele-routing` 로컬 삭제(원격은 GitHub가 이미 삭제)

## 사람이 한 것

- M5로 넘어가기로 결정

## 검증

- 실험마다 `python -m sim arena`로 200경기(시드 0~99 × 진영 교대). 수치는 `docs/benchmarks.md`
- `pytest`: 784 통과. `tests/test_official.py::test_devtool_is_unmodified`는 이번 변경과 관계없이 실패한다 —
  `.gitignore`의 `dist/` 때문에 `devtool/bots/dist/`가 저장소에 없다(#30부터)
