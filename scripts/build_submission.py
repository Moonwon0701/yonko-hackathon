"""제출 ZIP을 만들고, 풀어서 실제로 한 판(가짜 입력) 돌려 본다.

사용법 (저장소 최상위에서):
    python scripts/build_submission.py

결과: dist/bot-<커밋 해시>.zip  (커밋 안 된 변경이 있으면 이름에 -dirty가 붙는다)

ZIP에는 submission.json, main.py, agent/*.py만 넣는다. 규칙(docs/game-api.md 9절)에 어긋나면
만들지 않고 이유를 출력한다.
"""

import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from fake_input import random_game

ALLOWED_PATH = re.compile(r"^[A-Za-z0-9_.\-/]+$")
MAX_ZIP_BYTES = 5 * 1024 * 1024
MAX_UNZIPPED_BYTES = 20 * 1024 * 1024
MAX_FILES = 200
TURNS = 160


def collect() -> list[Path]:
    files = [ROOT / "submission.json", ROOT / "main.py"]
    files += sorted((ROOT / "agent").glob("*.py"))
    return files


def version() -> str:
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False,
        ).stdout
    sha = git("rev-parse", "--short", "HEAD").strip() or "nogit"
    return sha + ("-dirty" if git("status", "--porcelain", "--", "main.py", "agent").strip() else "")


def check(files: list[Path]) -> list[str]:
    problems = []
    names = [f.relative_to(ROOT).as_posix() for f in files]
    problems += [f"허용되지 않는 경로 문자: {n}" for n in names if not ALLOWED_PATH.match(n)]
    if len(files) > MAX_FILES:
        problems.append(f"파일 {len(files)}개 > {MAX_FILES}")
    total = sum(f.stat().st_size for f in files)
    if total > MAX_UNZIPPED_BYTES:
        problems.append(f"해제 크기 {total} B > 20 MiB")
    return problems


def smoke_test(zip_path: Path) -> None:
    """ZIP을 풀어 서버처럼 main.py를 실행하고 160턴 모두 END가 오는지 본다."""
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "main.py"], cwd=tmp, input=random_game(seed=0, turns=TURNS),
            capture_output=True, text=True, timeout=120, check=False,
        )
        elapsed = time.perf_counter() - start
    ends = result.stdout.splitlines().count("END")
    if result.returncode != 0 or ends != TURNS:
        sys.exit(f"스모크 테스트 실패: 종료 코드 {result.returncode}, END {ends}/{TURNS}\n{result.stderr}")
    if result.stderr:
        print(f"경고: stderr 출력이 있음\n{result.stderr[:2000]}")
    print(f"스모크 테스트 통과: {TURNS}턴 모두 END, 전체 {elapsed:.2f}s (턴당 평균 {elapsed / TURNS * 1000:.1f} ms)")


def main() -> None:
    files = collect()
    problems = check(files)
    if problems:
        sys.exit("ZIP을 만들지 않음:\n" + "\n".join(problems))

    out = ROOT / "dist" / f"bot-{version()}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, arcname=f.relative_to(ROOT).as_posix())
    if out.stat().st_size > MAX_ZIP_BYTES:
        sys.exit(f"ZIP 크기 {out.stat().st_size} B > 5 MiB")

    print(f"{out.relative_to(ROOT)}  ({out.stat().st_size} B)")
    for f in files:
        print("  " + f.relative_to(ROOT).as_posix())
    smoke_test(out)


if __name__ == "__main__":
    main()
