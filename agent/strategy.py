"""World를 받아 다음 행동을 결정하는 에이전트 두뇌: decide(world) -> actions.

현재 내용은 스타터 킷 starter/example_lv2.py를 우리 구조로 옮긴 것이다. 같은 입력이면 같은
명령을 낸다(tests/test_parity.py). 전략 개선은 여기서부터 시작한다.
"""

from __future__ import annotations

from agent.algorithms import DEFAULT_ORDER, first_step
from agent.world import (
    CAPTURE_COST,
    ENG_COST_FLOOR,
    ENG_DISCOUNT,
    LIBRARY_DISCOUNT,
    MIN_CAPTURE_COST,
    PLAZA_CAPTURE_COST,
    UNIT_COST,
    Action,
    Move,
    Pos,
    Spawn,
    World,
)

MAX_WARRIORS = 3  # 예제의 전투병 상한


def decide(world: World) -> list[Action]:
    me, enemy = world.me, world.enemy
    actions: list[Action] = []
    flags = world.units_of(me, "F")
    warriors = world.units_of(me, "W")
    enemy_flags = {pos for pos, _ in world.units_of(enemy, "F")}
    targets = {b.pos for b in world.buildings.values() if b.owner != me}
    live = targets - enemy_flags

    # 점령 비용을 먼저 남기고 남은 자원으로 생산한다.
    budget = max(0, world.gold[me] - capture_reserve(world))
    wc = max(ENG_COST_FLOOR, UNIT_COST["W"] - len(world.owned(me, "ENG")) * ENG_DISCOUNT)
    fc = UNIT_COST["F"]
    nf = sum(n for _, n in flags)
    nw = sum(n for _, n in warriors)
    make_w = min(max(0, MAX_WARRIORS - nw), budget // wc) if nf or budget >= fc + wc else 0
    budget -= make_w * wc
    if make_w:
        actions.append(Spawn("W", make_w))
    make_f = budget // fc
    if make_f:
        actions.append(Spawn("F", make_f))

    order = direction_order(world)
    passable = world.map.passable
    # 전투병은 상대 깃발병을 쫓고, 없으면 점령 목표로 간다.
    warrior_goals = enemy_flags or live
    for pos, n in warriors:
        step = first_step(pos, warrior_goals, passable, order)
        if step:
            actions.append(Move(pos, "W", n, step))
    # 깃발병은 상대 깃발병이 없는 미점령 건물로 간다.
    for pos, n in flags:
        step = first_step(pos, live, passable, order)
        if step:
            actions.append(Move(pos, "F", n, step))
    return actions


def capture_reserve(world: World) -> int:
    """이번 턴 점령에 남겨 둘 자원. 깃발병이 올라가 있는 건물 중 가장 비싼 한 단계 비용."""
    me = world.me
    has_library = bool(world.owned(me, "LIBRARY"))
    costs = [CAPTURE_COST]
    for pos, _ in world.units_of(me, "F"):
        b = world.building_at(pos)
        if b and b.owner != me:
            cost = PLAZA_CAPTURE_COST if b.kind == "PLAZA" else CAPTURE_COST
            costs.append(max(MIN_CAPTURE_COST, cost - (LIBRARY_DISCOUNT if has_library else 0)))
    return max(costs)


def direction_order(world: World) -> tuple[Pos, ...]:
    """거리가 같을 때의 방향 우선순위. 본진이 오른쪽 절반이면 뒤집어 자기 본진 기준으로 맞춘다."""
    base_x = world.map.bases[world.me][0]
    if base_x * 2 > world.map.width - 1:
        return tuple((-dx, -dy) for dx, dy in DEFAULT_ORDER)
    return DEFAULT_ORDER
