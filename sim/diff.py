"""행동 비교: 봇 A가 봇 B와 매 턴 같은 명령을 내는지 확인한다.

구조만 바꾸고 행동은 그대로여야 하는 변경(리팩터링)을 검증하는 도구다. 상대 봇 C(기본 B)를 정하고, 시드마다
B 대 C(기준)와 A 대 C를 A가 Y·K일 때 한 번씩 둔다. A 쪽 명령을 기준 경기의 같은 진영 명령과 턴마다 비교해서,
처음 달라진 턴과 두 명령 목록을 알려 준다. 상대가 같으므로 A의 명령이 같으면 경기 전체가 똑같이 흘러간다.
상대를 바꿔 가며 돌리면 크게 이기는 판·지는 판처럼 다양한 국면에서 확인할 수 있다.

시간 제한은 끈다. 컴퓨터가 잠깐 느려져 생긴 시간 초과를 행동 차이로 잘못 보지 않기 위해서다.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed

from sim import mapgen, match
from sim.bots import BotSpec


def _commands(replay: dict, team: str) -> list[tuple[int, list[str]]]:
    return [(t["turn"], [c["line"] for c in t["commands"].get(team, [])]) for t in replay["turns"]]


def _play(spec, bots: dict[str, BotSpec]) -> dict:
    return match.play(spec, bots, time_scale=None, record=True)


def _check_seed(task: tuple) -> list[dict]:
    """시드 하나: A가 Y일 때와 K일 때, 기준 경기와 처음 달라진 곳 (같으면 turn=None)."""
    seed, a, b, c = task
    spec = mapgen.generate(seed)
    found = []
    for team in ("Y", "K"):
        other = "K" if team == "Y" else "Y"
        base = _play(spec, {team: b, other: c})
        test = _play(spec, {team: a, other: c})
        row = {"seed": seed, "a_team": team, "turn": None, "turns": len(test["turns"])}
        for (turn, got), (_, want) in zip(_commands(test, team), _commands(base, team)):
            if got != want:
                row.update(turn=turn, a=got, b=want)
                break
        else:
            if len(test["turns"]) != len(base["turns"]):
                row.update(turn=min(len(test["turns"]), len(base["turns"])) + 1, a=[], b=[])
        found.append(row)
    return found


def run(a: BotSpec, b: BotSpec, seeds: list[int], *, jobs: int, vs: BotSpec | None = None,
        progress=None) -> list[dict]:
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(_check_seed, (s, a, b, vs or b)) for s in seeds]
        for done, fut in enumerate(as_completed(futures), 1):
            rows += fut.result()
            if progress:
                progress(done, len(futures))
    rows.sort(key=lambda r: (r["seed"], r["a_team"]))
    return rows


def summarize(rows: list[dict], a_name: str, b_name: str, vs_name: str | None = None, show: int = 5) -> str:
    diff = [r for r in rows if r["turn"] is not None]
    turns = sum(r["turns"] for r in rows)
    lines = [
        f"A = {a_name}",
        f"B = {b_name}",
        f"상대 = {vs_name or b_name}",
        f"{len(rows)}경기 (A가 둔 {turns}턴): 명령이 모두 같은 경기 {len(rows) - len(diff)} · 달라진 경기 {len(diff)}",
    ]
    for r in diff[:show]:
        lines.append(f"  시드 {r['seed']} A={r['a_team']}  {r['turn']}턴에서 처음 달라짐")
        lines.append(f"    A: {r['a']}")
        lines.append(f"    B: {r['b']}")
    if len(diff) > show:
        lines.append(f"  … 외 {len(diff) - show}경기")
    return "\n".join(lines)
