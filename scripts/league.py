"""리그: 여러 봇을 서로 모두 붙여(라운드 로빈) 누가 가장 강한지 본다.

사용법 (저장소 최상위에서):
    python scripts/league.py 테마=git:origin/moonwon/eval-tuning main=git:main 러시=opponents/eng_rush.py --seeds 50
    python scripts/league.py ... --maps data/server-replays        # 서버 맵(같은 지형은 하나로)으로

봇은 `이름=지정` 또는 지정만 쓴다(지정은 sim과 같다: ., git:참조, 파일·폴더 경로). 두 봇마다 맵 × 진영 교대로 두고,
승 1 · 무 0.5 · 패 0으로 센다. 출력: 상대별 승점률 표와, 다른 모든 봇 상대 평균 승점률 순위.
결과는 `runs/league/<시각>/games.jsonl`에 남는다.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import mapgen, match
from sim.bots import resolve


def play_one(task: tuple) -> dict:
    i, j, seed, i_team, specs = task
    j_team = "K" if i_team == "Y" else "Y"
    if isinstance(seed, tuple):
        name, spec = seed
    else:
        name, spec = seed, mapgen.generate(seed)
    result = match.play(spec, {i_team: resolve(specs[i]), j_team: resolve(specs[j])}, record=False)["result"]
    winner = result["winner"]
    return {"i": i, "j": j, "map": name, "i_team": i_team, "reason": result["reason"],
            "score": 1.0 if winner == i_team else 0.5 if winner is None else 0.0}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bots", nargs="+", help="이름=지정 또는 지정")
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--seed", type=int, default=5000)
    ap.add_argument("--maps", help="서버 리플레이 폴더 (주면 --seeds 대신)")
    ap.add_argument("--jobs", type=int, default=20)
    args = ap.parse_args()
    names, specs = [], []
    for item in args.bots:
        name, _, spec = item.rpartition("=")
        names.append(name or spec)
        specs.append(spec)
        resolve(spec)  # git: 참조를 미리 풀어 둔다 (작업자마다 풀면 같은 폴더에 동시에 쓴다)
    maps = mapgen.load_server_maps(args.maps) if args.maps else list(range(args.seed, args.seed + args.seeds))
    tasks = [(i, j, m, team, specs) for i, j in combinations(range(len(specs)), 2) for m in maps for team in ("Y", "K")]
    out = ROOT / "runs" / "league" / time.strftime("%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with ProcessPoolExecutor(args.jobs) as ex:
        rows = list(ex.map(play_one, tasks))
    with open(out / "games.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps({**r, "i": names[r["i"]], "j": names[r["j"]]}, ensure_ascii=False) + "\n" for r in rows)
    n = len(names)
    score = [[None] * n for _ in range(n)]
    for i, j in combinations(range(n), 2):
        s = st.mean(r["score"] for r in rows if r["i"] == i and r["j"] == j)
        score[i][j], score[j][i] = s, 1 - s
    where = f"서버 맵 {len(maps)}개" if args.maps else f"시드 {args.seed}~{args.seed + args.seeds - 1}"
    print(f"{where} × 진영 교대, 한 쌍 {2 * len(maps)}경기, 모두 {len(rows)}경기 ({time.perf_counter() - started:.0f}초)")
    print("\n행 봇의 승점률 (열 봇 상대)")
    print("\t".join(["", *names]))
    for i in range(n):
        print("\t".join([names[i], *("-" if i == j else f"{score[i][j]:.0%}" for j in range(n))]))
    games = 2 * len(maps) * (n - 1)
    print(f"\n순위 (다른 {n - 1}개 봇 상대 평균, 봇마다 {games}경기)")
    ranked = sorted(range(n), key=lambda i: -st.mean(score[i][j] for j in range(n) if j != i))
    for rank, i in enumerate(ranked, 1):
        p = st.mean(score[i][j] for j in range(n) if j != i)
        half = 1.96 * math.sqrt(p * (1 - p) / games)
        worst = min((score[i][j], names[j]) for j in range(n) if j != i)
        print(f"{rank}. {names[i]}\t{p:.1%} (±{half:.1%})\t가장 약한 상대: {worst[1]} {worst[0]:.0%}")
    print(f"\n기록: {out}")


if __name__ == "__main__":
    main()
