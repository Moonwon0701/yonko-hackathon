"""World를 받아 다음 행동을 결정하는 에이전트 두뇌: decide(world) -> actions.

M1 — 건물 효용 점수 + 깃발병 목표 분산 (M0 기준선은 tests/lv2_port.py에 보관)

- 건물 효용 = (추정 점수 + 기능 가치) / (도착 거리 + 점령 단계 수 + ETA_OFFSET)
- 깃발병을 한 명씩, 효용이 가장 높은 (깃발병, 건물) 짝부터 배정한다. 한 건물에는 한 명만 간다.
  목표보다 깃발병이 많으면 남는 인원은 효용이 가장 높은 건물로 겹쳐 보낸다.
- 점령 비용은 이번 턴 수입까지 셈해 필요한 만큼만 남기고, 나머지로 생산한다.
- 이번 턴 점령할 건물이 둘 이상이면 효용 순으로 PRIORITY를 낸다.
- 전투병은 아직 lv2 방식(상대 깃발병 추격, 최대 3명)이다. M2에서 바꾼다.
"""

from __future__ import annotations

from collections import Counter

from agent.algorithms import DEFAULT_ORDER, distance_map, first_step, step_along
from agent.world import (
    BASE_INCOME,
    CAPTURE_COST,
    ENG_COST_FLOOR,
    ENG_DISCOUNT,
    HALL_BONUS,
    LIBRARY_DISCOUNT,
    MIN_CAPTURE_COST,
    PLAZA_CAPTURE_COST,
    TOTAL_TURNS,
    UNIT_COST,
    Action,
    Building,
    Move,
    Pos,
    Priority,
    Spawn,
    World,
)

MAX_WARRIORS = 3  # lv2와 같은 전투병 상한 (M2에서 바꾼다)
SPARE_FLAGS = 1  # 목표 건물 수보다 이만큼 더 많은 깃발병까지만 만든다

# 점수를 모를 때의 기대값. 규칙: 신촌·안암 건물 1~2점, 중앙 건물 2~4점
SIDE_SCORE_GUESS = 1.5
CENTER_SCORE_GUESS = 3.0
SIDE_KINDS = {"HALL", "LIBRARY", "ENG", "HOSPITAL"}  # 역은 위치로 가린다(campus_stations)
CENTER_KINDS = {"WATCH", "DEPOT"}

# 기능 가치 (점수 단위)
HALL_VALUE_PER_TURN = 0.02  # 학생회관: 남은 턴 × 이 값 (초반일수록 크다)
DEPOT_VALUE = 2.0  # 보급소: 최초 점령 +15 자원, 팀별 건물당 1회
FUNCTION_VALUE = {"LIBRARY": 0.5, "ENG": 0.5, "HOSPITAL": 0.5, "STATION": 0.3, "WATCH": 0.3}

ETA_OFFSET = 2  # 효용 분모에 더하는 값. 클수록 거리보다 건물 가치를 중시한다

_depots_taken: set[int] = set()  # 우리가 소유했던 보급소 id (보너스는 1회뿐). 한 프로세스 = 한 경기


