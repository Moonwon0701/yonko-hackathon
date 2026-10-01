"""직접 대결: 후보 설정 여럿을 같은 상대·같은 새 랜덤 시드 맵으로 붙여 승점률을 비교한다.

사용법 (저장소 최상위에서):
    python scripts/h2h.py --opp git:074803e --opp opponents/strong_wide.py --seed 40000 --seeds 200 \
        base= "guard=FLAG_GUARD_SCORE=3" "both=FLAG_GUARD_SCORE=3 EARLY_GUARD=6"

후보 = "이름=상수 덮어쓰기"(비우면 봇 그대로). 후보 봇은 --bot 폴더(기본 저장소 최상위)를 scripts/cfg_bot.py로 실행하므로
학습 가중치는 봇에 박힌 그대로다. 시드마다 진영 하나(짝수 Y, 홀수 K). 서버 맵은 쓰지 않는다(리더보드·최종 평가는 매번
랜덤 시드 맵). 결과는 runs/h2h/<시각>.jsonl.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import mapgen, match  # noqa: E402
from sim.bots import BotSpec, resolve  # noqa: E402

LAUNCHER = ROOT / "scripts" / "cfg_bot.py"


def play_one(task: tuple) -> dict:
    name, cfg, bot, opp, seed, scale = task
    side = "YK"[seed % 2]
    other = "K" if side == "Y" else "Y"
    me = BotSpec(f"{name}", (sys.executable, str(LAUNCHER), bot, cfg), bot)
    try:
        result = match.play(mapgen.generate(seed), {side: me, other: resolve(opp)}, time_scale=scale,
                            record=False)["result"]
    except Exception as e:  # noqa: BLE001 — 한 경기 오류로 전체를 멈추지 않는다
        return {"cand": name, "opp": opp, "seed": seed, "error": str(e)}
    winner = result["winner"]
    return {"cand": name, "opp": opp, "seed": seed, "side": side, "reason": result["reason"],
            "score": 1.0 if winner == side else 0.5 if winner is None else 0.0,
            "max_ms": result.get("max_ms", {}).get(side), "opp_max_ms": result.get("max_ms", {}).get(other)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cands", nargs="+", help='이름=상수 덮어쓰기 ("이름=값 이름=값", 비우면 봇 그대로)')
    ap.add_argument("--bot", default=str(ROOT), help="후보 봇 폴더 또는 git:참조 (기본 저장소 최상위)")
    ap.add_argument("--opp", action="append", required=True, help="상대 (여러 번 가능, sim 지정 형식)")
    ap.add_argument("--seed", type=int, default=40000)
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--time-scale", type=float, default=3.0,
                    help="응답 제한 배율. 여러 경기를 한꺼번에 돌리면 CPU가 붐벼 제한(300 ms)을 넘는 몰수가 섞인다(22작업·배율 1에서 10~16%%)")
    args = ap.parse_args()
    cands = [c.partition("=")[::2] for c in args.cands]
    if args.bot.startswith("git:"):  # 다른 브랜치의 봇도 후보로: runs/bots/<커밋>에 풀어 둔 폴더를 쓴다
        args.bot = resolve(args.bot).cwd
    for opp in args.opp:
        resolve(opp)  # git 봇을 미리 풀어 둔다 (작업자끼리 겹치지 않게)
    tasks = [(name, cfg, str(Path(args.bot).resolve()), opp, s, args.time_scale)
             for opp in args.opp for s in range(args.seed, args.seed + args.seeds) for name, cfg in cands]
    out = ROOT / "runs" / "h2h"
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    table: dict[tuple[str, str], list[float]] = {}
    errors = 0
    forfeits: dict[tuple[str, str], int] = {}
    slowest: dict[str, float] = {}
    with ProcessPoolExecutor(args.jobs) as ex, (out / f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl").open("w") as log:
        log.write(json.dumps({"cands": dict(cands), "bot": args.bot, "seed": args.seed, "seeds": args.seeds},
                             ensure_ascii=False) + "\n")
        for row in ex.map(play_one, tasks, chunksize=1):
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            if "error" in row:
                errors += 1
                continue
            table.setdefault((row["cand"], row["opp"]), []).append(row["score"])
            key = (row["cand"], row["opp"])
            forfeits[key] = forfeits.get(key, 0) + (row["reason"] == "forfeit")
            slowest[row["cand"]] = max(slowest.get(row["cand"], 0.0), row["max_ms"] or 0.0)
    print(f"{len(tasks)}경기, {time.perf_counter() - started:.0f}초, 오류 {errors}")
    for opp in args.opp:
        print(f"\n상대 {opp}")
        for name, _ in cands:
            res = table.get((name, opp), [])
            n = max(1, len(res))
            p = sum(res) / n
            se = math.sqrt(max(p * (1 - p), 1e-9) / n)
            w, d, l = sum(x == 1 for x in res), sum(x == 0.5 for x in res), sum(x == 0 for x in res)
            print(f"  {name:10s} {p:.3f} ±{1.96 * se:.3f} ({w}-{d}-{l}, {len(res)}판, 몰수 {forfeits.get((name, opp), 0)})")
    print("\n후보별 최대 응답(ms, 시간 배율 적용 전 실측): " + ", ".join(f"{k} {v:.0f}" for k, v in slowest.items()))


if __name__ == "__main__":
    main()
