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
