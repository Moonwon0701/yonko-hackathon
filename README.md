# yonko-hackathon

캡처 더 플래그(CTF) 형식 게임을 플레이하는 해커톤용 AI 에이전트입니다.

## 팀원과 담당

| 이름 | 담당 파일 |
| --- | --- |
| (이름) | `agent/adapter.py`, `agent/world.py` |
| (이름) | `agent/pathfind.py` |
| (이름) | `agent/strategy.py` |

## 시작하는 법

```bash
git clone https://github.com/Moonwon0701/yonko-hackathon.git
cd yonko-hackathon

python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
```

TODO: 게임 규칙과 API가 공개되면 필요한 패키지 설치와 실행 명령을 여기에 적는다.

## 매일 작업 순서

1. `git checkout main` 후 `git pull` — 최신 코드를 받는다.
2. `git checkout -b 이름/기능` — 내 작업용 브랜치를 만든다.
3. 작업하고 `git add` → `git commit`.
4. `git push -u origin 이름/기능`.
5. GitHub에서 PR을 만들고 팀원에게 알린다.

## 문서

- [claude-code-setup.md](claude-code-setup.md) — Claude Code 설치, CLI/GUI 차이, GitHub 연결.
  **해커톤 시작 전에 먼저 읽으세요.**
- [onboarding.md](onboarding.md) — GitHub 협업 방식, 행동 트리, 강화학습 배경 설명.
