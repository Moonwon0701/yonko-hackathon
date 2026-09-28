# yonko-hackathon

2026 연고전 AI 해커톤 「깃발 대항전」(2026-09-27 ~ 10-01)에 제출하는 봇입니다. 15×15 격자에서 두 팀이
동시에 턴을 두고, 160턴 동안 깃발병으로 건물을 점령해 점수를 겨룹니다. 규칙 정리는
[docs/game-api.md](docs/game-api.md), 원문은 [docs/rules-original.md](docs/rules-original.md)에 있습니다.

## 팀원과 담당

| 이름 | 담당 파일 | 하는 일 |
| --- | --- | --- |
| 문원 | `agent/adapter.py`, `agent/world.py`, `agent/strategy.py`·`agent/bt.py`(공동) | 게임 입출력 ↔ `World` 변환, 로컬 시뮬레이터, 전략(현진과 공동) |
| 성혁 | `agent/algorithms.py` | 경로 탐색 등 순수 알고리즘 함수 |
| 현진 | `agent/strategy.py`, `agent/bt.py`(공동) | `decide(world) -> actions` 판단 로직, 행동 트리 노드(문원과 공동) |

전략은 규칙 기반입니다. 행동 트리(BT)가 국면을 고르고, 효용 점수가 건물 가치를 매겨 유닛에 목표를
나눕니다. 운영진 답변(9/27)에 따르면 소스 코드 안에 적은 상수는 학습한 가중치라도 허용되고, 별도 데이터
파일로 넣는 것만 안 됩니다. 학습을 실제로 적용할지는 아직 팀에서 정하지 않았습니다. 자세한 내용은
[CLAUDE.md](CLAUDE.md)의 "전략 방식" 절을 보세요.

## 협업 방식: 테마 브랜치 (9/28 회의 결정)

9/28부터 세 명이 각자 테마를 잡고 어느 정도 독립적으로 봇을 키웁니다. 위 담당 표는 `main` 기준이고,
테마 브랜치 안에서는 브랜치 주인이 전략 파일을 자유롭게 고칩니다.

| 이름 | 브랜치 | 테마 | 하는 일 |
| --- | --- | --- | --- |
| 성혁 | 성혁 테마 브랜치 | **공격·확장** | 상대 건물 공략과 빠른 점령 확장 위주의 봇 |
| 현진 | 현진 테마 브랜치 | **수비·자원 수급** | 내 건물 지키기와 자원 확보 위주의 봇 |
| 문원 | `main` | 지금 상태 그대로 + 통합 | 두 브랜치에 push된 결과를 중간중간 확인해 `main`에 반영하고, 자체 개발도 계속 |

- 테마 브랜치는 PR 없이 **push만** 합니다. `main`에는 문원이 PR로 옮깁니다.
- 모든 봇이 같이 쓰는 파일(`adapter.py`, `world.py`, `main.py`, `sim/`)의 버그 수정은 따로 브랜치를 만들어
  `main`에 PR로 올리고, 테마 브랜치에는 `git merge main`으로 받습니다.
- 어느 회차에 어느 브랜치의 어느 커밋을 냈는지 [docs/benchmarks.md](docs/benchmarks.md)에 적습니다.

### 리더보드 일정

| 때 | 할 일 |
| --- | --- |
| 9/30(수) 08:00 회차 | **현진** 봇 제출 |
| 9/30(수) 20:00 회차 | **성혁** 봇 제출 |
| 9/30(수) 24:00경 | 두 결과를 보고 셋이 이야기해 10/1 08:00 회차에 낼 봇을 고름 |
| 10/1(목) 08:00 회차 | 고른 봇 제출 |
| 10/1(목) 08:00 이후 | 결과를 보고 서로 소통하며 최종 제출 전까지 계속 개선. 23:00 파일 제출, 23:59 최종 선택·보고서 마감 |

회의 메모의 "수요일 오후 12시"는 20:00 회차 결과까지 보려면 자정이어야 해서 24:00경으로 적었습니다.
9/28 20:00 ~ 9/29 20:00 회차에 무엇을 낼지는 아직 정하지 않았습니다. 자세한 규칙은
[CLAUDE.md](CLAUDE.md)의 "협업 방식" 절에 있습니다.

## 폴더 구조

봇은 한 방향으로만 의존합니다: `adapter.py → world.py → algorithms.py → strategy.py`.
`strategy.py`가 쓰는 행동 트리 노드는 게임과 무관한 `bt.py`에 따로 있습니다.
게임 입출력 형식은 `adapter.py`만 알고, `strategy.py`는 `World` 객체만 봅니다.

