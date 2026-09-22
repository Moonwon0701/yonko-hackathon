# Claude Code 환경설정

지금까지 Claude를 "웹에서 질문하고 답을 복사해서 에디터에 붙여넣는" 식으로 썼다면, 이 문서는
그 단계를 끝내기 위한 것입니다. Claude Code는 **내 컴퓨터의 저장소 안에서 직접 파일을 읽고
고치고 git 명령까지 실행하는** 도구입니다. 복붙이 사라집니다.

해커톤 시작 전에 셋 다 4번까지는 끝내 두세요. 5번부터는 필요할 때 찾아보면 됩니다.

1. 설치하고 로그인하기
2. CLI와 GUI의 차이 — 뭘 언제 쓰나
3. CLI 기본 조작
4. GitHub와 연결하기
5. 설정 파일로 내 취향에 맞추기
6. 우리 저장소에서의 하루 흐름
7. 잘 안 될 때

---

## 0. 먼저: 복붙과 뭐가 다른가

| | 웹에서 복붙 | Claude Code |
| --- | --- | --- |
| 코드를 보는 범위 | 내가 붙여넣은 조각만 | 저장소 전체를 스스로 열어봄 |
| 파일 수정 | 내가 직접 붙여넣기 | Claude가 직접 수정 (내 승인 후) |
| 명령 실행 | 불가능 | 테스트·git·설치 명령을 직접 실행 |
| 프로젝트 규칙 | 매번 다시 설명 | `CLAUDE.md`를 매 세션 자동으로 읽음 |
| git/PR | 내가 수동으로 | 브랜치·커밋·PR까지 대신 |

핵심은 **맥락(context)** 입니다. 복붙은 매번 "우리 프로젝트가 뭐고 파일 구조가 어떻고"를 다시
설명해야 하지만, Claude Code는 저장소 안에서 돌기 때문에 이미 알고 있습니다. 이 저장소 루트의
`CLAUDE.md`가 바로 그 설명서고, 세션이 시작될 때 자동으로 읽힙니다.

---

## 1. 설치하고 로그인하기

### 설치 (Windows)

**PowerShell**을 열고 (시작 메뉴에서 `powershell` 검색) 아래 한 줄을 붙여넣습니다.

```powershell
irm https://claude.ai/install.ps1 | iex
```

설치가 끝나면 **터미널 창을 닫았다가 새로 엽니다.** (PATH가 새 창부터 적용됩니다.)

> **Windows는 Git for Windows가 반드시 필요합니다.** Claude Code가 명령을 실행할 때 Git Bash를
> 씁니다. `git --version`이 동작하지 않으면 <https://git-scm.com/download/win> 에서 먼저
> 설치하세요.

### 설치 (macOS / Linux)

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

### 설치 확인

```bash
claude --version      # 예: 2.1.278 (Claude Code)
claude doctor         # 설치 상태 진단
```

### 로그인

저장소 폴더에서 `claude`를 실행하면 처음 한 번 로그인 화면이 뜹니다.

```bash
cd C:\yonko-hackathon     # 내 저장소 폴더로 이동
claude
```

브라우저가 열리면 평소 쓰는 Claude 계정(Pro/Max 구독)으로 로그인합니다. 나중에 계정을 바꾸려면
Claude Code 안에서 `/login`, 확인은 `/status`입니다.

> 로그인은 **컴퓨터 단위로 한 번**입니다. 저장소마다 다시 하지 않습니다.

---

## 2. CLI와 GUI의 차이

같은 Claude Code를 어디서 띄우느냐의 차이일 뿐, **두뇌는 동일합니다.** 내 컴퓨터의 파일을
읽고 고친다는 점도 같습니다. 다른 건 화면과 조작 방식입니다.

