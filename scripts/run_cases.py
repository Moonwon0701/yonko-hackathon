"""스위치 조합(케이스)마다 봇 복사본을 만들어 여러 상대와 arena를 돌리고 표로 정리한다.

사용: python scripts/run_cases.py <케이스 파일.json> [--seeds 50] [--seed 200] [--vs git:origin/main git:origin/hyunjin/defense-econ]

케이스 파일: {"이름": {"NAME": 값, ...}, ...}. 값은 파이썬 리터럴 그대로 agent/strategy.py의 `NAME = ...` 한 줄을 바꾼다.
(한 줄짜리 최상위 상수만 바꾼다. 없는 이름이면 멈춘다.) 결과는 runs/cases-<시각>.md에도 남긴다.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINE = re.compile(r"A 기준\s+승 (\d+) · 무 (\d+) · 패 (\d+)\s+승점률 ([\d.]+)% \(95% 구간 (\d+)%–(\d+)%\)")
SCORE = re.compile(r"평균 점령 점수 A ([\d.]+) vs B ([\d.]+)")
LENGTH = re.compile(r"평균 경기 길이 (\d+)턴")
FORFEIT = re.compile(r"^([AB]): 몰수 (\d+)회", re.M)


def make_bot(name: str, overrides: dict, out: Path) -> Path:
    bot = out / re.sub(r"[^\w-]", "_", name)
    (bot / "agent").mkdir(parents=True)
    shutil.copy(ROOT / "main.py", bot / "main.py")
    for f in (ROOT / "agent").glob("*.py"):
        shutil.copy(f, bot / "agent" / f.name)
    path = bot / "agent" / "strategy.py"
    text = path.read_text(encoding="utf-8")
    for key, value in overrides.items():
        text, n = re.subn(rf"^{key} = .*$", f"{key} = {value!r}", text, count=1, flags=re.M)
        if n != 1:
            sys.exit(f"상수 {key}를 strategy.py에서 찾지 못했다 (케이스 {name})")
    path.write_text(text, encoding="utf-8")
    return bot


def arena(bot: Path, vs: str, seeds: int, seed: int, jobs: int | None) -> dict:
    cmd = [sys.executable, "-m", "sim", "arena", str(bot), vs, "--seeds", str(seeds), "--seed", str(seed), "--save", "none"]
    if jobs:
        cmd += ["--jobs", str(jobs)]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    m = LINE.search(out)
    if not m:
        return {"error": out[-400:]}
    sc, ln = SCORE.search(out), LENGTH.search(out)
    ff = {k: int(v) for k, v in FORFEIT.findall(out)}
    return {"w": int(m[1]), "d": int(m[2]), "l": int(m[3]), "rate": float(m[4]), "lo": int(m[5]), "hi": int(m[6]),
            "ours": float(sc[1]) if sc else None, "theirs": float(sc[2]) if sc else None, "turns": int(ln[1]) if ln else None, "ff": f"{ff.get('A', 0)}/{ff.get('B', 0)}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases")
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--seed", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--vs", nargs="+", default=["git:origin/main", "git:origin/hyunjin/defense-econ"])
    ap.add_argument("--only", nargs="*", default=None, help="이 이름의 케이스만")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    rows = []
    header = "| 케이스 | " + " | ".join(f"{v} 승점률 (구간)" for v in args.vs) + " | 점령 점수 (우리:상대) |"
    print(header)
    with tempfile.TemporaryDirectory() as tmp:
        # 실행 도중 strategy.py를 고쳐도 섞이지 않게, 모든 케이스 봇을 시작할 때 한꺼번에 복사한다
        bots = {name: make_bot(name, ov, Path(tmp)) for name, ov in cases.items() if not args.only or name in args.only}
        for name, bot in bots.items():
            cells, scores = [], []
            for vs in args.vs:
                r = arena(bot, vs, args.seeds, args.seed, args.jobs)
                if "error" in r:
                    cells.append("ERR")
                    print(r["error"])
                    continue
                cells.append(f"{r['rate']:.1f}% ({r['lo']}–{r['hi']}) {r['w']}-{r['d']}-{r['l']} 몰수 {r['ff']}")
                scores.append(f"{r['ours']}:{r['theirs']}")
            row = f"| {name} | " + " | ".join(cells) + f" | {' / '.join(scores)} |"
            print(row, flush=True)
            rows.append(row)
    stamp = time.strftime("%m%d-%H%M%S")
    out = ROOT / "runs" / f"cases-{stamp}{args.tag}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(f"seeds {args.seed}~{args.seed + args.seeds - 1} (경기 {args.seeds * 2})\n\n{header}\n| --- |" + " --- |" * (len(args.vs) + 1) + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