def decide(world: World) -> list[Action]:
    me, enemy = world.me, world.enemy
    remember(world)
    actions: list[Action] = []
    order = direction_order(world)
    passable = world.map.passable

    enemy_flags = {pos for pos, _ in world.units_of(enemy, "F")}
    # 상대 깃발병이 있는 건물은 경합이라 점령이 안 된다 → 목표에서 뺀다 (깃발 뽑기는 M2)
    targets = sorted(
        (b for b in world.buildings.values() if b.owner != me and b.pos not in enemy_flags),
        key=lambda b: b.id,
    )
    dists = {b.id: distance_map([b.pos], passable) for b in targets}
    values = {b.id: building_value(world, b) for b in targets}

    # 1) 지금 있는 깃발병으로 이번 턴 점령할 건물을 정하고, 그 비용만 남긴다.
    flags = world.units_of(me, "F")
    plan = assign(flags, targets, dists, values)
    need = sum(stage_cost(world, b) for b in capturing(plan, dists))
    income = BASE_INCOME + HALL_BONUS * len(world.owned(me, "HALL"))
    budget = max(0, world.gold[me] - max(0, need - income))  # 점령은 이번 턴 수입 뒤에 치른다

    # 2) 생산: 전투병(상한까지) → 깃발병(목표 수만큼) → 남으면 전투병
    wc = max(ENG_COST_FLOOR, UNIT_COST["W"] - len(world.owned(me, "ENG")) * ENG_DISCOUNT)
    fc = UNIT_COST["F"]
    nf = sum(n for _, n in flags)
    nw = sum(n for _, n in world.units_of(me, "W"))
    make_w = min(max(0, MAX_WARRIORS - nw), budget // wc) if nf or budget >= fc + wc else 0
    budget -= make_w * wc
    want_f = max(0, len(targets) + SPARE_FLAGS - nf)
    make_f = min(budget // fc, want_f)
    budget -= make_f * fc
    if make_f == want_f:  # 깃발병이 충분하면 남는 자원은 쌓아 두지 않고 전투병으로
        make_w += budget // wc
    if make_w:
        actions.append(Spawn("W", make_w))
    if make_f:
        actions.append(Spawn("F", make_f))

    # 3) 새로 만든 깃발병까지 포함해 다시 배정하고 이동한다.
    if make_f:
        base = world.map.bases[me]
        merged = Counter(dict(flags))
        merged[base] += make_f
        flags = sorted(merged.items(), key=lambda item: (item[0][1], item[0][0]))
        plan = assign(flags, targets, dists, values)
    steps: Counter[tuple[Pos, Pos]] = Counter()
    for pos, b in plan:
        step = step_along(pos, dists[b.id], order)
        if step:
            steps[(pos, step)] += 1
    actions += [Move(src, "F", n, dst) for (src, dst), n in steps.items()]

    now = sorted(capturing(plan, dists), key=lambda b: -values[b.id])
    if len(now) >= 2:
        actions.append(Priority(tuple(b.pos for b in now)))

    # 4) 전투병: 상대 깃발병을 쫓고, 없으면 점령 목표로 (lv2와 같음)
    warrior_goals = enemy_flags or {b.pos for b in targets}
    for pos, n in world.units_of(me, "W"):
        step = first_step(pos, warrior_goals, passable, order)
        if step:
            actions.append(Move(pos, "W", n, step))
    return actions


def remember(world: World) -> None:
    """턴을 넘어 기억해야 하는 것: 보급소 보너스를 이미 받았는지."""
    if world.turn <= 1:
        _depots_taken.clear()
    _depots_taken.update(b.id for b in world.owned(world.me, "DEPOT"))


def assign(
    flags: list[tuple[Pos, int]],
    targets: list[Building],
    dists: dict[int, dict[Pos, int]],
    values: dict[int, float],
) -> list[tuple[Pos, Building]]:
    """깃발병 한 명씩 (칸, 목표 건물) 짝. 효용이 큰 짝부터 탐욕적으로 고르고, 한 건물엔 한 명.

    목표가 다 차면 남는 인원은 효용이 가장 높은 건물로 겹쳐 보낸다. 닿을 수 없으면 제자리.
    """
    pool = [pos for pos, n in flags for _ in range(n)]
    free = list(targets)
    plan: list[tuple[Pos, Building]] = []
    while pool:
        best: tuple[float, int, Building] | None = None
        for i, pos in enumerate(pool):
            for b in free or targets:
                d = dists[b.id].get(pos)
                if d is None:
                    continue
                u = values[b.id] / (d + stages(b) + ETA_OFFSET)
                if best is None or u > best[0]:
                    best = (u, i, b)
        if best is None:
            break
        _, i, b = best
        plan.append((pool.pop(i), b))
        if free:
            free.remove(b)
    return plan


def capturing(plan: list[tuple[Pos, Building]], dists: dict[int, dict[Pos, int]]) -> list[Building]:
    """이번 턴 이동 뒤 깃발병이 올라가 있을 건물 (= 이번 턴 점령 단계가 진행될 건물)."""
    found: dict[int, Building] = {}
    for pos, b in plan:
        if dists[b.id].get(pos, 99) <= 1:
            found[b.id] = b
    return list(found.values())


def stages(b: Building) -> int:
    """내 소유가 될 때까지 남은 점령 단계 수. 상대 건물은 중립화 → 점령 2단계."""
    return 1 if b.owner is None else 2


def stage_cost(world: World, b: Building) -> int:
    """이 건물의 점령 한 단계 비용 (도서관 할인 반영)."""
    cost = PLAZA_CAPTURE_COST if b.kind == "PLAZA" else CAPTURE_COST
    if world.owned(world.me, "LIBRARY"):
        cost = max(MIN_CAPTURE_COST, cost - LIBRARY_DISCOUNT)
    return cost


def building_value(world: World, b: Building) -> float:
    """건물 하나의 가치(점수 단위) = 추정 점수 + 기능 가치."""
    score = world.known_score(b)
    if score is None:
        score = CENTER_SCORE_GUESS if is_center(world, b) else SIDE_SCORE_GUESS
    if b.kind == "HALL":
        bonus = HALL_VALUE_PER_TURN * max(0, TOTAL_TURNS - world.turn)
    elif b.kind == "DEPOT":
        bonus = 0.0 if b.id in _depots_taken else DEPOT_VALUE
    else:
        bonus = FUNCTION_VALUE.get(b.kind, 0.0)
    return score + bonus


def is_center(world: World, b: Building) -> bool:
    """중앙 건물(서울역·방송국·보급소)인가. 역은 각 본진에서 가장 가까운 역이 캠퍼스 역이다."""
    if b.kind in CENTER_KINDS:
        return True
    if b.kind != "STATION":
        return b.kind not in SIDE_KINDS
    return b.id not in campus_stations(world)


def campus_stations(world: World) -> set[int]:
    stations = [b for b in world.buildings.values() if b.kind == "STATION"]
    campus = set()
    for bx, by in world.map.bases.values():
        if stations:
            campus.add(min(stations, key=lambda s: (abs(s.pos[0] - bx) + abs(s.pos[1] - by), s.id)).id)
    return campus


def direction_order(world: World) -> tuple[Pos, ...]:
    """거리가 같을 때의 방향 우선순위. 본진이 오른쪽 절반이면 뒤집어 자기 본진 기준으로 맞춘다."""
    base_x = world.map.bases[world.me][0]
    if base_x * 2 > world.map.width - 1:
        return tuple((-dx, -dy) for dx, dy in DEFAULT_ORDER)
    return DEFAULT_ORDER