| | CLI (터미널) | GUI (데스크톱 앱 / IDE 확장 / 웹) |
| --- | --- | --- |
| 실행 | 터미널에서 `claude` | 앱 아이콘, VS Code 사이드바, claude.ai/code |
| 변경 내용 보기 | 터미널 안에 텍스트 diff | 색칠된 diff, 파일 탭으로 확인 |
| 여러 작업 동시에 | 터미널 창을 여러 개 | 탭·세션으로 나란히 |
| 이미지 붙여넣기 | 되지만 불편 | 스크린샷 붙여넣기가 편함 |
| 기능 범위 | 모든 기능이 다 있음 | 일부 설정은 결국 CLI로 |
| 추천 | **기본으로 이걸 쓰세요** | diff 확인할 때 병행 |

- **CLI** — 터미널에 `claude`. 가장 빠르고 기능이 빠짐없이 있습니다. 이 문서의 기준입니다.
- **데스크톱 앱** — Mac/Windows용 앱. 터미널이 부담스러운 사람의 입문용으로 좋습니다.
- **IDE 확장** — VS Code / JetBrains. 에디터 안에서 diff를 보며 작업합니다. VS Code에서 통합
  터미널을 열고 `claude`를 치면 확장이 자동으로 연동됩니다.
- **웹** — <https://claude.ai/code>. 내 PC가 아니라 클라우드에서 돕니다. 외출 중에 쓸 때.

**결론: 셋 다 CLI를 기본으로 쓰고, diff를 눈으로 꼼꼼히 보고 싶을 때만 VS Code 확장을 같이
켜세요.** 어느 쪽에서 작업하든 결과는 같은 저장소에 쌓입니다.

---

## 3. CLI 기본 조작

`claude`를 실행하면 프롬프트가 뜹니다. 여기서 그냥 한국어로 말하면 됩니다.

```
> agent/pathfind.py에 A* 경로탐색을 추가해줘
```

### 외워야 하는 키 5개

| 키 | 하는 일 |
| --- | --- |
| `Esc` | **작업 중단.** Claude가 엉뚱한 길로 가면 바로 누릅니다 |
| `Esc` `Esc` | 이전 대화 시점으로 되돌리기 (되돌아가서 다시 시키기) |
| `Shift` + `Tab` | 권한 모드 전환 (아래 설명) |
| `Ctrl` + `C` | 입력 취소 / 두 번 누르면 종료 |
| `↑` | 이전에 보낸 메시지 다시 꺼내기 |

### 입력 앞에 붙이는 기호 3개

| 기호 | 뜻 | 예시 |
| --- | --- | --- |
| `@` | 파일 지정 (자동완성됨) | `@agent/world.py 이 구조 설명해줘` |
| `!` | 터미널 명령 직접 실행 | `!git status` |
| `#` | 이 내용을 `CLAUDE.md`에 기억시키기 | `# 테스트는 pytest -q로 돌린다` |

### 권한 모드 — `Shift` + `Tab`

Claude가 파일을 고치거나 명령을 실행할 때마다 물어보는 게 기본값입니다. `Shift+Tab`을 누를
때마다 아래로 순환합니다.

1. **기본** — 매번 물어봄. 뭘 하는지 다 보입니다. **처음엔 이걸로.**
2. **auto-accept edits** — 파일 수정은 묻지 않고 진행. 믿을 만한 단순 작업일 때.
3. **plan mode** — 계획만 세우고 **파일은 건드리지 않음.** "어떻게 할 건지 먼저 말해봐"가
   필요할 때 아주 유용합니다.

> 익숙해지기 전까지는 기본 모드를 쓰세요. 승인 화면을 읽는 게 Claude Code를 배우는 가장 빠른
> 길입니다.

### 자주 쓰는 슬래시 명령

```
/help          명령 목록
/clear         대화를 비움 (주제가 바뀌면 이걸 — 가장 자주 쓰게 됩니다)
/init          저장소를 분석해 CLAUDE.md 초안 생성
/model         모델 변경
/status        로그인 계정·버전·설정 확인
/config        설정 화면
/permissions   허용/거부 규칙 관리
/doctor        설치 상태 진단
/cost          사용량 확인
/mcp           외부 도구 연결 (선택)
```

