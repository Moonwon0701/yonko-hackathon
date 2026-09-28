"""상대 풀 평가: 봇 A를 흉내 봇 풀과 여러 시드로 붙여 승점률과 운용 지표를 상대마다 낸다.

사용법 (저장소 최상위에서):
    python scripts/eval_pool.py git:main                         # 기본 풀, 시드 100~119 (상대마다 40경기)
    python scripts/eval_pool.py . --seeds 50 --seed 200
    python scripts/eval_pool.py . --pool opponents/eng_rush.py git:origin/sunghyuk/attack-expand

지표는 `scripts/profile_opponents.py`와 같은 정의다(로컬 경기를 서버 리플레이 형식으로 바꿔 같은 함수로 잰다).
흉내가 맞는지 볼 때는 서버에서 진 경기의 모습과 비교한다(docs/benchmarks.md "서버 리더보드" 표 2026-09-28 분석):
- 생산(20~80턴 전투병): 진 경기 4판은 상대가 46~99명 많음
- 전투병 값 3 비율(1~80턴): 진 경기 5판 우리 25~74%, 상대 0~21%
- 10~30턴 운용: 강팀 호위 62%·수비 배치 43%·전투병 칸 20.4·전투 뒤 남음 42%·상대 진영 전투 50%
"""

from __future__ import annotations

import argparse
import math
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from profile_opponents import economy, from_local, tactics

from sim import mapgen, match
from sim.bots import resolve

POOL = ("opponents/eng_rush.py", "opponents/econ_raid.py", "opponents/wide.py", "opponents/blob.py")
TACTICS = ("escort", "garrison", "stacks", "won", "battle_away", "fdead")


def play_one(task: tuple) -> dict:
    seed, a_team, a, b = task
    b_team = "K" if a_team == "Y" else "Y"
    replay = match.play(mapgen.generate(seed), {a_team: resolve(a), b_team: resolve(b)})
    winner = replay["result"]["winner"]
    r = from_local(replay, a_team)
    return {
        "b": b,
        "outcome": 1.0 if winner == a_team else 0.5 if winner is None else 0.0,
        "economy": economy(r),
        "a": tactics(r, a_team, 10, 30),
        "o": tactics(r, b_team, 10, 30),
    }


def mean(rows: list[dict], key: str) -> float | None:
    vals = [r[key] for r in rows if r.get(key) is not None]
    return st.mean(vals) if vals else None


def pct(v: float | None) -> str:
    return "-" if v is None else f"{v:.0%}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", help="평가할 봇 (sim 봇 지정: ., git:main, 파일 경로 ...)")
    ap.add_argument("--pool", nargs="+", default=list(POOL), help="상대 봇들")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--seed", type=int, default=100, help="시작 시드")
    ap.add_argument("--jobs", type=int, default=6)
    args = ap.parse_args()
    a = resolve(args.a).name  # git: 참조는 여기서 한 번 풀어 둔다 (작업자마다 풀면 같은 폴더에 동시에 쓴다)
    for b in args.pool:
        resolve(b)
    tasks = [(seed, team, args.a, b) for b in args.pool
             for seed in range(args.seed, args.seed + args.seeds) for team in ("Y", "K")]
    with ProcessPoolExecutor(args.jobs) as ex:
        rows = list(ex.map(play_one, tasks))
    print(f"A = {a}, 시드 {args.seed}~{args.seed + args.seeds - 1} × 진영 교대")
    head = ["상대", "경기", "A 승점률 (95%)", "생산W A:상대", "값3 A:상대", "A 공학관 잃음",
            *[f"{c} A:상대" for c in TACTICS]]
    print("\t".join(head))
    for b in args.pool:
        sel = [r for r in rows if r["b"] == b]
        n = len(sel)
        p = st.mean(r["outcome"] for r in sel)
        half = 1.96 * math.sqrt(p * (1 - p) / n)
        eco = [r["economy"] for r in sel]
        lost = sum(e.get("eng_lost") is not None for e in eco) / n
        cells = [f"{Path(b).stem if not b.startswith('git:') else b}", str(n),
                 f"{p:.0%} ({max(0, p - half):.0%}–{min(1, p + half):.0%})",
                 f"{mean(eco, 'prodW') or 0:.0f}:{mean(eco, 'oprodW') or 0:.0f}",
                 f"{pct(mean(eco, 'cost3'))}:{pct(mean(eco, 'ocost3'))}", pct(lost)]
        for c in TACTICS:
            va, vo = mean([r["a"] for r in sel], c), mean([r["o"] for r in sel], c)
            if c in ("stacks", "fdead"):
                cells.append(f"{va or 0:.1f}:{vo or 0:.1f}")
            else:
                cells.append(f"{pct(va)}:{pct(vo)}")
        print("\t".join(cells))


if __name__ == "__main__":
    main()
