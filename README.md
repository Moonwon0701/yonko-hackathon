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

## 막히면

혼자 억지로 해결하지 말고, Claude Code에게 상황(무엇을 하려 했고, 어떤 메시지가 나왔는지)을
그대로 설명하고 물어보세요. 특히 git 충돌은 잘못 건드리면 작업이 날아갈 수 있으니 먼저 물어보는
편이 안전합니다.