**`/clear`를 아까워하지 마세요.** 한 대화에 여러 주제를 섞으면 Claude가 앞의 이야기에 끌려
다닙니다. 작업 하나 끝나면 `/clear`.

### 대화창을 열지 않고 한 번만 시키기

```bash
claude -p "이 저장소의 테스트를 돌리고 결과만 알려줘"   # 한 번 실행하고 종료
claude -c                                            # 직전 대화 이어서
claude -r                                            # 지난 대화 골라서 이어서
```

---

## 4. GitHub와 연결하기

Claude가 브랜치를 만들고 커밋하고 PR까지 올리게 하려면, **GitHub CLI(`gh`)에 로그인**되어
있으면 됩니다. 이것 하나면 끝입니다.

### 4-1. gh 설치와 로그인

```powershell
winget install --id GitHub.cli     # Windows. mac은: brew install gh
```

새 터미널을 열고:

```bash
gh auth login
```

질문에 이렇게 답합니다.

```
? What account do you want to log into?           GitHub.com
? What is your preferred protocol?                HTTPS
? Authenticate Git with your GitHub credentials?  Yes
? How would you like to authenticate?             Login with a web browser
```

브라우저에 뜨는 8자리 코드를 붙여넣고 승인하면 끝입니다. 확인:

```bash
gh auth status     # ✓ Logged in to github.com account ... 가 나오면 성공
```

> `Authenticate Git with your GitHub credentials?`에 **Yes**가 중요합니다. 이걸 해두면
> `git push`할 때마다 비밀번호를 묻지 않습니다.

### 4-2. 저장소 받아오기

```bash
git clone https://github.com/Moonwon0701/yonko-hackathon.git
cd yonko-hackathon
claude
```

이제 Claude에게 이렇게 말할 수 있습니다.

```
> pathfind.py에 A* 추가하고, 브랜치 만들어서 PR까지 올려줘
```

그러면 Claude가 `main`에서 pull → 새 브랜치 → 수정 → 커밋 → push → `gh pr create`까지 합니다.
각 단계마다 승인 화면이 뜨니 읽고 승인하면 됩니다.

> 이 저장소의 git 규칙(브랜치 이름, PR 본문 형식, 누가 머지하는가)은 `CLAUDE.md`에 적혀 있고
> Claude가 알아서 지킵니다. 규칙을 바꾸고 싶으면 코드가 아니라 `CLAUDE.md`를 고치세요.

### 4-3. (선택) GitHub에서 @claude 부르기

PR 코멘트에 `@claude 이 함수 리뷰해줘`라고 쓰면 Claude가 답하게 만들 수도 있습니다.

```
/install-github-app
```

저장소 **관리자 권한**이 필요하고 GitHub App 설치 과정을 거칩니다. 해커톤 필수는 아니니,
시간이 남으면 저장소 주인 계정으로 해보세요.

---

## 5. 설정 파일로 내 취향에 맞추기

설정은 JSON 파일 두 종류입니다. **직접 손으로 쓰지 말고 Claude에게 시키는 게 편합니다.**

```
> 이 프로젝트에서 pytest 실행은 매번 묻지 말고 허용해줘
```

| 파일 | 범위 | 커밋하나? |
| --- | --- | --- |
| `.claude/settings.json` | 이 저장소, **팀 전원 공유** | 예 |
| `.claude/settings.local.json` | 이 저장소, **나만** | 아니오 (`.gitignore`에 있음) |
| `~/.claude/settings.json` | 내 모든 프로젝트 | 해당 없음 |

우선순위는 `settings.local.json` > `settings.json` > 사용자 설정입니다. 즉 개인 설정이 팀
설정을 덮어씁니다.

권한 규칙 예시 (`.claude/settings.json`):

```json
{
  "permissions": {
    "allow": ["Bash(pytest:*)", "Bash(git status)", "Bash(git diff:*)"],
    "deny": ["Bash(git push --force:*)", "Read(.env)"]
  }
}
```

