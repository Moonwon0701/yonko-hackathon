"""ES 후보 θ 여럿을 같은 경기로 비교: 후보마다 상대 × (서버 맵 + 생성 시드 묶음), 맵마다 진영 하나.

사용법 (저장소 최상위에서):
    python scripts/es_eval.py --bot experiments/learned_uo --opp git:daa1888 --seed 8400 --seeds 400 \
        g70=runs/es/<시각>/theta_g70.json g140=... zero=
    (θ 경로를 비우면 θ = 0 = 기준 봇)

학습(매 세대 새 시드 10만~)·검증(90만~)에 쓰지 않은 시드와 서버 맵으로 잰다. 모든 경기 결과는 runs/es_eval/<시각>.jsonl.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cands", nargs="+", help="이름=θ.json (비우면 θ = 0)")
    ap.add_argument("--bot", default="experiments/learned_uo")
    ap.add_argument("--cfg", default="", help='봇의 strategy 상수 덮어쓰기 "이름=값 ..." (es_bot.py ES_CFG)')
    ap.add_argument("--opp", action="append", required=True, help="상대 (여러 번 가능)")
    ap.add_argument("--seed", type=int, default=8400)
    ap.add_argument("--seeds", type=int, default=400)
    ap.add_argument("--no-server", action="store_true")
    ap.add_argument("--jobs", type=int, default=22)
    args = ap.parse_args()
    os.environ["ES_BOT"] = args.bot  # 작업자 프로세스가 es_train을 불러올 때 이 봇 폴더를 쓴다
    os.environ["ES_CFG"] = args.cfg
    sys.path.insert(0, str(ROOT / "scripts"))
    import es_train
    from sim import mapgen
    from sim.bots import resolve

    out = ROOT / "runs" / "es_eval"
    out.mkdir(parents=True, exist_ok=True)
    zero = out / "zero.json"
    zero.write_text("{}")
    cands = {}
    for c in args.cands:
        name, _, path = c.partition("=")
        cands[name] = str(Path(path).resolve()) if path else str(zero)
    for opp in args.opp:
        resolve(opp)
    sets = {} if args.no_server else {"server": mapgen.load_server_maps(ROOT / "data" / "server-replays")}
    sets[f"seed{args.seed}"] = list(range(args.seed, args.seed + args.seeds))
    tasks = [((name, opp, set_name, i), m, "YK"[i % 2], path, opp)
             for name, path in cands.items() for opp in args.opp
             for set_name, maps in sets.items() for i, m in enumerate(maps)]
    started = time.perf_counter()
    table: dict[tuple, list[float]] = {}
    with ProcessPoolExecutor(args.jobs) as ex, (out / f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl").open("w") as log:
        for (name, opp, set_name, i), r, info in ex.map(es_train.play_one, tasks, chunksize=2):
            log.write(json.dumps({"cand": name, "opp": opp, "set": set_name, "map": i,
                                  "reward": r, "info": info}, ensure_ascii=False) + "\n")
            if r is not None:
                table.setdefault((name, opp, set_name), []).append(info[0])
    print(f"{len(tasks)}경기, {time.perf_counter() - started:.0f}초")
    for opp in args.opp:
        print(f"\n상대 {opp}")
        for name in cands:
            cells, total = [], []
            for set_name in sets:
                res = table.get((name, opp, set_name), [])
                total += res
                w, d, l = sum(x == 1 for x in res), sum(x == 0.5 for x in res), sum(x == 0 for x in res)
                cells.append(f"{set_name} {sum(res) / max(1, len(res)):.3f} ({w}-{d}-{l})")
            print(f"  {name:8s} 합계 {sum(total) / max(1, len(total)):.3f} ({len(total)}판) | " + " | ".join(cells))


if __name__ == "__main__":
    main()
