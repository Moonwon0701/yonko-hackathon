"""서버 리플레이의 매 턴 입력을 우리 봇에 그대로 다시 넣어, 봇이 그 턴에 무엇을 판단했는지 본다 (진 경기 분석용).

사용법 (저장소 최상위에서):
    python scripts/rerun_replay.py data/server-replays/<회차>/vs_치명ㄷ_패.json --bot git:337ab49
    python scripts/rerun_replay.py <리플레이> --bot git:337ab49 --at 4,9 --turns 20-32
    python scripts/rerun_replay.py data/server-replays/<회차>/*.json --bot git:337ab49 --bank

리플레이 JSON(사이트 API로 받은 것)의 직전 턴 관측으로 TURN 블록을 만들어 `adapter.parse_turn` → `strategy.decide`에
넣고, 나온 명령을 그 턴에 실제로 낸 명령과 비교한다. 그 경기를 둔 커밋을 `--bot`으로 주면 매 턴 명령이 같아야 한다
(10/1 00:30 회차 12판을 `337ab49`로 돌려 전부 같았다). 처음 달라진 턴부터는 "이 봇이라면 그 상태에서 무엇을
했을까"를 보는 것이다(이후 상태는 실제로 둔 봇의 수로 만들어졌다).

- 기본 출력: 판마다 턴 수와 명령이 달라진 턴 수, 처음 달라진 턴
- `--at X,Y --turns A-B`: 그 칸 `--radius`걸음 안의 양쪽 유닛, 그 근처 전투병 과제(종류·칸·필요 인원·가치 → 배정 인원),
  근처 전투병이 간 목표, 그 턴 생산 명령
- `--bank`: `ENG_BANK`로 전투병 생산을 미룬 턴마다, 목표 공학관 위 적 전투병 수와 3턴 안에 실제로 먹었는지

리플레이의 `side`는 늘 우리 시점이다(우리가 K 칸으로 둔 경기도 Y로 저장). 전략 모듈의 전역 상태를 판마다 새로
시작하도록 판마다 `agent`를 다시 불러온다.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim.bots import resolve


def load_agent(bot_dir: str):
    """`bot_dir`의 agent 패키지를 새로 불러온다 (전역 상태 초기화)."""
    for name in [m for m in sys.modules if m == "agent" or m.startswith("agent.")]:
        del sys.modules[name]
    if sys.path[0] != bot_dir:
        sys.path.insert(0, bot_dir)
    return importlib.import_module("agent.adapter"), importlib.import_module("agent.strategy")


def init_lines(replay: dict) -> list[str]:
    """INIT 블록. 본진은 맵의 `H` 두 칸 중 1턴 뒤 우리 유닛에 가까운 쪽이 우리 것."""
    me = replay["side"]
    turns = {t["turn"]: t for t in replay["turns"]}
    obs0 = turns[0]["observation"]
    rows = obs0["map"]
    homes = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == "H"]
    ours = [(x, y) for team, _, x, y, _ in turns[1]["observation"]["units"] if team == me]
    mine = min(homes, key=lambda h: min((abs(h[0] - x) + abs(h[1] - y) for x, y in ours), default=99))
    theirs = next(h for h in homes if h != mine)
    enemy = "K" if me == "Y" else "Y"
    return (["INIT 15 15", f"TEAM {me}"] + ["MAP " + row for row in rows]
            + [f"BUILDINGS {len(obs0['buildings'])}"]
            + [f'{b["id"]} {b["x"]} {b["y"]} {b["type"]}' for b in obs0["buildings"]]
            + [f"BASE {me} {mine[0]} {mine[1]}", f"BASE {enemy} {theirs[0]} {theirs[1]}"])


def turn_lines(turn: int, obs: dict, me: str, scores: dict[str, int]) -> list[str]:
    """직전 턴 관측 → TURN 블록 (정렬은 서버 규격: 팀 우리→상대, 병종 F→W→S, y, x)."""
    enemy = "K" if me == "Y" else "Y"
    units = sorted(obs["units"], key=lambda u: (u[0] != me, "FWS".index(u[1]), u[3], u[2]))
    return ([f"TURN {turn}", f'RESOURCE {obs["resources"][me]} {obs["resources"][enemy]}', f"UNITS {len(units)}"]
            + [f"{team} {kind} {x} {y} {n}" for team, kind, x, y, n in units]
            + [f"BUILDINGS {len(obs['buildings'])}"]
            + [f'{b["id"]} {b["x"]} {b["y"]} {b["type"]} {b["owner"]} {b["stage"]} {scores.get(str(b["id"]), -1)}'
               for b in obs["buildings"]])


def rerun(path: Path, bot_dir: str, at: tuple[int, int] | None, span: tuple[int, int], radius: int,
          bank: bool) -> None:
    adapter, strategy = load_agent(bot_dir)
    replay = json.loads(path.read_text(encoding="utf-8"))
    me = replay["side"]
    enemy = "K" if me == "Y" else "Y"
    turns = {t["turn"]: t for t in replay["turns"]}
    game_map, _ = adapter.parse_init(init_lines(replay))

    seen: dict = {}  # 이번 턴 훅이 본 것
    if hasattr(strategy, "assign_warriors"):
        assign = strategy.assign_warriors

        def assign_hook(warriors, tasks, dist_to, *rest):
            result = assign(warriors, tasks, dist_to, *rest)
            seen["w"] = (list(tasks), result)
            return result
        strategy.assign_warriors = assign_hook
    if bank and hasattr(strategy, "eng_coming"):
        coming = strategy.eng_coming

        def coming_hook(t):
            result = coming(t)
            if result:
                seen["bank"] = [task.pos for _, task in t.flag_plan1
                                if task.building is not None and task.building.kind == "ENG"]
            return result
        strategy.eng_coming = coming_hook

    scores: dict[str, int] = {}
    differ: list[int] = []
    bank_rows = []
    last = max(t for t, e in turns.items() if "command" in e)
    for turn in range(1, last + 1):
        prev = turns[turn - 1]
        obs = prev["observation"]
        scores.update(prev["revealed"]["buildingScores"])
        world = adapter.parse_turn(turn_lines(turn, obs, me, scores), game_map, me)
        seen.clear()
        got = [adapter.to_line(a) for a in strategy.decide(world)]
        if got != turns[turn]["command"]["lines"]:
            differ.append(turn)
        if at and span[0] <= turn <= span[1]:
            show_turn(turn, obs, me, enemy, at, radius, seen.get("w"), got)
        if "bank" in seen:
            target = seen["bank"][0] if seen["bank"] else None
            on_target = sum(n for team, kind, x, y, n in obs["units"]
                            if team == enemy and kind == "W" and (x, y) == target)
            took = next((dt for dt in range(4) if turn + dt in turns and any(
                (b["x"], b["y"]) == target and b["owner"] == me
                for b in turns[turn + dt]["observation"]["buildings"])), None)
            bank_rows.append((turn, target, obs["resources"][me], on_target, took))

    first = f", 처음 {differ[0]}턴" if differ else ""
    print(f"{path.name}: {last}턴, 명령 다른 턴 {len(differ)}{first}")
    if bank:
        blocked = [r for r in bank_rows if r[3] > 0]
        print(f"  적립 {len(bank_rows)}턴 (3턴 안에 먹음 {sum(r[4] is not None for r in bank_rows)}), "
              f"그중 공학관 위 적 전투병 {len(blocked)}턴 (먹음 {sum(r[4] is not None for r in blocked)})")
        for turn, target, gold, on_target, took in blocked:
            print(f"    {turn}턴 목표 {target} 자원 {gold} 적 {on_target}명 → "
                  + (f"{took}턴 뒤 먹음" if took is not None else "못 먹음"))


def show_turn(turn: int, obs: dict, me: str, enemy: str, at: tuple[int, int], radius: int,
              assigned, got: list[str]) -> None:
    def near(pos) -> bool:
        return abs(pos[0] - at[0]) + abs(pos[1] - at[1]) <= radius

    def cells(team, kind):
        return [(x, y, n) for t, k, x, y, n in obs["units"] if t == team and k == kind and near((x, y))]

    def total(team):
        return sum(n for t, k, *_, n in obs["units"] if t == team and k == "W")

    owner = next((b["owner"] for b in obs["buildings"] if (b["x"], b["y"]) == at), "-")
    print(f"{turn}턴 {at} 소유 {owner} · 전투병 {total(me)}:{total(enemy)} · 자원 {obs['resources'][me]}")
    print(f"  우리 W {cells(me, 'W')} F {cells(me, 'F')} | 상대 W {cells(enemy, 'W')} F {cells(enemy, 'F')}")
    if assigned:
        tasks, (plan, _, _) = assigned
        dst = Counter(goal for _, goal in plan)
        print("  과제 " + ", ".join(f"{t.kind}{t.pos} 필요{t.need} 가치{t.value:.1f}→{dst.get(t.pos, 0)}"
                                    for t in tasks if near(t.pos)))
        print(f"  근처 전투병의 목표 {dict(Counter(goal for src, goal in plan if near(src)))}")
    print(f"  생산 {[line for line in got if line.startswith('SPAWN')]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("replays", nargs="+", type=Path, help="서버 리플레이 JSON")
    parser.add_argument("--bot", default=".", help="봇 (경로 또는 git:<커밋>, 기본 = 작업 트리)")
    parser.add_argument("--at", help="자세히 볼 칸 X,Y")
    parser.add_argument("--turns", default="1-160", help="--at으로 볼 턴 구간 A-B")
    parser.add_argument("--radius", type=int, default=3, help="--at 칸에서 몇 걸음 안을 볼지")
    parser.add_argument("--bank", action="store_true", help="ENG_BANK 적립 턴 요약")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    bot_dir = resolve(args.bot).cwd
    at = tuple(int(v) for v in args.at.split(",")) if args.at else None
    span = tuple(int(v) for v in args.turns.split("-"))
    for path in args.replays:
        rerun(path, bot_dir, at, span, args.radius, args.bank)


if __name__ == "__main__":
    main()