`allow`에 넣은 명령은 다시 묻지 않고, `deny`는 아예 실행하지 않습니다. 팀 전체에 유용한
규칙(테스트 실행 등)만 `settings.json`에 넣고, 나머지는 각자 `settings.local.json`에 두세요.

### CLAUDE.md — 사실 이게 제일 중요한 설정

JSON보다 `CLAUDE.md`가 훨씬 중요합니다. **매 세션 자동으로 읽히는 프로젝트 설명서**라서, 여기
적어두면 매번 설명할 필요가 없습니다. 우리 저장소에는 이미 담당 파일, 구조 규칙, PR 형식, git
규칙이 들어 있습니다.

- 새 규칙을 추가하고 싶으면: 대화 중에 `#`으로 시작하는 메시지를 보내면 됩니다.
- `CLAUDE.md`는 **팀 공유 파일**이므로, 고치면 PR로 올리고 팀에 알립니다.

---

## 6. 우리 저장소에서의 하루 흐름

```bash
cd C:\yonko-hackathon
claude
```

```
> 오늘은 pathfind.py에 BFS 경로탐색을 추가할 거야. main에서 브랜치부터 만들어줘
  ... (작업) ...
> 테스트 돌려보고, 통과하면 커밋하고 PR 올려줘
```

중간에 이런 말들이 유용합니다.

| 상황 | 이렇게 말하세요 |
| --- | --- |
| 바로 고치지 말고 계획부터 | "계획만 먼저 보여줘" (또는 `Shift+Tab`으로 plan mode) |
| 방향이 틀렸을 때 | `Esc` 누르고 → "그거 말고 ~로 해줘" |
| 뭘 했는지 확인 | "방금 뭐 바꿨는지 요약해줘" 또는 `!git diff` |
| 주제가 바뀔 때 | `/clear` |
| 충돌이 났을 때 | 에러 메시지를 통째로 붙여넣고 "어떻게 하면 돼?" |

**`git reset --hard`, `git push --force`, 머지 안 된 브랜치 삭제는 Claude가 반드시 먼저
물어봅니다.** (`CLAUDE.md`에 그렇게 적혀 있습니다.) 이 셋을 물어보면 잠깐 멈추고 팀에
확인하세요.

---

## 7. 잘 안 될 때

| 증상 | 해결 |
| --- | --- |
| `claude` 명령을 못 찾음 | 터미널을 새로 열기. 그래도 안 되면 재설치 |
| Windows에서 명령 실행이 실패 | Git for Windows 설치 확인 (`git --version`) |
| 뭔가 이상하게 동작 | `claude doctor` → `/status` |
| 대답이 헛돌거나 옛날 이야기를 함 | `/clear` 후 다시 |
| 승인 창이 너무 자주 뜸 | `/permissions`로 자주 쓰는 명령 허용 |
| 한글 입력이 깨짐 | Windows Terminal 사용 (기본 cmd 창 말고) |
| 줄바꿈하려는데 전송됨 | `\` 입력 후 Enter |
| Claude가 파일을 못 찾음 | `@`로 경로를 직접 지정 |

### 하지 말아야 할 것

- **`.env`나 토큰 파일 내용을 대화에 붙여넣지 않기.** 게임 API 키가 나오면 `.env`에 넣고 파일
  경로만 말하세요. `.gitignore`에 이미 `.env`가 들어 있습니다.
- **승인 화면을 안 읽고 계속 Enter 치지 않기.** 특히 git 관련 명령.
- **한 대화에서 여러 주제 섞지 않기.** `/clear`는 공짜입니다.
- **`main`에서 바로 작업하지 않기.** Claude가 막아주지만, 습관을 들이세요.

---

## 더 읽을거리

- 공식 문서: <https://docs.claude.com/en/docs/claude-code/overview>
- 팀 배경 지식(git 사이클, 행동 트리, 강화학습): [onboarding.md](onboarding.md)
- 우리 저장소 규칙: [CLAUDE.md](CLAUDE.md)
