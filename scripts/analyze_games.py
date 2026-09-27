"""이긴 경기와 진 경기를 나눠, 턴에 따라 무엇이 벌어지는지 비교한다 (진 경기 분석용).

사용법 (저장소 최상위에서):
    python scripts/analyze_games.py . git:f564d8b --seeds 100

A(첫 번째 봇)를 기준으로, 시드마다 진영을 바꿔 두 경기씩 둔다. 출력:
- 턴별(10·20·30·50·80·120) 평균 점수 차·건물 수 차·전투병 차·깃발병 차
- 건물 종류별 평균 보유 수 (구간별 A:B) — 어느 건물부터 밀리는가
- 상대가 우리 건물을 중립화한 횟수(종류별)와 국면 비율(A의 stderr 턴 로그)
전투병은 전투에서 양쪽이 같은 수만큼 상쇄되므로, 살아 있는 전투병 차이 = 생산량 차이다.
"""

from __future__ import annotations

import argparse
import re
import statistics as st
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import arena, mapgen, match
from sim.bots import resolve

KINDS = ("ENG", "HALL", "LIBRARY", "HOSPITAL", "DEPOT", "STATION", "PLAZA", "WATCH")
CHECKPOINTS = (10, 20, 30, 50, 80, 120)
SPANS = ((0, 30), (30, 60), (60, 100), (100, 161))


def summarize_game(task: tuple) -> dict:
    seed, a_team, a, b = task
    b_team = "K" if a_team == "Y" else "Y"
    spec = mapgen.generate(seed)
    rp = match.play(spec, {a_team: resolve(a), b_team: resolve(b)}, time_scale=None)
    frames, turns, buildings = rp["frames"], rp["turns"], rp["map"]["buildings"]
    winner = rp["result"]["winner"]

    def count(frame, team, kind):
        return sum(n for t, k, _, _, n in frame["units"] if t == team and k == kind)

    phases = Counter()
    for e in turns:
        m = re.search(r"#t \d+ [\d.]+ms (\w+)", e.get("stderr", {}).get(a_team, ""))
        phases[m.group(1) if m else "?"] += 1
    lost = Counter(buildings[ev["id"]]["kind"] for e in turns for ev in e["events"]
                   if ev["type"] == "neutralize" and ev["team"] == b_team)
    return {
        "result": "win" if winner == a_team else ("loss" if winner else "draw"),
        "diff": [f["score"][a_team] - f["score"][b_team] for f in frames],
        "owned": [sum(o == a_team for o in f["owner"]) - sum(o == b_team for o in f["owner"]) for f in frames],
        "w": [count(f, a_team, "W") - count(f, b_team, "W") for f in frames],
        "f": [count(f, a_team, "F") - count(f, b_team, "F") for f in frames],
        "kind": {k: [[sum(o == t for o, bd in zip(f["owner"], buildings) if bd["kind"] == k) for t in (a_team, b_team)]
                     for f in frames] for k in KINDS},
        "lost": dict(lost),
        "phases": dict(phases),
    }


def kind_share(r: dict, kind: str, side: int, lo: int, hi: int) -> float:
    """lo~hi-1턴 동안 한쪽(0 = A, 1 = B)이 이 종류 건물을 평균 몇 개 가졌나."""
    xs = r["kind"][kind][lo:hi]
    return sum(x[side] for x in xs) / max(1, len(xs))


def report(rows: list[dict]) -> str:
    out = [f"경기 {len(rows)}: " + " · ".join(f"{k} {v}" for k, v in Counter(r["result"] for r in rows).items())]
    for label, key in (("이긴 경기", "win"), ("진 경기", "loss")):
        grp = [r for r in rows if r["result"] == key]
        if not grp:
            continue
        out.append(f"\n-- {label} {len(grp)}")

        def at(r, name, t):
            return r[name][min(t, len(r[name]) - 1)]

        for t in CHECKPOINTS:
            out.append(f"  {t:3d}턴: 점수 차 {st.mean(at(r, 'diff', t) for r in grp):+5.1f} · 건물 수 차 "
                       f"{st.mean(at(r, 'owned', t) for r in grp):+4.1f} · 전투병 차 "
                       f"{st.mean(at(r, 'w', t) for r in grp):+5.1f} · 깃발병 차 {st.mean(at(r, 'f', t) for r in grp):+4.1f}")
        out.append("  건물 종류별 평균 보유 수 A:B")
        for k in KINDS:
            cells = []
            for lo, hi in SPANS:
                a = st.mean(kind_share(r, k, 0, lo, hi) for r in grp)
                b = st.mean(kind_share(r, k, 1, lo, hi) for r in grp)
                cells.append(f"{lo}-{hi - 1}턴 {a:.2f}:{b:.2f}")
            out.append(f"    {k:8s} " + " | ".join(cells))
        lost = Counter()
        for r in grp:
            lost.update(r["lost"])
        out.append("  상대가 우리 건물을 중립화한 횟수 (경기당): "
                   + ", ".join(f"{k} {v / len(grp):.1f}" for k, v in lost.most_common()))
        ph = Counter()
        for r in grp:
            ph.update(r["phases"])
        total = sum(ph.values())
        out.append("  국면 비율: " + ", ".join(f"{k} {v / total:.0%}" for k, v in ph.most_common()))
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description="이긴 경기와 진 경기 비교")
    p.add_argument("a", help="분석할 봇 (A)")
    p.add_argument("b", help="상대 봇 (B)")
    p.add_argument("--seed", type=int, default=0, help="시작 시드")
    p.add_argument("--seeds", type=int, default=50, help="맵 개수 (경기 수는 2배)")
    p.add_argument("--jobs", type=int, default=arena.default_jobs(), help="동시 경기 수")
    args = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tasks = [(s, t, args.a, args.b) for s in range(args.seed, args.seed + args.seeds) for t in ("Y", "K")]
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(summarize_game, tasks))
    print(f"A = {args.a}\nB = {args.b}\n" + report(rows))


if __name__ == "__main__":
    main()
