"""리더보드 리플레이에서 상대 팀마다 행동 수치를 뽑는다 (흉내 봇 설계용).

사용법 (저장소 최상위에서):
    python scripts/profile_opponents.py                  # 리더보드 회차 전부, 상대마다 한 줄
    python scripts/profile_opponents.py --team AIKU      # 그 팀 경기만
    python scripts/profile_opponents.py --us            # 같은 경기의 우리 쪽 수치 (비교용)
    python scripts/profile_opponents.py --economy       # 20~80턴 전투병 생산량과 공학관 쟁탈

리플레이에는 안개가 없어 상대 유닛·자원·건물 소유가 전부 있다. 뽑는 것:
- 병력: 턴별 깃발병·전투병 수, 정찰병 사용
- 경제: 남긴 자원 평균, 건물 수
- 전투병 배치: 전투병이 있는 칸 수와 칸당 인원(넓게 까는가), 우리 본진 쪽에 있는 비율(싸움을 어디서 하는가)
- 점령: 처음 먹은 건물 종류 순서, 광장을 처음 가진 턴, 우리 건물을 중립화한 횟수
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPLAYS = ROOT / "data" / "server-replays"
ROUNDS = ("2026-09-27_leaderboard", "2026-09-28_leaderboard_10", "2026-09-28_leaderboard_22")
CHECKPOINTS = (10, 20, 30, 50, 80)
SHORT = {"PLAZA": "광", "HALL": "학", "LIBRARY": "도", "ENG": "공", "HOSPITAL": "병",
         "STATION": "역", "WATCH": "방", "DEPOT": "보"}


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_games() -> list[dict]:
    """리더보드 회차의 경기 목록. 상대 이름·결과는 matches.csv에서."""
    games = []
    for name in ROUNDS:
        folder = REPLAYS / name
        with open(folder / "matches.csv", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                games.append({"round": name, "opponent": row["opponent"], "result": row["result"],
                              "reason": row["reason"], "path": folder / row["file"]})
    return games


def bases(turns: list[dict]) -> dict[str, tuple[int, int]]:
    """진영별 본진 = 지도의 H 중, 첫 유닛들에 더 가까운 것."""
    rows = turns[0]["observation"]["map"]
    hs = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == "H"]
    for t in turns:
        units = t["observation"]["units"]
        found = {}
        for team in ("Y", "K"):
            mine = [(u[2], u[3]) for u in units if u[0] == team]
            if mine:
                found[team] = min(hs, key=lambda h: sum(abs(h[0] - x) + abs(h[1] - y) for x, y in mine))
        if len(found) == 2 and found["Y"] != found["K"]:
            return found
    raise ValueError("본진을 찾지 못함")


def profile(path: Path, side: str | None = None) -> dict:
    """한 경기에서 `side`(기본: 상대) 팀의 수치."""
    r = load(path)
    turns = [t for t in r["turns"] if t["observation"].get("units") is not None]
    me = side or ("K" if r["side"] == "Y" else "Y")
    other = "Y" if me == "K" else "K"
    home = bases(turns)
    out: dict = {"turns": turns[-1]["observation"]["turn"]}
    kinds = {b["id"]: b["type"] for b in turns[0]["observation"]["buildings"]}

    def count(obs: dict, team: str, kind: str) -> int:
        return sum(u[4] for u in obs["units"] if u[0] == team and u[1] == kind)

    by_turn = {t["observation"]["turn"]: t["observation"] for t in turns}
    for c in CHECKPOINTS:
        obs = by_turn.get(c)
        if obs is None:
            continue
        out[f"F{c}"] = count(obs, me, "F")
        out[f"W{c}"] = count(obs, me, "W")
        out[f"oW{c}"] = count(obs, other, "W")
        out[f"B{c}"] = sum(1 for b in obs["buildings"] if b["owner"] == me)
        out[f"oB{c}"] = sum(1 for b in obs["buildings"] if b["owner"] == other)
    early = [o for tt, o in by_turn.items() if 2 <= tt <= 80]
    out["gold"] = st.mean(o["resources"][me] for o in early) if early else 0
    out["scouts"] = max((count(o, me, "S") for o in by_turn.values()), default=0)
    # 전투병 배치 (20~60턴): 칸 수, 칸당 인원, 상대 본진 쪽(맨해튼 거리로 상대 본진이 더 가까운 칸) 비율
    cells, per_cell, forward, total = [], [], 0, 0
    for tt, o in by_turn.items():
        if not 20 <= tt <= 60:
            continue
        ws = [(u[2], u[3], u[4]) for u in o["units"] if u[0] == me and u[1] == "W"]
        if ws:
            cells.append(len(ws))
            per_cell.append(sum(n for *_, n in ws) / len(ws))
        for x, y, n in ws:
            d_mine = abs(x - home[me][0]) + abs(y - home[me][1])
            d_theirs = abs(x - home[other][0]) + abs(y - home[other][1])
            forward += n if d_theirs < d_mine else 0
            total += n
    out["wcells"] = st.mean(cells) if cells else 0
    out["wpercell"] = st.mean(per_cell) if per_cell else 0
    out["wforward"] = forward / total if total else 0
    # 점령 순서, 광장, 중립화
    first: list[str] = []
    seen: set[int] = set()
    out["plaza"] = None
    neutralized = Counter()
    for tt, o in sorted(by_turn.items()):
        for e in o.get("events") or []:
            if e.get("team") != me:
                continue
            if e["kind"] == "capture" and e["buildingId"] not in seen:
                seen.add(e["buildingId"])
                first.append(SHORT.get(kinds[e["buildingId"]], "?"))
                if kinds[e["buildingId"]] == "PLAZA" and out["plaza"] is None:
                    out["plaza"] = tt
            if e["kind"] == "neutral" and tt <= 50:
                neutralized[SHORT.get(kinds[e["buildingId"]], "?")] += 1
    out["order"] = "".join(first[:10])
    out["neutral50"] = sum(neutralized.values())
    out["neutral_kinds"] = "".join(f"{k}{n}" for k, n in neutralized.most_common())
    return out


def economy(path: Path, start: int = 20, end: int = 80) -> dict:
    """생산량과 공학관. 전투는 같은 칸에서 양쪽 전투병을 같은 수만큼 없애고, 우리 전투병은 상대와의 전투에서만
    죽는다. 그래서 우리 `SPAWN W` 명령 합 − 우리 전투병 증감 = 우리 사망 = 상대 사망이고,
    상대 생산 = 상대 증감 + 우리 사망이다. (자원이 모자라 요청보다 덜 만든 턴이 있으면 우리 생산을 조금 크게 센다)

    공학관: 우리 쪽 공학관 = 첫 턴 우리 유닛들에 더 가까운 것. 전투병 값 3 = 공학관이 하나도 없는 턴.
    """
    r = load(path)
    me = r["side"]
    op = "K" if me == "Y" else "Y"
    turns = {t["observation"]["turn"]: t for t in r["turns"] if t["observation"].get("units") is not None}
    obs = {tt: t["observation"] for tt, t in turns.items()}
    last = max(obs)

    def warriors(tt: int, team: str) -> int:
        return sum(u[4] for u in obs[tt]["units"] if u[0] == team and u[1] == "W")

    out: dict = {}
    if last >= end:
        spawned = 0
        for tt in range(start + 1, end + 1):
            command = turns[tt].get("command") or {}
            if isinstance(command, str):
                command = ast.literal_eval(command)
            for line in command.get("lines", []):
                m = re.match(r"SPAWN W (\d+)", line)
                spawned += int(m[1]) if m else 0
        deaths = spawned - (warriors(end, me) - warriors(start, me))
        out["prodW"] = spawned
        out["oprodW"] = warriors(end, op) - warriors(start, op) + deaths
    first = next(o for _, o in sorted(obs.items()) if any(u[0] == me for u in o["units"]))
    mine = [(u[2], u[3]) for u in first["units"] if u[0] == me]
    engs = [b for b in first["buildings"] if b["type"] == "ENG"]
    ours = min(engs, key=lambda b: sum(abs(b["x"] - x) + abs(b["y"] - y) for x, y in mine))["id"]
    theirs = next(b["id"] for b in engs if b["id"] != ours)
    span = [o for tt, o in sorted(obs.items()) if 1 <= tt <= end]
    lost = took = None
    cost3 = {me: 0, op: 0}
    for o in span:
        owner = {b["id"]: b["owner"] for b in o["buildings"]}
        for team in (me, op):
            cost3[team] += owner[ours] != team and owner[theirs] != team
        if lost is None and owner[ours] == op:
            lost = o["turn"]
        if took is None and owner[theirs] == me:
            took = o["turn"]
    out["cost3"] = cost3[me] / len(span)
    out["ocost3"] = cost3[op] / len(span)
    out["eng_lost"] = lost
    out["eng_took"] = took
    return out


def fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", help="이 팀 경기만 자세히")
    ap.add_argument("--us", action="store_true", help="상대 대신 우리 쪽 수치")
    ap.add_argument("--economy", action="store_true", help="20~80턴 전투병 생산량(우리:상대)과 공학관 쟁탈")
    args = ap.parse_args()
    if args.economy:
        cols = ["prodW", "oprodW", "cost3", "ocost3", "eng_lost", "eng_took"]
        print("\t".join(["회차", "상대", "결과", "턴"] + cols))
        for g in load_games():
            if args.team and g["opponent"] != args.team:
                continue
            e = economy(g["path"])
            turns = profile(g["path"])["turns"]
            print("\t".join([g["round"][5:], g["opponent"][:10], g["result"], fmt(turns)] + [fmt(e.get(c)) for c in cols]))
        return
    cols = ["F10", "F20", "F30", "W10", "W20", "W30", "W50", "oW20", "oW30", "oW50", "B20", "oB20", "B30", "oB30",
            "gold", "scouts", "wcells", "wpercell", "wforward", "plaza", "neutral50", "order"]
    print("\t".join(["회차", "상대", "결과", "턴"] + cols))
    for g in load_games():
        if args.team and g["opponent"] != args.team:
            continue
        r = load(g["path"])
        p = profile(g["path"], r["side"] if args.us else None)
        print("\t".join([g["round"][5:], g["opponent"][:10], g["result"], fmt(p["turns"])]
                        + [fmt(p.get(c)) for c in cols]))


if __name__ == "__main__":
    main()