| 위치 | 내용 |
| --- | --- |
| `main.py` | 제출 진입 파일. 입력 루프만 돌리고, 어떤 예외가 나도 매 턴 `END`를 출력한다 |
| `agent/` | 봇 본체 (위 다섯 파일). 제출 ZIP에는 `main.py`, `agent/`, `submission.json`만 들어간다 |
| `sim/` | 로컬 시뮬레이터: 대전(arena), 리플레이 뷰어, 행동 비교(diff) |
| `scripts/` | 제출 ZIP 만들기, 이긴 경기·진 경기 분석 |
| `tests/` | `pytest` 테스트 |
| `starter/`, `devtool/` | 운영진 스타터 킷과 공식 개발도구 원본. **고치지 않는다** |
| `data/server-replays/` | 대회 페이지에서 받은 서버 경기 리플레이 |
| `docs/` | 규칙 정리, 로드맵, 성능 기록, LLM 사용 기록 |

## 시작하는 법

팀 전원이 Windows이므로 **PowerShell 기준**으로 적습니다. Git Bash나 macOS·Linux는 아래
"다른 셸을 쓴다면"을 보세요.

### 먼저 설치할 것

| 프로그램 | 받는 곳 | 설치할 때 |
| --- | --- | --- |
| Python **3.12** | <https://www.python.org/downloads/windows/> 에서 3.12.x의 "Windows installer (64-bit)" | 첫 화면의 **"py launcher"** 체크를 켜 둔 채로(기본값) 설치. 3.13·3.14가 아니라 3.12 |
| Git | <https://git-scm.com/download/win> | 기본값 그대로 설치 |

Microsoft Store의 Python, VS Code의 Python 확장, GitHub Desktop으로는 대신할 수 없습니다.
VS Code Python 확장은 파이썬을 설치하지 않고 이미 설치된 것을 찾아 쓰기만 하고, GitHub Desktop은 자기 안에만
Git을 넣어 둬서 터미널에서 `git` 명령이 안 됩니다. 둘 다 위 설치를 마친 뒤 **추가로** 쓰는 것은 괜찮습니다.

설치 후 **새 PowerShell 창**을 열고 확인합니다.

```powershell
py -0p          # -V:3.12 줄이 보여야 한다
git --version
```

