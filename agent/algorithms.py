"""경로 탐색을 포함한 순수 알고리즘 함수 모음."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Collection, Sequence

Pos = tuple[int, int]

# 기본 탐색 방향 순서: U, D, L, R
DEFAULT_ORDER: tuple[Pos, ...] = ((0, -1), (0, 1), (-1, 0), (1, 0))


def manhattan(a: Pos, b: Pos) -> int:
    """두 칸 사이의 상하좌우 거리(장애물 무시)."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def first_step(
    start: Pos,
    targets: Collection[Pos],
    passable: Callable[[Pos], bool],
    order: Sequence[Pos] = DEFAULT_ORDER,
) -> Pos | None:
    """가장 가까운 목표로 가는 최단 경로의 첫 칸.

    BFS라 가까운 칸부터 방문한다. 거리가 같으면 `order`에 먼저 있는 방향을 고른다.
    이미 목표 위에 있거나 닿을 수 없으면 None.
    """
    if start in targets:
        return None
    queue = deque([(start, None)])
    seen = {start}
    while queue:
        (x, y), first = queue.popleft()
        for dx, dy in order:
            pos = (x + dx, y + dy)
            if pos in seen or not passable(pos):
                continue
            step = first or pos
            if pos in targets:
                return step
            seen.add(pos)
            queue.append((pos, step))
    return None


def distance_map(
    sources: Collection[Pos], passable: Callable[[Pos], bool], portals: Sequence[Pos] = (),
) -> dict[Pos, int]:
    """여러 출발 칸에서 각 칸까지의 최단 거리(4방향). 닿을 수 없는 칸은 키가 없다.

    `portals`(우리 역)는 서로 비용 1로 이어진다 — 순간이동도 한 턴을 쓰기 때문이다(도착한 유닛은 그 턴에 더 못
    움직인다). 비어 있으면 걸어서만의 거리.
    """
    gates = set(portals)
    dist = {pos: 0 for pos in sources}
    queue = deque(dist)
    while queue:
        x, y = queue.popleft()
        d = dist[(x, y)] + 1
        nexts = [(x + dx, y + dy) for dx, dy in DEFAULT_ORDER]
        if (x, y) in gates:
            nexts += portals
        for pos in nexts:
            if pos not in dist and passable(pos):
                dist[pos] = d
                queue.append(pos)
    return dist


def threat_map(stacks: Collection[tuple[Pos, int]], passable: Callable[[Pos], bool]) -> dict[Pos, int]:
    """다음 턴 각 칸에 모일 수 있는 최대 인원. 각 무리는 제자리 또는 상하좌우 한 칸으로 갈 수 있다.

    무리를 나눠 여러 칸으로 보낼 수도 있으므로, 칸마다 닿을 수 있는 무리의 인원을 모두 더한다(최악의 경우).
    """
    threat: dict[Pos, int] = {}
    for (x, y), n in stacks:
        for dx, dy in ((0, 0), *DEFAULT_ORDER):
            pos = (x + dx, y + dy)
            if passable(pos):
                threat[pos] = threat.get(pos, 0) + n
    return threat


def step_along(
    start: Pos, dist: dict[Pos, int], order: Sequence[Pos] = DEFAULT_ORDER, portals: Sequence[Pos] = (),
) -> Pos | None:
    """거리표 `dist`(목표에서 잰 거리)를 한 칸 줄이는 칸. 거리가 같으면 `order` 순서.

    상하좌우 이웃을 먼저 보고, 없으면 `start`가 역일 때 다른 역(`portals` 순서)을 본다 — 붙어 있지 않은 칸을
    돌려주면 순간이동이라는 뜻이다. 이미 목표(거리 0) 위에 있거나 닿을 수 없으면 None.
    """
    here = dist.get(start)
    if not here:
        return None
    x, y = start
    for dx, dy in order:
        pos = (x + dx, y + dy)
        if dist.get(pos) == here - 1:
            return pos
    if start in portals:
        for pos in portals:
            if pos != start and dist.get(pos) == here - 1:
                return pos
    return None
