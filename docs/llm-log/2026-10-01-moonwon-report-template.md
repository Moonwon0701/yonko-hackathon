# 보고서 양식 추가와 항목 정리

- 날짜: 2026-10-01
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI (백그라운드 작업)
- PR: #60 (`moonwon/report-template`)

## 프롬프트 (원문 그대로)

1. > "C:\Users\k4jgj\Downloads\2026 연고전 AI 해커톤 보고서.docx" 이 보고서 양식 레포지토리에 추가하고, 항목 뭐 있는지 파악해봐

## 목적

- 운영진 보고서 양식을 저장소에 두고, 세 명이 같은 항목·배점을 보고 자료를 모으게 한다.

## 범위 — LLM이 한 것

- `docs/report/template.docx`: 받은 양식을 바꾸지 않고 복사(이름만 영문으로)
- `docs/report/README.md`: docx XML에서 읽은 항목·표 칸·안내문을 규정의 배점(`docs/rules-original.md`)과 맞춰 표로 정리,
  부록 표에 프롬프트 칸이 없다는 점과 쓸 자료 위치를 적음

## 사람이 한 것

- 양식 파일을 받아 위치를 알려 줌(문원)

## 이어진 대화

### 프롬프트 (원문 그대로)

2. > 개발과정에 협업 방식도 추가하면 좋을 것 같아

### LLM이 한 것

- `docs/report/README.md`에 "개발 과정 — 협업 방식 (초안)" 절 추가: `CLAUDE.md` 협업 규칙, git 기록(첫 커밋 9/21, 원격 브랜치, PR 수),
  `docs/benchmarks.md`·빼 보기 결과에서 사실을 모아 5~6문장 초안과 근거 목록을 씀
