# Workflow / 작업 흐름

How a change actually gets from an idea to `main`. If you have not worked this way before,
read this once end to end - the whole team runs on this loop, and it is the same loop
whether the change is one line or a new module.

아이디어가 실제로 `main`까지 가는 과정입니다. 이런 방식이 처음이라면 한 번 끝까지 읽어 보세요.
팀 전체가 이 한 바퀴로 돌아가며, 한 줄짜리 변경이든 새 모듈이든 절차는 같습니다.

## The loop / 한 바퀴

```
main 최신화  →  브랜치  →  작업  →  커밋  →  push  →  PR  →  CI  →  머지  →  브랜치 삭제
```

One lap takes 20-60 minutes. **Keep laps small.** A branch that lives for three hours is a
branch that `main` has moved out from under, and that is where conflicts come from.

한 바퀴는 보통 20~60분입니다. **한 바퀴를 작게 유지하세요.** 세 시간짜리 브랜치는 그 사이
`main`이 움직여 버린 브랜치이고, 충돌은 거기서 생깁니다.

## Step by step / 단계별

### 1. Start from an up-to-date `main` / 최신 `main`에서 시작

```bash
git switch main
git pull
```

Always. Branching from a stale `main` means resolving conflicts later that never needed to
exist.

항상 이렇게 시작합니다. 오래된 `main`에서 가지를 치면, 원래 없어도 될 충돌을 나중에 풀게
됩니다.

### 2. Make a branch / 브랜치 만들기

```bash
git switch -c io/adapter-auth
```

Name it `<owner>/<topic>` - `io/`, `algo/` or `strategy/`. Uncommitted work follows you
onto the new branch, so it is fine to start editing first and branch a minute later.

이름은 `<owner>/<topic>` 형식으로 — `io/`, `algo/`, `strategy/`. 아직 커밋하지 않은 작업은
새 브랜치로 따라오므로, 먼저 편집을 시작했다가 나중에 브랜치를 만들어도 괜찮습니다.

### 3. Work / 작업

Run your Claude Code session here. It reads `CLAUDE.md`, so it already knows the layer
boundaries and who owns what.

여기서 Claude Code 세션을 돌립니다. 세션이 `CLAUDE.md`를 읽으므로 계층 경계와 파일 소유권을
이미 알고 있습니다.

### 4. Commit - the hooks run themselves / 커밋 - 훅이 알아서 돕니다

```bash
git add -A
git commit -m "add adapter authentication"
```

On every commit, pre-commit runs ruff (format + lint), mdformat, and the whitespace hooks.
**If a hook changes a file, the commit is aborted on purpose** - the files are fixed in
your working tree, so `git add -A` and commit again. That is normal, not an error.

커밋할 때마다 pre-commit이 ruff(서식·린트), mdformat, 공백 정리 훅을 실행합니다. **훅이 파일을
고치면 커밋은 일부러 중단됩니다.** 고쳐진 내용이 작업 트리에 반영되어 있으니 `git add -A` 후 다시
커밋하면 됩니다. 오류가 아니라 정상 동작입니다.

### 5. Push / 원격으로 보내기

```bash
git push -u origin io/adapter-auth
```

`-u` only on the first push of a branch; after that plain `git push`.

`-u`는 브랜치의 첫 push에만 붙이고, 이후에는 그냥 `git push`.

### 6. Open a PR / PR 올리기

```bash
gh pr create
```

This opens the PR template: *what changed / how tested / arena result vs main*. Fill it in
honestly - "not run, because docs only" is a perfectly good answer. `CODEOWNERS`
automatically requests the right reviewer.

PR 템플릿이 열립니다(무엇을 바꿨나 / 어떻게 테스트했나 / main 대비 아레나 결과). 솔직하게
채우세요. "문서만 바꿔서 안 돌렸음"도 훌륭한 답입니다. `CODEOWNERS`가 알맞은 리뷰어를 자동으로
지정합니다.

### 7. CI / 자동 검사

Opening the PR starts GitHub Actions, which runs the same checks you can run locally:
`ruff format --check`, `ruff check`, `mdformat --check` and `pytest`.

```bash
gh pr checks          # 현재 상태
gh run watch          # 끝날 때까지 지켜보기
```

Green means the change is safe to merge. Red means read the log - see below.

PR을 올리면 GitHub Actions가 시작되어, 로컬에서 돌릴 수 있는 것과 똑같은 검사를 실행합니다.
초록불이면 머지해도 안전하고, 빨간불이면 로그를 읽습니다(아래 참고).

### 8. Merge and clean up / 머지하고 정리

```bash
gh pr merge --squash --delete-branch
git switch main && git pull
```

