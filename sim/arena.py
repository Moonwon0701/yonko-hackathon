"""아레나: 봇 A와 B를 여러 맵에서 진영을 바꿔 가며 붙이고 성적을 요약한다.

시드 하나마다 두 경기(A가 Y, A가 K)를 둔다. 스타터 봇처럼 진영 기준으로 정규화한 봇끼리는
점대칭 맵에서 진영만 바꾼 두 경기가 같은 결과를 내야 하므로, 진영 편향이 섞이지 않는다.
"""

from __future__ import annotations

import json
import math
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from sim import mapgen, match, viewer
from sim.bots import BotSpec


def _play_one(task: tuple) -> dict:
    seed, a_team, bots, time_scale, save_dir, save_mode = task
    spec = mapgen.generate(seed)
    replay = match.play(spec, bots, time_scale=time_scale, record=save_mode != "none")
    res = replay["result"]
    b_team = "K" if a_team == "Y" else "Y"
    outcome = "draw" if res["winner"] is None else ("win" if res["winner"] == a_team else "loss")
    row = {
        "seed": seed, "a_team": a_team, "outcome": outcome, "reason": res["reason"],
        "turn": res["turn"],
        "score": {"A": res["score"][a_team], "B": res["score"][b_team]},
        "occupation": {"A": res["occupation"][a_team], "B": res["occupation"][b_team]},
        "max_ms": {"A": res["max_ms"][a_team], "B": res["max_ms"][b_team]},
        "first_ms": {"A": res["first_ms"][a_team], "B": res["first_ms"][b_team]},
        "forfeit": {("A" if t == a_team else "B"): why
                    for t, why in res.get("detail", {}).items()},
    }
    if res["ignored_commands"] is not None:
        row["ignored"] = {"A": res["ignored_commands"][a_team], "B": res["ignored_commands"][b_team]}
    if save_mode == "all" or (save_mode == "losses" and outcome != "win"):
        path = Path(save_dir) / f"seed{seed:04d}-A_is_{a_team}-{outcome}.html"
        viewer.write_html(replay, path)
        row["replay"] = str(path)
    return row


def run(a: BotSpec, b: BotSpec, seeds: list[int], *, jobs: int, time_scale: float | None,
        save_dir: Path, save_mode: str = "losses", progress=None) -> list[dict]:
    tasks = []
    for seed in seeds:
        for a_team in ("Y", "K"):
            bots = {a_team: a, ("K" if a_team == "Y" else "Y"): b}
            tasks.append((seed, a_team, bots, time_scale, str(save_dir), save_mode))
    rows = []
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(_play_one, t) for t in tasks]
        for fut in as_completed(futures):
            rows.append(fut.result())
            if progress:
                progress(len(rows), len(tasks))
    rows.sort(key=lambda r: (r["seed"], r["a_team"]))
    save_dir.mkdir(parents=True, exist_ok=True)
    with open(save_dir / "results.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    return rows


def default_jobs() -> int:
    # 한 경기에 봇 프로세스 둘이 동시에 계산하므로 코어의 절반. 넘치면 가짜 시간 초과가 난다
    return max(1, (os.cpu_count() or 2) // 2)


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def summarize(rows: list[dict], a_name: str, b_name: str) -> str:
    n = len(rows)
    c = Counter(r["outcome"] for r in rows)
    rate = (c["win"] + 0.5 * c["draw"]) / n if n else 0.0
    lo, hi = wilson(rate, n)
    lines = [
        f"A = {a_name}",
        f"B = {b_name}",
        f"{n}경기 (시드 {n // 2}개 × 진영 교대)",
        (f"A 기준  승 {c['win']} · 무 {c['draw']} · 패 {c['loss']}   "
         f"승점률 {rate:.1%} (95% 구간 {lo:.0%}–{hi:.0%})"),
    ]
    for team in ("Y", "K"):
        sub = Counter(r["outcome"] for r in rows if r["a_team"] == team)
        lines.append(f"  A가 {team}일 때: {sub['win']}승 {sub['draw']}무 {sub['loss']}패")
    reasons = Counter(r["reason"] for r in rows)
    lines.append("결정 사유: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common()))

    def mean(key, side):
        return sum(r[key][side] for r in rows) / n if n else 0.0

    lines.append(f"평균 점령 점수 A {mean('score', 'A'):.1f} vs B {mean('score', 'B'):.1f}   "
                 f"평균 누적 점령-턴 A {mean('occupation', 'A'):.0f} vs B {mean('occupation', 'B'):.0f}")
    lines.append(f"평균 경기 길이 {sum(r['turn'] for r in rows) / n:.0f}턴" if n else "")
    for side in ("A", "B"):
        forfeits = [r for r in rows if side in r["forfeit"]]
        worst = max((r["max_ms"][side] for r in rows), default=0.0)
        first = max((r["first_ms"][side] for r in rows), default=0.0)
        ignored = sum(r.get("ignored", {}).get(side, 0) for r in rows)
        text = (f"{side}: 몰수 {len(forfeits)}회 · 최대 응답 {worst:.0f} ms (첫 턴 최대 {first:.0f} ms)"
                + (f" · 무시된 명령 {ignored}줄" if "ignored" in rows[0] else ""))
        lines.append(text)
        for r in forfeits[:3]:
            team = r["a_team"] if side == "A" else ("K" if r["a_team"] == "Y" else "Y")
            lines.append(f"    시드 {r['seed']} ({side}={team}): {r['forfeit'][side]}")
    return "\n".join(lines)
