"""경로 탐색을 포함한 순수 알고리즘 함수 모음."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Collection, Sequence

Pos = tuple[int, int]

# 기본 탐색 방향 순서: U, D, L, R
DEFAULT_ORDER: tuple[Pos, ...] = ((0, -1), (0, 1), (-1, 0), (1, 0))


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


def distance_map(sources: Collection[Pos], passable: Callable[[Pos], bool]) -> dict[Pos, int]:
    """여러 출발 칸에서 각 칸까지의 최단 거리(4방향). 닿을 수 없는 칸은 키가 없다."""
    dist = {pos: 0 for pos in sources}
    queue = deque(dist)
    while queue:
        x, y = queue.popleft()
        d = dist[(x, y)] + 1
        for dx, dy in DEFAULT_ORDER:
            pos = (x + dx, y + dy)
            if pos not in dist and passable(pos):
                dist[pos] = d
                queue.append(pos)
    return dist


def step_along(start: Pos, dist: dict[Pos, int], order: Sequence[Pos] = DEFAULT_ORDER) -> Pos | None:
    """거리표 `dist`(목표에서 잰 거리)를 한 칸 줄이는 이웃 칸. 거리가 같으면 `order` 순서.

    이미 목표(거리 0) 위에 있거나 닿을 수 없으면 None.
    """
    here = dist.get(start)
    if not here:
        return None
    x, y = start
    for dx, dy in order:
        pos = (x + dx, y + dy)
        if dist.get(pos) == here - 1:
            return pos
    return None
