# roadmap에 지금 행동 트리 전체 싣기

- 날짜: 2026-09-28
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: (올린 뒤 번호 기록) (브랜치 `moonwon/full-tree-docs`)

## 프롬프트 (원문 그대로)

1. > 노션 작업 요약 페이지도 수정해줘
2. > 전체 트리도 수정해줘야지

## 목적

- PR #40에서 `docs/roadmap.md` "구조 정리 2"에 트리를 줄여 적어(HOLD·ATTACK·EXPAND 한 줄 요약, 깃발병 트리 빠짐)
  보고서에 그대로 옮길 수 없었다. `tree_text()` 출력 전체로 바꾼다.

## 범위 — LLM이 한 것

- `docs/roadmap.md`: "구조 정리 2"의 트리를 `tree_text()` 출력 그대로(한 턴 트리 + 깃발병 트리)로 교체.
  9/27 "구조 정리" 절의 옛 트리는 기록으로 두고 "9/27 당시 트리"라고 표시
- (저장소 밖) 노션 작업 요약 페이지: PR #40 내용 반영, 판단 구조 절에 전체 트리를 접는 블록으로 추가

## 사람이 한 것

- 트리를 줄여 적은 것을 지적하고 전체 트리로 고치라고 지시

## 검증

- 트리 텍스트는 `python -c "from agent.strategy import tree_text; print(tree_text())"` 출력을 그대로 붙임
