# yonko-hackathon

캡처 더 플래그(CTF) 형식 게임을 플레이하는 해커톤용 AI 에이전트입니다.

## 팀원과 담당

| 이름 | 담당 파일 | 하는 일 |
| --- | --- | --- |
| 문원 | `agent/adapter.py`, `agent/world.py` | 게임 입출력 ↔ `World` 변환. 필요 시 로컬 시뮬레이터 |
| 성혁 | `agent/algorithms.py` | 경로 탐색 등 순수 알고리즘 함수 |
| 현진 | `agent/strategy.py` | `decide(world) -> actions` 판단 로직 |

전략은 규칙 기반(BT + 효용 점수)으로 만듭니다. 제출 규정이 학습 가중치를 금지하므로
신경망·강화학습은 하지 않습니다. 자세한 내용은 [CLAUDE.md](CLAUDE.md)의 "전략 방식" 절을 보세요.

## 시작하는 법

팀 전원이 Windows이므로 **PowerShell 기준**으로 적습니다. Git Bash나 macOS·Linux는 아래
"다른 셸을 쓴다면"을 보세요.

```powershell
git clone https://github.com/Moonwon0701/yonko-hackathon.git
cd yonko-hackathon

py -m venv .venv              # python 아님. 아래 "python 대신 py를 쓰는 이유" 참고
.venv\Scripts\activate
pip install -e ".[dev]"       # agent 패키지 + 개발 도구(pytest, ruff) 설치
```

제대로 됐는지 확인:

```powershell
python -c "import agent; print('ok')"
pytest                        # 아직 테스트가 없으면 "no tests ran"이 정상
```

### python 대신 py를 쓰는 이유

Windows에서 `python`은 실제 파이썬이 아니라 **Microsoft Store 바로가기**를 가리키는 경우가
많습니다. 그 상태에서 `py -m venv` 대신 `python -m venv`를 치면 이렇게 나옵니다.

```
Python was not found; run without arguments to install from the Microsoft Store, ...
```

**이 메시지를 따라 Store에서 설치하지 마세요.** 파이썬이 두 개가 되어 더 꼬입니다. `py`가
진짜 파이썬을 찾아주므로 `py -m venv .venv`로 만들면 됩니다.

`py`가 필요한 것은 venv를 만드는 이 한 줄뿐입니다. 활성화하고 나면 `.venv\Scripts`가 PATH 맨
앞에 붙어서 `python`이 venv 안의 파이썬을 가리키므로, 그 뒤로는 `python`을 그대로 씁니다.

설치된 파이썬을 확인하려면 `py -0p`를 칩니다.

### 활성화가 막히면 (PowerShell)

Windows는 기본적으로 PowerShell 스크립트 실행을 막아둡니다. 그 상태라면 활성화에서 이 에러가
납니다.

```
File ...\Activate.ps1 cannot be loaded because running scripts is disabled on this system.
```

한 번만 풀어주면 됩니다. 관리자 권한은 필요 없습니다.

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 다른 셸을 쓴다면

활성화 명령만 다르고 나머지는 같습니다.

| 환경 | 활성화 명령 |
| --- | --- |
| PowerShell | `.venv\Scripts\activate` |
| Git Bash (Windows) | `source .venv/Scripts/activate` |
| macOS · Linux | `source .venv/bin/activate` |

Windows는 `bin`이 아니라 **`Scripts`** 입니다. macOS·Linux에서는 `py`가 없으므로
`python3 -m venv .venv`로 만듭니다.

### 버전과 의존성

파이썬은 **3.12**를 씁니다(`.python-version`). 셋의 버전이 다르면 같은 코드가 다르게 돕니다.

의존성을 추가할 때는 `pip install`만 하고 끝내지 말고 **`pyproject.toml`에 버전을 고정해서
적은 뒤** PR로 올립니다. 그래야 나머지 두 명이 `git pull` 후 `pip install -e ".[dev]"` 한 번으로
같은 환경이 됩니다.

## 봇 실행과 제출

```powershell
pytest                                  # 테스트 (스타터 예제와 같은 명령을 내는지 포함)
ruff check .                            # 린트
python scripts/build_submission.py      # 제출 ZIP 만들기 + 풀어서 160턴 스모크 테스트
```

결과는 `dist/bot-<커밋 해시>.zip`입니다. 커밋 안 된 변경이 섞여 있으면 이름에 `-dirty`가
붙으니, 제출용은 커밋한 뒤에 만드세요. 만든 ZIP을 대회 페이지에 올리고 **검사 통과 확인 →
코드 선택**까지 해야 반영됩니다.

ZIP은 손으로 만들지 마세요. PowerShell 5.1의 `Compress-Archive`는 경로를 역슬래시로 저장하고,
Git Bash의 `tar`는 ZIP이 아니라 tar 파일을 만듭니다. 둘 다 서버 검사에서 떨어질 수 있습니다.

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
  (강화학습은 대회 규정상 쓰지 않기로 했습니다.)
- [docs/llm-log/](docs/llm-log/) — LLM 사용 기록. 보고서 필수 기재 항목의 원자료.
- [docs/game-api.md](docs/game-api.md) — 게임 규칙을 설계용으로 정리한 문서. 원문은
  [docs/rules-original.md](docs/rules-original.md).
