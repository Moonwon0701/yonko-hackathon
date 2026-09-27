"""맵: 규칙서 1장 조건을 만족하는 무작위 맵 생성, 서버가 보낸 INIT 블록 읽기, 서버 리플레이에서 맵 뽑기.

시드 맵은 운영진 공식 mapgen(devtool/, sim/official.py)으로 만든다. 같은 시드는 서버와 같은 맵이고,
서버 모의 전투 맵은 공개 시드 0~9 그대로다(tests/test_official.py가 서버 리플레이로 확인).
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from sim import official, rules

PUBLIC_SEEDS = range(10)  # 서버 모의 전투 맵 (devtool/docs/PLATFORM_OPERATIONS.md)

Pos = tuple[int, int]


@dataclass(frozen=True)
class BuildingSpec:
    id: int
    pos: Pos
    kind: str
    score: int  # 실제 점수. 봇에게는 공개 전까지 -1로 보인다


@dataclass(frozen=True)
class MapSpec:
    rows: tuple[str, ...]  # rows[y][x]: "." 평지, "#" 장애물, "B" 건물, "H" 본진
    buildings: tuple[BuildingSpec, ...]
    bases: dict[str, Pos]
    seed: int | None = None

    @property
    def size(self) -> int:
        return len(self.rows)

    def passable(self, pos: Pos) -> bool:
        x, y = pos
        return 0 <= x < self.size and 0 <= y < self.size and self.rows[y][x] != "#"

    @property
    def total_score(self) -> int:
        return sum(b.score for b in self.buildings)


def mirror(pos: Pos) -> Pos:
    return (rules.SIZE - 1 - pos[0], rules.SIZE - 1 - pos[1])


def generate(seed: int) -> MapSpec:
    """시드로 맵 하나를 만든다. 운영진 공식 mapgen을 쓰므로 같은 시드는 서버와 같은 맵이다.

    서버 모의 전투는 공개 시드 0~9를 쓴다(PUBLIC_SEEDS).
    """
    g = official.generate(seed)
    return MapSpec(
        rows=tuple("".join(row) for row in g.terrain),
        buildings=tuple(BuildingSpec(b.id, (b.x, b.y), b.btype, b.score) for b in g.buildings),
        bases={t: tuple(g.bases[t]) for t in rules.TEAMS},
        seed=seed,
    )


@cache
def _public_scores() -> dict[tuple[str, ...], dict[Pos, int]]:
    """공개 시드 맵의 지형 → {건물 칸: 실제 점수}."""
    out = {}
    for seed in PUBLIC_SEEDS:
        m = generate(seed)
        out[m.rows] = {b.pos: b.score for b in m.buildings}
    return out


def public_scores(rows) -> dict[Pos, int] | None:
    """지형이 공개 시드 맵 중 하나와 같으면 그 맵의 실제 점수, 아니면 None."""
    return _public_scores().get(tuple(rows))



def from_init(text: str, seed: int = 0) -> MapSpec:
    """서버에서 받은 INIT 블록으로 맵을 만든다.

    INIT에는 점수가 없다. 지형이 공개 시드 맵이면 그 실제 점수를 쓰고, 아니면 규칙 범위에서 시드로
    채운다(대칭 짝은 같은 점수, 중앙광장은 3점, 신촌·안암/중앙 구분은 x좌표).
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    size = int(lines[0].split()[2])
    rows = tuple(lines[2 + y].split()[1] for y in range(size))
    idx = 2 + size
    n = int(lines[idx].split()[1])
    raw = []
    for line in lines[idx + 1: idx + 1 + n]:
        bid, x, y, kind = line.split()
        raw.append((int(bid), (int(x), int(y)), kind))
    bases = {}
    for line in lines[idx + 1 + n: idx + 3 + n]:
        _, team, x, y = line.split()
        bases[team] = (int(x), int(y))

    rng = random.Random(seed)
    scores: dict[Pos, int] = dict(public_scores(rows) or {})
    clo, chi = rules.REGIONS["center"]
    for _, pos, kind in sorted(raw):
        if pos in scores:
            continue
        if kind == "PLAZA":
            score = rules.PLAZA_SCORE
        elif clo <= pos[0] <= chi:
            score = rng.randint(*rules.CENTER_SCORE)
        else:
            score = rng.randint(*rules.SIDE_SCORE)
        scores[pos] = scores[mirror(pos)] = score
    buildings = tuple(BuildingSpec(bid, pos, kind, scores[pos]) for bid, pos, kind in raw)
    return MapSpec(rows=rows, buildings=buildings, bases=bases, seed=None)