`--squash` puts the whole branch on `main` as one commit, which keeps the history readable.
`--delete-branch` removes the branch locally and remotely so the branch list stays short.

`--squash`는 브랜치 전체를 하나의 커밋으로 `main`에 올려 히스토리를 읽기 쉽게 유지합니다.
`--delete-branch`는 로컬과 원격의 브랜치를 지워 목록을 깔끔하게 유지합니다.

## The day / 하루

| When / 시점               | What / 하는 일                                                                                                         |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Morning, 5 min / 아침 5분 | What merged yesterday, who is doing what today / 어제 뭐가 머지됐고 오늘 각자 뭘 하는지                                |
| During the day / 낮       | Repeat the loop. No coordination needed - your files are yours / 사이클 반복. 파일 주인이 다르니 따로 조율할 일이 없음 |
| Evening / 저녁            | Run the arena, log it in `experiments.md`, pick tomorrow's targets / 아레나 돌리고 기록, 내일 목표 정하기              |

## Why we do not collide / 왜 안 부딪히는가

Ownership is set in `.github/CODEOWNERS` so that the three of us edit different files. The
one place our work meets is `agent/world.py` - the shared state object everyone reads.

소유권이 `.github/CODEOWNERS`에 정해져 있어 셋이 서로 다른 파일을 고칩니다. 우리 작업이 만나는
유일한 지점은 모두가 읽는 공용 상태 객체 `agent/world.py`입니다.

**So the only rule you have to remember is: say something before you change `world.py`.**
Adding a field is usually safe; changing or removing one breaks other people's code.

**그래서 외워야 할 규칙은 하나뿐입니다: `world.py`를 바꾸기 전에 말할 것.** 필드를 추가하는
것은 대개 안전하지만, 기존 필드를 바꾸거나 지우면 다른 사람의 코드가 깨집니다.

## When it goes wrong / 막혔을 때

Three things go wrong. All three have a standard fix.

막히는 건 사실상 세 가지이고, 각각 정해진 대처법이 있습니다.

### CI is red / CI 빨간불

```bash
gh run view --log-failed     # 실패한 스텝의 로그만
pre-commit run --all-files   # 로컬에서 같은 검사 재현
pytest                       # 테스트만
```

Most red builds are formatting, and `pre-commit run --all-files` fixes those for you. Push
the fix to the same branch; the PR re-runs CI by itself.

빨간불의 대부분은 서식 문제이고 `pre-commit run --all-files`가 알아서 고쳐 줍니다. 같은
브랜치에 고친 것을 push하면 PR이 CI를 자동으로 다시 돌립니다.

A run that never appears is not the same as a failed run. GitHub sometimes takes a minute
or two to queue the run on a private repo, and `gh pr checks` will say "no checks reported"
until it does. Wait, then check `gh run list --event pull_request`. Do not merge a PR that
has genuinely never been checked.

런이 아예 안 뜨는 것과 실패한 것은 다릅니다. 비공개 저장소에서는 GitHub가 런을 대기열에
넣는 데 1~2분 걸릴 때가 있고, 그 전까지 `gh pr checks`는 "no checks reported"라고 말합니다.
잠시 기다렸다가 `gh run list --event pull_request`로 확인하세요. 검사가 한 번도 돌지 않은 PR을
머지하지는 마세요.

### Merge conflict / 머지 충돌

```bash
git switch main && git pull
git switch io/my-branch
git rebase main
# 충돌한 파일을 열어 고친 뒤
git add <파일>
git rebase --continue
```

Conflicts mean two branches changed the same lines. The real fix is prevention: short
branches, merged the same day.

충돌은 두 브랜치가 같은 줄을 고쳤다는 뜻입니다. 진짜 해법은 예방입니다. 브랜치를 짧게 가져가고
같은 날 머지하세요.

### `main` is broken / `main`이 깨졌을 때

Reverting beats fixing forward. Get `main` submittable again first, then work out what went
wrong on a branch.

고치는 것보다 되돌리는 게 먼저입니다. `main`을 다시 제출 가능한 상태로 만들어 놓고, 원인은
브랜치에서 따로 찾습니다.

```bash
git switch main && git pull
git revert <bad-commit-sha>
git push
```

## Rules of thumb / 경험칙

- A branch should live less than half a day. / 브랜치는 반나절을 넘기지 않기.
- Merge before you sleep. An unmerged branch is work nobody else can build on. / 자기 전에
  머지하기. 머지되지 않은 브랜치는 아무도 그 위에 쌓을 수 없는 작업입니다.
- Never leave `main` red overnight. / `main`을 빨간불로 둔 채 하루를 끝내지 않기.
- When in doubt, open the PR anyway - a PR is a question, not a commitment. / 애매하면 일단
  PR을 올리세요. PR은 확정이 아니라 질문입니다.
