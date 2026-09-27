"""맵: 규칙서 1장 조건을 만족하는 무작위 맵 생성과, 서버가 보낸 INIT 블록 읽기.

서버의 실제 맵 생성기는 공개되지 않았다. 여기서는 규칙서에 적힌 조건만 지킨다.

- 15×15, (7,7) 기준 180° 점대칭. 중앙광장은 (7,7), 항상 3점
- 신촌(Y) 쪽 5개(학생회관·도서관·공학관·병원·역)와 안암(K) 쪽 대칭 짝, 점수 1~2
- 중앙 6개(역·방송국·보급소 각 2개, 대칭 짝), 점수 2~4, y 2~12
- 장애물 10쌍(20칸), 모든 건물과 본진이 서로 도달 가능
- 본진 사이 맨해튼 거리 12 이상

BALANCE의 regions(신촌 0~4, 중앙 5~9, 안암 10~14)는 x축 기준으로 해석했다. 스타터 킷
search.directions()가 본진의 x좌표로 진영 방향을 정하고, 중앙 건물 제한이 y축에 걸려 있어서다.
건물을 어디에 얼마나 몰아 두는지 같은 세부 분포는 서버와 다를 수 있다.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

from sim import rules

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
    """시드로 맵 하나를 만든다. 같은 시드는 항상 같은 맵."""
    rng = random.Random(seed)
    for _ in range(rules.MAX_PLACE_ATTEMPTS):
        spec = _try_generate(rng, seed)
        if spec is not None:
            return spec
    raise RuntimeError(f"맵 생성 실패 (seed={seed})")


def _try_generate(rng: random.Random, seed: int) -> MapSpec | None:
    size = rules.SIZE
    lo, hi = rules.REGIONS["sinchon"]
    bases = [
        (x, y) for x in range(lo, hi + 1) for y in range(size)
        if _manhattan((x, y), mirror((x, y))) >= rules.MIN_BASE_DISTANCE
    ]
    base_y = rng.choice(bases)
    taken = {base_y, mirror(base_y), rules.CENTER}

    placed: list[tuple[Pos, str, int]] = [(rules.CENTER, "PLAZA", rules.PLAZA_SCORE)]

    def place(cells: list[Pos], kind: str, score: int) -> bool:
        free = [c for c in cells if c not in taken and mirror(c) not in taken and c != mirror(c)]
        if not free:
            return False
        cell = rng.choice(free)
        taken.update((cell, mirror(cell)))
        placed.extend(((cell, kind, score), (mirror(cell), kind, score)))
        return True

    side = [(x, y) for x in range(lo, hi + 1) for y in range(size)]
    for kind in rules.SIDE_KINDS:
        if not place(side, kind, rng.randint(*rules.SIDE_SCORE)):
            return None
    clo, chi = rules.REGIONS["center"]
    margin = rules.CENTRAL_Y_MARGIN
    center = [(x, y) for x in range(clo, chi + 1) for y in range(margin, size - margin)]
    for kind in rules.CENTER_KINDS:
        if not place(center, kind, rng.randint(*rules.CENTER_SCORE)):
            return None

    # 장애물은 연결성을 깨면 그 쌍만 다시 뽑는다
    obstacles: set[Pos] = set()
    must_reach = [pos for pos, _, _ in placed] + [base_y, mirror(base_y)]
    free = [(x, y) for y in range(size) for x in range(size)]
    tries = 0
    while len(obstacles) < 2 * rules.OBSTACLE_PAIRS:
        tries += 1
        if tries > 200:
            return None
        cell = rng.choice(free)
        if cell in taken or cell in obstacles or cell == mirror(cell):
            continue
        trial = obstacles | {cell, mirror(cell)}
        if _connected(must_reach, trial):
            obstacles = trial

    grid = [["."] * size for _ in range(size)]
    for x, y in obstacles:
        grid[y][x] = "#"
    for (x, y), _, _ in placed:
        grid[y][x] = "B"
    for x, y in (base_y, mirror(base_y)):
        grid[y][x] = "H"

    # id는 (y, x) 순서로 매긴다. 진영에 따라 id가 쏠리지 않게 하려는 것일 뿐 서버 방식은 모른다
    ordered = sorted(placed, key=lambda p: (p[0][1], p[0][0]))
    buildings = tuple(BuildingSpec(i, pos, kind, score) for i, (pos, kind, score) in enumerate(ordered))
    return MapSpec(
        rows=tuple("".join(row) for row in grid),
        buildings=buildings,
        bases={"Y": base_y, "K": mirror(base_y)},
        seed=seed,
    )


def _manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _connected(cells: list[Pos], obstacles: set[Pos]) -> bool:
    start = cells[0]
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in rules.DIRS.values():
            nxt = (x + dx, y + dy)
            if (0 <= nxt[0] < rules.SIZE and 0 <= nxt[1] < rules.SIZE
                    and nxt not in obstacles and nxt not in seen):
                seen.add(nxt)
                queue.append(nxt)
    return all(c in seen for c in cells)


def from_init(text: str, seed: int = 0) -> MapSpec:
    """서버에서 받은 INIT 블록으로 맵을 만든다. INIT에는 점수가 없으므로 규칙 범위에서 시드로 채운다.

    대칭 짝은 같은 점수, 중앙광장은 3점. 신촌·안암/중앙 구분은 x좌표(regions)로 한다.
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
    scores: dict[Pos, int] = {}
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
