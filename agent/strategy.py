"""World를 받아 다음 행동을 결정하는 에이전트 두뇌: decide(world) -> actions.

M1 — 건물 효용 점수 + 깃발병 목표 분산 (M0 기준선은 tests/lv2_port.py에 보관)
- 건물 효용 = (추정 점수 + 기능 가치) / (도착 거리 + 점령 단계 수 + ETA_OFFSET)
- 깃발병을 한 명씩, 효용이 가장 높은 (깃발병, 건물) 짝부터 배정한다. 한 건물에는 한 명만 간다.
- 점령 비용은 이번 턴 수입까지 셈해 필요한 만큼만 남기고, 나머지로 생산한다.
- 이번 턴 점령할 건물이 둘 이상이면 효용 순으로 PRIORITY를 낸다.

M2 — 위험 판단 + 전투병 과제 + 깃발 뽑기 (docs/roadmap.md)
- 위협 맵: 다음 턴 적 전투병이 각 칸에 모일 수 있는 최대 인원 (이번 턴 본진 생산분 포함)
- 전투병 과제: 적 깃발병 처치(건물 위면 깃발 뽑기·방어 가치 추가), 점령 중인 우리 깃발병 호위.
  과제마다 이기는 데 필요한 인원이 있고, 인원을 채울 수 있는 과제 중 가치/거리가 큰 것부터 배정한다.
- 깃발병은 이번 턴 우리 전투병보다 적 전투병이 더 모일 수 있는 칸에 들어가지 않는다(피하거나 대기).
- 깃발 뽑기: 적 깃발병이 있는 건물은 전투병 과제가 잡혔을 때만 깃발병 목표가 되고, 깃발병은 전투병이
  이번 턴 도착할 때까지 한 칸 앞에서 기다린다(깃발병만 들어가면 경합이라 점령이 안 된다).
- 전투병 수: 적 전투병 + 1 (최소 MIN_WARRIORS)
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from agent.algorithms import DEFAULT_ORDER, distance_map, first_step, step_along, threat_map
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

MIN_WARRIORS = 3  # 전투병 최소 인원 (적 전투병이 적어도 이만큼은 둔다)
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
KILL_VALUE = 1.0  # 적 깃발병 한 명 제거의 가치 (점수 단위)
DANGER_DISCOUNT = 0.5  # 적 전투병이 닿는 건물은 깃발병 목표로서 가치를 이만큼 곱한다

_depots_taken: set[int] = set()  # 우리가 소유했던 보급소 id (보너스는 1회뿐). 한 프로세스 = 한 경기


@dataclass(frozen=True)
class Task:
    """전투병 과제: `pos`에 `need`명 이상 보내면 `value`만큼 얻는다."""

    pos: Pos
    need: int
    value: float


def decide(world: World) -> list[Action]:
    me, enemy = world.me, world.enemy
    remember(world)
    actions: list[Action] = []
    order = direction_order(world)
    passable = world.map.passable
    cache: dict[Pos, dict[Pos, int]] = {}

    def dist_to(pos: Pos) -> dict[Pos, int]:
        if pos not in cache:
            cache[pos] = distance_map([pos], passable)
        return cache[pos]

    key = normalizer(world)  # 동점일 때의 순서를 자기 본진 기준으로 맞춘다 → 양 진영이 거울처럼 움직인다
    enemy_flags = dict(sorted(world.units_of(enemy, "F"), key=lambda u: key(u[0])))
    enemy_warriors = world.units_of(enemy, "W")
    threat = threat_map(enemy_warriors + enemy_spawnable(world), passable)
    values = {b.id: building_value(world, b) for b in world.buildings.values()}
    others = sorted((b for b in world.buildings.values() if b.owner != me), key=lambda b: key(b.pos))
    dists = {b.id: dist_to(b.pos) for b in others}
    # 상대 깃발병이 있는 건물은 경합이라, 전투병이 뽑아 주기 전에는 깃발병 목표가 아니다
    free_targets = [b for b in others if b.pos not in enemy_flags]

    # 1) 지금 있는 깃발병으로 이번 턴 점령할 건물을 정하고, 그 비용만 남긴다.
    flags = sorted(world.units_of(me, "F"), key=lambda u: key(u[0]))
    plan = assign(flags, free_targets, dists, values, threat)
    need = sum(stage_cost(world, b) for b in capturing(plan, dists))
    income = BASE_INCOME + HALL_BONUS * len(world.owned(me, "HALL"))
    budget = max(0, world.gold[me] - max(0, need - income))  # 점령은 이번 턴 수입 뒤에 치른다

    # 2) 생산: 전투병(적 + 1까지) → 깃발병(목표 수만큼) → 남으면 전투병
    wc = warrior_cost(world, me)
    fc = UNIT_COST["F"]
    nf = sum(n for _, n in flags)
    nw = sum(n for _, n in world.units_of(me, "W"))
    want_w = max(MIN_WARRIORS, sum(n for _, n in enemy_warriors) + 1)
    make_w = min(max(0, want_w - nw), budget // wc) if nf or budget >= fc + wc else 0
    budget -= make_w * wc
    want_f = max(0, len(free_targets) + SPARE_FLAGS - nf)
    make_f = min(budget // fc, want_f)
    budget -= make_f * fc
    if make_f == want_f:  # 깃발병이 충분하면 남는 자원은 쌓아 두지 않고 전투병으로
        make_w += budget // wc
    if make_w:
        actions.append(Spawn("W", make_w))
    if make_f:
        actions.append(Spawn("F", make_f))
    base = world.map.bases[me]

    # 3) 전투병: 과제 배정 → 이동. 이동 뒤 칸별 인원(w_after)은 깃발병 안전 판단에 쓴다.
    warriors = with_spawned(world.units_of(me, "W"), base, make_w, key)
    tasks = sorted(warrior_tasks(world, enemy_flags, threat, values, capturing(plan, dists)),
                   key=lambda t: key(t.pos))
    w_plan, leftover, arrival = assign_warriors(warriors, tasks, dist_to)
    goals = set(enemy_flags) or {b.pos for b in free_targets}
    w_after: Counter[Pos] = Counter()
    w_steps: Counter[tuple[Pos, Pos]] = Counter()
    for pos, goal in w_plan:
        step = step_along(pos, dist_to(goal), order)
        w_after[step or pos] += 1
        if step:
            w_steps[(pos, step)] += 1
    for pos in leftover:
        step = first_step(pos, goals, passable, order)
        w_after[step or pos] += 1
        if step:
            w_steps[(pos, step)] += 1
    actions += [Move(src, "W", n, dst) for (src, dst), n in w_steps.items()]

    # 4) 깃발병: 전투병이 뽑아 줄 건물까지 목표에 넣어 다시 배정하고, 안전한 칸으로만 이동한다.
    pulled = {b.id for b in others if b.pos in enemy_flags and b.pos in arrival}
    targets = free_targets + [b for b in others if b.id in pulled]
    flags = with_spawned(flags, base, make_f, key)
    plan = assign(flags, targets, dists, values, threat, pulled)

    def safe(pos: Pos) -> bool:
        # 전투병 수가 같으면 서로 상쇄되고 남은 전투병이 없어 깃발병은 살아남는다
        return threat.get(pos, 0) <= w_after[pos]

    f_steps: Counter[tuple[Pos, Pos]] = Counter()
    for pos, b in plan:
        hold = b.id in pulled and arrival[b.pos] > 1  # 전투병이 이번 턴에 못 오면 한 칸 앞에서 대기
        step = flag_step(pos, b.pos, dists[b.id], order, safe, hold)
        if step:
            f_steps[(pos, step)] += 1
    actions += [Move(src, "F", n, dst) for (src, dst), n in f_steps.items()]

    now = sorted(capturing(plan, dists), key=lambda b: -values[b.id])
    if len(now) >= 2:
        actions.append(Priority(tuple(b.pos for b in now)))
    return actions


def remember(world: World) -> None:
    """턴을 넘어 기억해야 하는 것: 보급소 보너스를 이미 받았는지."""
    if world.turn <= 1:
        _depots_taken.clear()
    _depots_taken.update(b.id for b in world.owned(world.me, "DEPOT"))


# ------------------------------------------------------------------ 깃발병


def assign(
    flags: list[tuple[Pos, int]],
    targets: list[Building],
    dists: dict[int, dict[Pos, int]],
    values: dict[int, float],
    threat: dict[Pos, int] | None = None,
    pulled: set[int] = frozenset(),
) -> list[tuple[Pos, Building]]:
    """깃발병 한 명씩 (칸, 목표 건물) 짝. 효용이 큰 짝부터 탐욕적으로 고르고, 한 건물엔 한 명.

    목표가 다 차면 남는 인원은 효용이 가장 높은 건물로 겹쳐 보낸다. 닿을 수 없으면 제자리.
    적 전투병이 닿는 건물은 가치를 깎는다. 전투병이 깃발을 뽑아 줄 건물(`pulled`)은 한 단계로 끝난다.
    """
    threat = threat or {}
    worth = {
        b.id: values[b.id] * (DANGER_DISCOUNT if threat.get(b.pos, 0) and b.id not in pulled else 1.0)
        for b in targets
    }
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
                u = worth[b.id] / (d + (1 if b.id in pulled else stages(b)) + ETA_OFFSET)
                if best is None or u > best[0]:
                    best = (u, i, b)
        if best is None:
            break
        _, i, b = best
        plan.append((pool.pop(i), b))
        if free:
            free.remove(b)
    return plan


def flag_step(
    pos: Pos,
    goal: Pos,
    dist: dict[Pos, int],
    order: tuple[Pos, ...],
    safe: Callable[[Pos], bool],
    hold: bool,
) -> Pos | None:
    """깃발병 한 명의 다음 칸 (None = 제자리).

    목표 쪽으로 한 칸 줄이는 칸 중 안전한 곳 → 없으면 지금 칸이 안전할 때 대기 → 아니면 안전한 이웃으로
    피한다 → 그것도 없으면 그냥 목표 쪽으로 간다. `hold`면 목표 칸에 들어가지 않고 앞에서 기다린다.
    """
    here = dist.get(pos)
    if here is None:
        return None
    neighbors = [(pos[0] + dx, pos[1] + dy) for dx, dy in order]
    neighbors = [n for n in neighbors if n in dist]
    if here == 0:
        if safe(pos):
            return None
        closer = []
    else:
        closer = [n for n in neighbors if dist[n] == here - 1]
        for n in closer:
            if safe(n) and not (hold and n == goal):
                return n
        if safe(pos):
            return None
    escape = sorted((n for n in neighbors if safe(n)), key=lambda n: dist[n])
    if escape:
        return escape[0]
    return closer[0] if closer and not (hold and closer[0] == goal) else None


def capturing(plan: list[tuple[Pos, Building]], dists: dict[int, dict[Pos, int]]) -> list[Building]:
    """이번 턴 이동 뒤 깃발병이 올라가 있을 건물 (= 이번 턴 점령 단계가 진행될 건물)."""
    found: dict[int, Building] = {}
    for pos, b in plan:
        if dists[b.id].get(pos, 99) <= 1:
            found[b.id] = b
    return list(found.values())


# ------------------------------------------------------------------ 전투병


def warrior_tasks(
    world: World,
    enemy_flags: dict[Pos, int],
    threat: dict[Pos, int],
    values: dict[int, float],
    capturing_now: list[Building],
) -> list[Task]:
    """전투병이 할 일. 이기려면 그 칸에 모일 수 있는 적 전투병보다 한 명 많아야 한다."""
    tasks = []
    for pos, n in enemy_flags.items():
        b = world.building_at(pos)
        # 건물 위의 적 깃발병: 우리 건물이면 방어, 중립이면 점령 저지, 상대 건물이면 깃발 뽑기
        bonus = values[b.id] if b else 0.0
        tasks.append(Task(pos, threat.get(pos, 0) + 1, KILL_VALUE * n + bonus))
    for b in capturing_now:
        # 점령 중인 우리 깃발병 호위: 같은 수만 있어도 상쇄되어 깃발병이 산다
        if threat.get(b.pos, 0) and b.pos not in enemy_flags:
            tasks.append(Task(b.pos, threat[b.pos], values[b.id]))
    return tasks


def assign_warriors(
    warriors: list[tuple[Pos, int]],
    tasks: list[Task],
    dist_to: Callable[[Pos], dict[Pos, int]],
) -> tuple[list[tuple[Pos, Pos]], list[Pos], dict[Pos, int]]:
    """과제마다 가장 가까운 전투병 `need`명을 붙인다. 가치 / (1 + 가장 먼 전투병의 거리)가 큰 과제부터.

    돌려주는 값: (전투병 칸, 목표 칸) 목록, 과제를 못 받은 전투병 칸 목록, 과제 칸 → 전원 도착까지 턴 수.
    """
    pool = [pos for pos, n in warriors for _ in range(n)]
    plan: list[tuple[Pos, Pos]] = []
    arrival: dict[Pos, int] = {}
    remaining = list(tasks)
    while remaining and pool:
        best: tuple[float, Task, list[tuple[int, int]]] | None = None
        for task in remaining:
            dist = dist_to(task.pos)
            near = sorted((dist[p], i) for i, p in enumerate(pool) if p in dist)
            if len(near) < task.need:
                continue
            chosen = near[:task.need]
            score = task.value / (1 + chosen[-1][0])
            if best is None or score > best[0]:
                best = (score, task, chosen)
        if best is None:
            break
        _, task, chosen = best
        for _, i in sorted(chosen, key=lambda c: -c[1]):
            plan.append((pool.pop(i), task.pos))
        arrival[task.pos] = chosen[-1][0]
        remaining.remove(task)
    return plan, pool, arrival


def enemy_spawnable(world: World) -> list[tuple[Pos, int]]:
    """상대가 이번 턴 본진에서 새로 만들 수 있는 전투병 (생산한 유닛은 같은 턴에 바로 움직인다)."""
    enemy = world.enemy
    n = world.gold[enemy] // warrior_cost(world, enemy)
    return [(world.map.bases[enemy], n)] if n else []


def warrior_cost(world: World, team: str) -> int:
    return max(ENG_COST_FLOOR, UNIT_COST["W"] - len(world.owned(team, "ENG")) * ENG_DISCOUNT)


def with_spawned(
    units: list[tuple[Pos, int]], base: Pos, count: int, key: Callable[[Pos], Pos],
) -> list[tuple[Pos, int]]:
    """이번 턴 본진에서 새로 만든 유닛을 더한 목록 (정규화 좌표 순서)."""
    merged = Counter(dict(units))
    if count:
        merged[base] += count
    return sorted(merged.items(), key=lambda item: key(item[0]))


# ------------------------------------------------------------------ 건물 가치·비용


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
    """각 본진 쪽으로 가장 치우친 역 = 캠퍼스 역 (신촌역·안암역). 나머지 둘은 중앙의 서울역.

    "본진에서 가장 가까운 역"은 중앙 서울역이 더 가까운 맵이 있어 틀린다. 동점은 맵 중심에서 먼 역,
    그다음 본진 기준 정규화 좌표로 가른다(id로 가르면 두 진영의 판단이 대칭이 아니게 된다).
    """
    stations = [b for b in world.buildings.values() if b.kind == "STATION"]
    bases = list(world.map.bases.values())
    center = (world.map.width // 2, world.map.height // 2)
    campus = set()
    for home, away in (bases, bases[::-1]):
        flip = home > world.map.mirror(home)
        if stations:
            campus.add(min(stations, key=lambda s: (
                manhattan(s.pos, home) - manhattan(s.pos, away),
                -manhattan(s.pos, center),
                world.map.mirror(s.pos) if flip else s.pos,
            )).id)
    return campus


def manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def normalizer(world: World) -> Callable[[Pos], Pos]:
    """정렬 키: 자기 본진 기준으로 정규화한 (y, x). 본진이 오른쪽 절반이면 180° 뒤집는다."""
    w, h = world.map.width, world.map.height
    if world.map.bases[world.me][0] * 2 > w - 1:
        return lambda p: (h - 1 - p[1], w - 1 - p[0])
    return lambda p: (p[1], p[0])


def direction_order(world: World) -> tuple[Pos, ...]:
    """거리가 같을 때의 방향 우선순위. 본진이 오른쪽 절반이면 뒤집어 자기 본진 기준으로 맞춘다."""
    base_x = world.map.bases[world.me][0]
    if base_x * 2 > world.map.width - 1:
        return tuple((-dx, -dy) for dx, dy in DEFAULT_ORDER)
    return DEFAULT_ORDER