# ------------------------------------------------------------------ 서버 리플레이


def from_server_replay(path: str | Path, seed: int = 0) -> MapSpec:
    """대회 페이지에서 받은 리플레이 JSON 하나로 서버의 실제 맵을 만든다."""
    return _server_map([json.loads(Path(path).read_text(encoding="utf-8"))], seed)


def load_server_maps(folder: str | Path, seed: int = 0) -> list[tuple[str, MapSpec]]:
    """폴더(하위 폴더 포함)의 서버 리플레이를 지형이 같은 것끼리 한 맵으로 묶는다. 돌려주는 값: (이름, 맵).

    모의 전투는 상대 봇이 달라도 같은 맵을 다시 쓰므로, 같은 지형의 리플레이에서 공개된 점수를 합친다.
    내용이 똑같은 파일(같은 경기를 두 번 받은 것)은 한 번만 센다. 이름은 그 맵의 첫 파일 경로.
    """
    groups: dict[str, list[dict]] = {}
    names: dict[str, str] = {}
    seen: set[str] = set()
    for path in sorted(Path(folder).rglob("*.json")):
        raw = path.read_bytes()
        digest = hashlib.md5(raw).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        replay = json.loads(raw)
        terrain = "".join(replay["turns"][0]["observation"]["map"])
        groups.setdefault(terrain, []).append(replay)
        names.setdefault(terrain, path.relative_to(folder).as_posix())
    return [(names[t], _server_map(replays, seed)) for t, replays in groups.items()]


def _server_map(replays: list[dict], seed: int) -> MapSpec:
    """같은 지형의 서버 리플레이들 → MapSpec.

    - 지형·건물: 첫 턴 관측(`observation.map`, `observation.buildings`)
    - 점수: 공개 시드 맵이면 그 실제 점수, 거기에 리플레이마다 공개된 실제 점수(`revealed.buildingScores`)를
      모두 합친다. 모르는 건물은 대칭 짝 점수,
      그래도 모르면 규칙 범위에서 시드로 (방송국·보급소는 중앙 범위, 나머지는 진영 범위)
    - 본진: `H` 두 칸 중 리플레이 주인(`side`)의 유닛이 처음 나타난 칸에 가까운 쪽이 그 진영
    """
    first = replays[0]
    obs = first["turns"][0]["observation"]
    rows = tuple(obs["map"])
    raw = [(b["id"], (b["x"], b["y"]), b["type"]) for b in obs["buildings"]]

    public = public_scores(rows) or {}
    known: dict[int, int] = {bid: public[pos] for bid, pos, _ in raw if pos in public}
    for replay in replays:
        for turn in replay["turns"]:
            known.update({int(k): v for k, v in turn["revealed"]["buildingScores"].items()})
    pos_of = {bid: pos for bid, pos, _ in raw}
    by_pos = {pos: bid for bid, pos, _ in raw}
    rng = random.Random(seed)
    scores: dict[int, int] = {}
    for bid, pos, kind in sorted(raw):
        twin = by_pos.get(mirror(pos))
        if bid in known:
            scores[bid] = known[bid]
        elif twin in known:
            scores[bid] = known[twin]
        elif twin in scores:
            scores[bid] = scores[twin]
        elif kind == "PLAZA":
            scores[bid] = rules.PLAZA_SCORE
        elif kind in ("WATCH", "DEPOT"):
            scores[bid] = rng.randint(*rules.CENTER_SCORE)
        else:
            scores[bid] = rng.randint(*rules.SIDE_SCORE)

    homes = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == "H"]
    side = first["side"]
    other = "K" if side == "Y" else "Y"
    start = next(u for t in first["turns"] for u in t["observation"]["units"] if u[0] == side)
    mine = min(homes, key=lambda h: abs(h[0] - start[2]) + abs(h[1] - start[3]))
    bases = {side: mine, other: next(h for h in homes if h != mine)}
    buildings = tuple(BuildingSpec(bid, pos_of[bid], kind, scores[bid]) for bid, _, kind in raw)
    return MapSpec(rows=rows, buildings=buildings, bases=bases, seed=None)