### 저장소 받고 환경 만들기

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
pytest                        # 실패 1개만 나오면 현재 정상 (아래 참고)
ruff check .                  # All checks passed!
```

실패하는 1개는 `tests/test_official.py::test_devtool_is_unmodified`입니다. `.gitignore`의 `dist/` 줄이
`devtool/bots/dist/`까지 무시해서 그 파일들이 저장소에 없기 때문이고, 봇 동작과는 관계없습니다.
이 파일들을 추가하는 커밋이 `main`에 들어오면 전부 통과합니다. 그 밖의 실패나 `ERROR ... collecting`이
나오면 설치가 잘못된 것이니 팀 채팅에 에러 전문을 올리세요.

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

## 로컬에서 대전하기

코드를 고쳤으면 서버에 올리기 전에 로컬 시뮬레이터로 확인합니다. 자세한 사용법은
[docs/simulator.md](docs/simulator.md)에 있습니다.

```powershell
python -m sim arena . git:main --seeds 100                 # 지금 코드 vs main, 맵 100개 × 진영 교대 = 200경기
python -m sim match . starter:example_lv2 --seed 3 --open  # 한 판 두고 리플레이를 브라우저로 열기
python -m sim diff . git:main --seeds 100                  # 구조만 바꾼 변경이 main과 매 턴 같은 명령을 내는지
python scripts/analyze_games.py . git:main --seeds 100     # 이긴 경기와 진 경기를 턴별·건물 종류별로 비교
```

시드 0~9 맵은 서버 모의 전투와 같은 맵입니다(운영진 공식 맵 생성기 사용). `arena` 결과의 승점률 옆 95% 구간이
50%를 걸치면 아직 차이를 말할 수 없으니 `--seeds`를 늘립니다.

## 지금 봇 상태

- 9/27 서버 모의 전투(M3 버전): 하·중·상 봇 각 10전 10승 → 수료 기준(중 봇 상대 6승 이상) 통과
- 그 뒤로 병원 생산, 전투병 역 순간이동, 공학관 가치 상향이 들어갔고, 전략 코드를 행동 트리 하나로 정리했다
- 진행 상황과 다음 계획은 [docs/roadmap.md](docs/roadmap.md), 실험 수치는 [docs/benchmarks.md](docs/benchmarks.md)

## 봇 실행과 제출

```powershell
pytest                                  # 테스트 (스타터 예제와 같은 명령을 내는지 포함)
ruff check .                            # 린트
python scripts/build_submission.py      # 제출 ZIP 만들기 + 풀어서 160턴 스모크 테스트
```

결과는 `dist/bot-<커밋 해시>.zip`입니다. 커밋 안 된 변경이 섞여 있으면 이름에 `-dirty`가
붙으니, 제출용은 커밋한 뒤에 만드세요. 만든 ZIP을 대회 페이지에 올리고 **검사 통과 확인 →
코드 선택**까지 해야 반영됩니다.

마감(서버 시각): 회차 반영은 매일 **08:00·20:00**. 마지막 날(10/1)은 **23:00** 파일 제출,
**23:59** 최종 선택·보고서 마감입니다.

ZIP은 손으로 만들지 마세요. PowerShell 5.1의 `Compress-Archive`는 경로를 역슬래시로 저장하고,
Git Bash의 `tar`는 ZIP이 아니라 tar 파일을 만듭니다. 둘 다 서버 검사에서 떨어질 수 있습니다.

## 매일 작업 순서

1. `git checkout main` 후 `git pull` — 최신 코드를 받는다.
2. `git checkout -b 이름/기능` — 내 작업용 브랜치를 만든다.
3. 작업하고 `git add` → `git commit`.
4. `git push -u origin 이름/기능`.
5. GitHub에서 PR을 만들고 팀원에게 알린다.

**테마 브랜치(성혁·현진)는 이렇게 합니다.**

1. `git checkout main` 후 `git pull` — 내 컴퓨터의 `main`을 최신으로 만든다. `git merge main`은 GitHub이
   아니라 **내 컴퓨터의 `main`**을 합치므로, 이 단계를 빼면 새 공용 수정이 들어오지 않는다.
2. `git checkout 내-테마-브랜치` 후 `git pull` — 내 브랜치의 최신 상태를 받는다.
3. `git merge main` — `main`에 들어온 공용 수정을 내 브랜치로 가져온다. 내 브랜치의 작업은 그대로 남고
   `main`은 바뀌지 않는다(바뀐 게 없으면 아무 일도 없다). 충돌이 나면 멈추고 팀 채팅에 알린다.
4. 작업하고 `git add` → `git commit`.
5. `git push` — PR은 만들지 않는다. 팀 채팅에 무엇을 바꿨는지 한 줄 알린다.

## 개발 규칙 요약

전체 규칙은 [CLAUDE.md](CLAUDE.md)에 있습니다. 자주 잊는 것만 모았습니다.

- **턴 계산 시간:** 서버는 로컬보다 약 12배 느립니다. 로컬에서 턴당 계산이 **20 ms**를 넘지 않게 합니다
  (제한 300 ms, 넘으면 몰수패)
- **효과가 확인된 것만 넣습니다.** 전략 변경은 `arena`로 200경기 이상 두고, 결과는 넣든 빼든
  [docs/benchmarks.md](docs/benchmarks.md)에 적습니다
- **LLM으로 파일을 고치면** 같은 PR에 `docs/llm-log/` 기록 파일을 넣습니다. 보고서 필수 항목입니다
- 모든 변경은 브랜치 → PR로 `main`에 들어갑니다. 남의 담당 파일이 들어간 PR은 담당자가 확인하고 머지합니다.
  공동 담당인 `strategy.py`·`bt.py`만 고친 PR은 올린 사람이 머지하고 다른 담당자에게 알립니다.
  테마 브랜치는 예외로 PR 없이 push하고, `main`에는 문원이 옮깁니다

## 문서

- [claude-code-setup.md](claude-code-setup.md) — Claude Code 설치, CLI/GUI 차이, GitHub 연결.
  **해커톤 시작 전에 먼저 읽으세요.**
- [onboarding.md](onboarding.md) — GitHub 협업 방식, 행동 트리, 강화학습 배경 설명.
- [docs/llm-log/](docs/llm-log/) — LLM 사용 기록. 보고서 필수 기재 항목의 원자료.
- [docs/game-api.md](docs/game-api.md) — 게임 규칙을 설계용으로 정리한 문서. 원문은
  [docs/rules-original.md](docs/rules-original.md).
- [docs/roadmap.md](docs/roadmap.md) — 전략 개선 로드맵(M0~M5)과 마일스톤별 결과.
- [docs/benchmarks.md](docs/benchmarks.md) — 로컬 대전·서버 모의 전투·응답 시간 기록.
- [docs/simulator.md](docs/simulator.md) — 로컬 시뮬레이터 사용법.
