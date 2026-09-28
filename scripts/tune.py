"""파라미터 자동 탐색 (좌표 탐색): `agent/strategy.py`의 상수를 하나씩 바꿔 상대 풀 승점률이 오르는 값을 찾는다.

사용법 (저장소 최상위에서):
    python scripts/tune.py                          # 기준 = HEAD, 기본 풀, 1바퀴
    python scripts/tune.py --base git:main --rounds 2 --seeds 20
    python scripts/tune.py --check "MAX_FLAGS=7 ETA_OFFSET=1" --seeds 50 --seed 3000   # 한 설정만 기준과 비교

방법:
- 후보 봇 = 기준 커밋의 `main.py`·`agent/`(sim의 git: 봇 폴더) + 상수 덮어쓰기. 상수마다 작은 런처 파일을 만든다.
- 점수 = 상대 풀(흉내 봇 + 기준 봇 자신)과 학습 시드 × 진영 교대로 둔 경기의 평균 승점(승 1, 무 0.5, 패 0).
  기준 봇 자신을 풀에 넣어, 흉내 봇에만 맞추느라 원래 상대에게 약해지는 것을 막는다.
- 한 바퀴 = 상수를 차례로 돌며, 지금 값 말고 격자(GRID)의 다른 값을 모두 둔다. 가장 좋은 값이 학습 시드에서
  지금보다 MARGIN 이상 높으면, 검증 시드(학습과 다른 맵)에서도 지금보다 높을 때만 채택한다(잡음으로 뽑힌 값 거르기).
- 모든 평가를 `runs/tune/<시각>/log.jsonl`에 남긴다.

실행 중에 읽히는 상수만 넣었다. `DANGER_DISCOUNT`·`HOLD_TURNS`는 파일을 불러올 때 행동 트리에 값이 박혀 덮어써도
효과가 없어 뺐다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics as st
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import mapgen, match
from sim.bots import BotSpec, resolve

POOL = ("opponents/eng_rush.py", "opponents/econ_raid.py", "opponents/wide.py", "opponents/blob.py")
MARGIN = 0.02

# 상수 → 둘러볼 값. 지금 값(main 8fd93ee)을 가운데에 두고 양쪽으로 한 칸씩. "A.B"는 dict 상수 A의 키 B.
# 탐색의 출발점(지금 값)은 격자가 아니라 기준 봇에서 읽는다(defaults)
GRID: dict[str, list] = {
    "MIN_WARRIORS": [1, 3, 5],
    "SPARE_FLAGS": [0, 1, 2],
    "MIN_FLAGS": [1, 2, 3],
    "MAX_FLAGS": [4, 6, 8],
    "BEHIND_EXTRA_FLAGS": [0, 1, 2],
    "HALL_VALUE_PER_TURN": [0.01, 0.02, 0.04],
    "DEPOT_VALUE": [1.0, 2.0, 4.0],
    "FUNCTION_VALUE.ENG": [1.0, 2.0, 4.0],
    "ETA_OFFSET": [1, 2, 4],
    "KILL_VALUE": [0.5, 1.0, 2.0],
    "GUARD_RADIUS": [2, 3, 4],
    "THREAT_PRESSURE": [1.0, 2.0, 3.0],
    "LATE_TURN": [90, 110, 130],
    "ATTACK_MARGIN": [0, 2, 5],
    "EVICT_RADIUS": [1, 2, 3],
    "EVICT_WEIGHT": [0.5, 1.0, 2.0],
    "FRONT_SURPLUS": [5, 10, 20],
    "FRONT_COUNT": [2, 3, 5],
    "RAID_STEAL": [1.0, 2.0, 3.0],
    # 구조 변경 스위치 (첫 값 = 끔 또는 예전 동작)
    "ESCORT_VALUE": [0.0, 0.5, 1.0, 2.0],
    "ECON_EVICT_RADIUS": [2, 3, 4],
    "ECON_WEIGHT": [1.0, 2.0, 3.0],
}


def defaults(base: BotSpec) -> dict:
    """기준 봇의 실제 상수값 (탐색의 출발점). 기준 봇 폴더에서 따로 불러야 작업 폴더의 agent와 섞이지 않는다."""
    code = ("import json; from agent import strategy as s; names = json.loads(input()); "
            "print(json.dumps({n: (getattr(s, n.split('.')[0])[n.split('.')[1]] if '.' in n else getattr(s, n)) "
            "for n in names}))")
    out = subprocess.run([sys.executable, "-c", code], cwd=base.cwd, input=json.dumps(list(GRID)),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def launcher(base: BotSpec, params: dict, folder: Path) -> str:
    """기준 봇 폴더를 불러와 상수를 덮어쓰고 main을 도는 런처 파일. 같은 설정이면 같은 파일."""
    body = [
        "import sys",
        f"sys.path.insert(0, {base.cwd!r})",
        "from agent import strategy as s",
    ]
    for name, value in sorted(params.items()):
        if "." in name:
            table, key = name.split(".", 1)
            body.append(f"s.{table}[{key!r}] = {value!r}")
        else:
            body.append(f"s.{name} = {value!r}")
    body += ["import main", "main.main()", ""]
    text = "\n".join(body)
    path = folder / f"bot_{hashlib.sha1(text.encode()).hexdigest()[:10]}.py"
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return str(path)


def play_one(task: tuple) -> tuple[str, float]:
    seed, a_team, a, b = task
    b_team = "K" if a_team == "Y" else "Y"
    result = match.play(mapgen.generate(seed), {a_team: resolve(a), b_team: resolve(b)}, record=False)["result"]
    winner = result["winner"]
    return b, 1.0 if winner == a_team else 0.5 if winner is None else 0.0


class Tuner:
    def __init__(self, base: str, pool: list[str], jobs: int, out: Path) -> None:
        self.base = resolve(base)
        self.pool = [self.base.cwd + "/main.py", *pool]  # 기준 봇 자신 + 흉내 봇
        self.jobs = jobs
        self.out = out
        (out / "bots").mkdir(parents=True, exist_ok=True)
        self.log = open(out / "log.jsonl", "a", encoding="utf-8")  # noqa: SIM115 — 탐색 내내 연다
        self.cache: dict[tuple, dict] = {}
        self.defaults = defaults(self.base)

    def score(self, params: dict, seeds: range) -> dict:
        """`params`로 덮어쓴 봇의 풀 평균 승점과 상대별 승점."""
        key = (tuple(sorted(params.items())), seeds.start, seeds.stop)
        if key in self.cache:
            return self.cache[key]
        bot = launcher(self.base, params, self.out / "bots")
        tasks = [(seed, team, bot, b) for b in self.pool for seed in seeds for team in ("Y", "K")]
        started = time.perf_counter()
        with ProcessPoolExecutor(self.jobs) as ex:
            rows = list(ex.map(play_one, tasks))
        per = {Path(b).stem if b != self.pool[0] else "base": st.mean(v for bb, v in rows if bb == b)
               for b in self.pool}
        found = {"mean": st.mean(per.values()), "per": per, "games": len(rows)}
        self.log.write(json.dumps({"params": params, "seeds": [seeds.start, seeds.stop - 1], **found,
                                   "sec": round(time.perf_counter() - started, 1)}, ensure_ascii=False) + "\n")
        self.log.flush()
        self.cache[key] = found
        return found


def fmt(found: dict) -> str:
    return f"{found['mean']:.1%} (" + ", ".join(f"{k} {v:.0%}" for k, v in found["per"].items()) + ")"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="git:HEAD", help="기준 봇 (git: 참조)")
    ap.add_argument("--pool", nargs="+", default=list(POOL))
    ap.add_argument("--seeds", type=int, default=20, help="학습·검증 시드 수")
    ap.add_argument("--seed", type=int, default=1000, help="학습 시드 시작 (검증은 +1000)")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=20)
    ap.add_argument("--only", nargs="+", help="이 상수만 탐색")
    ap.add_argument("--check", help='"이름=값 이름=값" 설정 하나를 기준과 비교만 한다')
    args = ap.parse_args()
    out = ROOT / "runs" / "tune" / time.strftime("%m%d-%H%M%S")
    tuner = Tuner(args.base, args.pool, args.jobs, out)
    train = range(args.seed, args.seed + args.seeds)
    valid = range(args.seed + 1000, args.seed + 1000 + args.seeds)
    print(f"기준 {tuner.base.name}, 풀 {len(tuner.pool)}개, 학습 시드 {train.start}~{train.stop - 1}, "
          f"검증 {valid.start}~{valid.stop - 1}, 기록 {out}", flush=True)

    if args.check:
        params = {}
        for item in args.check.split():
            name, value = item.split("=")
            params[name] = type(GRID[name][0])(value) if name in GRID else float(value)
        print("기준 :", fmt(tuner.score({}, train)), flush=True)
        print("설정 :", fmt(tuner.score(params, train)), flush=True)
        return

    current: dict = {}
    best = tuner.score(current, train)
    print(f"시작 {fmt(best)}", flush=True)
    names = args.only or list(GRID)
    for rnd in range(1, args.rounds + 1):
        changed = False
        for name in names:
            now = current.get(name, tuner.defaults[name])
            trials = [(value, tuner.score({**current, name: value}, train)) for value in GRID[name] if value != now]
            value, found = max(trials, key=lambda t: t[1]["mean"])
            line = "  ".join(f"{v}: {f['mean']:.1%}" for v, f in trials)
            if found["mean"] < best["mean"] + MARGIN:
                print(f"[{rnd}] {name} = {now} 유지 (지금 {best['mean']:.1%} | {line})", flush=True)
                continue
            here = tuner.score(current, valid)
            there = tuner.score({**current, name: value}, valid)
            if there["mean"] <= here["mean"]:
                print(f"[{rnd}] {name} = {now} 유지 — 학습 {found['mean']:.1%} 이지만 검증 "
                      f"{there['mean']:.1%} ≤ {here['mean']:.1%} (지금 {best['mean']:.1%} | {line})", flush=True)
                continue
            current[name] = value
            best = found
            changed = True
            print(f"[{rnd}] {name} = {now} → {value} 채택: 학습 {fmt(found)}, 검증 {here['mean']:.1%} → "
                  f"{there['mean']:.1%}", flush=True)
        if not changed:
            break
    print("최종 설정:", " ".join(f"{k}={v}" for k, v in current.items()) or "(바뀐 것 없음)", flush=True)
    (out / "result.json").write_text(json.dumps({"params": current, "train": best}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")


if __name__ == "__main__":
    main()
