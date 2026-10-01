# 보고서 자료 정리와 초안

- 날짜: 2026-10-01
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: 없음 (브랜치 `moonwon/report-draft`, 아직 PR 안 만듦)

## 프롬프트 (원문 그대로)

1. > 보고서 작성 위해 자료 정리하고 초안 작성해.
2. > draft 파일 위치
3. > 그 개선 효과별로 나열한 파일 위치 알려줘
4. > 옮겨주고 그거 반영해서 보고서 쓰자.

## 목적

- 마감(10/1 23:59) 전에 보고서 양식 항목별 근거를 한곳에 모으고, 팀이 고쳐 쓸 초안을 만든다.

## 범위 — LLM이 한 것

- 읽은 자료: `docs/benchmarks.md`(`main`과 `moonwon/defense-intercept`·`moonwon/loss-1001`에만 있는 절), `docs/report/README.md`,
  `moonwon/loss-1001`의 `agent/strategy.py`·`agent/learned.py`(최종 후보 봇의 상수와 판단 트리), `data/leader_board/*.csv`의 우리 줄,
  세 사람의 `docs/llm-log/`(테마 브랜치 포함)의 모델·프롬프트, Claude Code 메모(tAIger 분석·진 경기 분석 등 저장소에 안 남긴 채팅 결론)
- `docs/report/materials.md`: 양식 항목별 근거 색인 — 확인이 필요한 것, 판단 조건 표, 제출 이력, 개선과 근거 표, 뺀 것, 빼 보기 등급,
  평가 도구, 상대 분석, 부록용 모델·기록 수
- `docs/report/draft.md`: 양식 순서대로 쓴 초안(전략 요약, 유닛 운용 표, 구역별 운영 표, 제출별 개발 과정 표, 소감 초안, 부록 표와
  대표 프롬프트 원문)
- `docs/report/README.md`: 위 두 파일 링크
- (4번 프롬프트) `moonwon/defense-intercept`의 빼 보기 커밋 `beb1ef9`를 이 브랜치로 cherry-pick(`docs/benchmarks.md` "개선별 기여도 — 빼 보기" 절과
  `docs/llm-log/2026-10-01-moonwon-ablation.md`, 충돌 없음). 초안을 고침: 전략 요약을 빼 보기 핵심 넷 중심으로, 4절에 등급표(등급·넣은
  제출·빼면 승점·처음 넣은 근거)와 해석·한계, 제출 표에서 핵심·중요 개선을 굵게, 3절에 국면 전환 측정값

## 사람이 한 것

- (작성 시점) 아직 검토 전. 표지·최종 봇·10/1 20:00 결과·소감은 사람이 채운다

## 검증

- 초안의 숫자를 출처(`docs/benchmarks.md` 각 절, 브랜치의 benchmarks, 리더보드 CSV)와 다시 대조해 틀린 것(학습 층 수치를 제출한 240세대
  값으로, 깃발병 최소 인원 날짜·판 수 등)을 고쳤다
- 학습 층 상수 수(37개)를 `moonwon/loss-1001`의 `agent/learned.py`에서 셈
- 등급표의 "넣은 제출"을 커밋으로 확인: 호위·러시·초소·급습은 ③ `0f689cd`의 `strategy.py`에 켜져 있음
- 분량(본문 4장)은 docx로 옮겨 봐야 알 수 있어 확인 못 함
