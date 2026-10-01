# 보고서용 문서 추가 (최종 제출본 정리, tAIger 분석 옮기기)

- 날짜: 2026-10-01
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: #66 (브랜치 `moonwon/report-docs`)

## 프롬프트 (원문 그대로)

1. > 전체 다 커밋됐지?
2. > 문서 추가해줘. 보고서에 참고할 수 있게

1번에 모든 작업 폴더·브랜치를 점검해, 다른 세션이 만든 `moonwon/taiger-lessons`(`5c8a9d3`, tAIger 분석)가 한 번도 푸시되지 않은 것을 알렸다.
2번을 그 문서를 보고서에서 쓸 수 있게 main에 넣으라는 뜻과 최종 제출본 정리 문서를 만드는 뜻으로 받았다.

## 목적

- 보고서("개발 과정"·"유닛 운용"·"정량적 검증")에서 바로 참고할 수 있게 최종 제출본과 10/1 개발 과정, 1위 봇 분석을 main 문서로 모은다

## 범위 — LLM이 한 것

- `moonwon/taiger-lessons`를 원격에 푸시(브랜치 보존)
- 그 브랜치의 `docs/benchmarks.md` "tAIger 분석" 절과 `docs/llm-log/2026-10-01-moonwon-taiger-lessons.md`를 main으로 옮김(문서만, 그 브랜치의
  `LOCAL_DISCOUNT`·`FLAG_SURGE` 스위치 코드는 옮기지 않음 — main 봇을 제출본 `6ed5706`과 같게 두려고)
- `docs/final-submission.md` 새로 작성: 최종 제출본, 봇의 층과 기여자, 10/1 개발 흐름, 통한 것·안 통한 것, 서버 리더보드 흐름, 한계,
  참고 문서. 숫자는 `docs/benchmarks.md`·`docs/learned-weights.md`·LLM 기록에서 옮김

## 사람이 한 것

- 보고서 참고용 문서를 남기자고 정함

## 검증

- 합친 뒤에도 `agent/`·`main.py`·`submission.json`이 `6ed5706`과 같음(문서만 바뀜)
- 요약 문서의 회차별 순위·승패와 주요 승점률을 `docs/benchmarks.md`의 해당 줄과 대조함
