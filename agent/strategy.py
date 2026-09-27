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

M3 — BT 국면 선택 (위층). 국면은 아래층(M1·M2 배정기)이 쓰는 가중치 묶음(Profile)이다.
- Selector: 위협 대응 → 굳히기 → 공격 → 확장. 위에서부터 처음 조건이 성립하는 국면을 고른다.
  - 위협 대응(THREAT): 적 깃발병이 GUARD_RADIUS 안에 들어온 우리 건물의 점수 합 ≥ THREAT_PRESSURE
  - 굳히기(HOLD): LATE_TURN 이후이고 추정 점수가 앞섬
  - 공격(ATTACK): 우리 전투병이 적보다 ATTACK_MARGIN 이상 많고 상대가 건물을 갖고 있음
  - 확장(EXPAND): 그 밖 (M2까지의 동작)
- 히스테리시스: 더 급한 국면으로는 바로 바꾸고, 덜 급한 국면으로는 지금 국면의 조건이 HOLD_TURNS턴
  연속 풀렸을 때만 내려간다(국면이 턴마다 흔들리지 않게).
- 지키기 과제: 적 깃발병이 GUARD_RADIUS 안에 있는 우리 건물에 전투병을 세운다(가치 × Profile.guard).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from agent.algorithms import DEFAULT_ORDER, distance_map, step_along, threat_map
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


@dataclass(frozen=True)
class Profile:
    """국면 하나 = 아래층 배정기의 가중치 묶음."""

    guard: float  # 우리 건물 지키기 과제의 가치 배수
    steal: float  # 상대 소유 건물을 깃발병 목표로 볼 때의 가치 배수 (빼앗으면 상대 점수도 준다)
    danger: float  # 적 전투병이 닿는 건물의 가치 배수 (작을수록 조심한다)
    extra_warriors: int  # 전투병 목표 인원 = 적 전투병 + 이 값


PROFILES = {
    "THREAT": Profile(guard=2.0, steal=1.0, danger=0.5, extra_warriors=2),
    "HOLD": Profile(guard=1.5, steal=1.0, danger=0.3, extra_warriors=2),
    "ATTACK": Profile(guard=0.5, steal=1.5, danger=0.5, extra_warriors=1),
    "EXPAND": Profile(guard=1.0, steal=1.0, danger=DANGER_DISCOUNT, extra_warriors=1),
}
PHASE_ORDER = ("THREAT", "HOLD", "ATTACK", "EXPAND")  # BT Selector의 우선순위
HOLD_TURNS = 3  # 덜 급한 국면으로 내려가려면 지금 국면의 조건이 이만큼 연속으로 풀려야 한다
GUARD_RADIUS = 3  # 적 깃발병이 이 거리 안에 있는 우리 건물은 위협받는 것으로 본다
THREAT_PRESSURE = 2.0  # 위협받는 우리 건물의 추정 점수 합이 이 이상이면 위협 대응
LATE_TURN = 110  # 굳히기: 이 턴 이후 추정 점수가 앞서면
ATTACK_MARGIN = 2  # 공격: 우리 전투병이 적보다 이만큼 많으면

_phase = {"name": "EXPAND", "calm": 0}  # 직전 국면과, 그 국면의 조건이 연속으로 풀린 턴 수

_depots_taken: set[int] = set()  # 우리가 소유했던 보급소 id (보너스는 1회뿐). 한 프로세스 = 한 경기
_dist_cache: dict[Pos, dict[Pos, int]] = {}  # 칸 → 그 칸까지의 거리표. 맵은 경기 내내 같으므로 턴을 넘어 재사용
_dist_cache_rows: list[tuple[str, ...]] = []  # 캐시를 만든 맵의 지형 (맵이 바뀌면 캐시를 비운다)


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
    def dist_to(pos: Pos) -> dict[Pos, int]:
        if pos not in _dist_cache:
            _dist_cache[pos] = distance_map([pos], passable)
        return _dist_cache[pos]

    key = normalizer(world)  # 동점일 때의 순서를 자기 본진 기준으로 맞춘다 → 양 진영이 거울처럼 움직인다
    enemy_flags = dict(sorted(world.units_of(enemy, "F"), key=lambda u: key(u[0])))
    enemy_warriors = world.units_of(enemy, "W")
    threat = threat_map(enemy_warriors + enemy_spawnable(world), passable)
    values = {b.id: building_value(world, b) for b in world.buildings.values()}
    others = sorted((b for b in world.buildings.values() if b.owner != me), key=lambda b: key(b.pos))
    dists = {b.id: dist_to(b.pos) for b in others}
    # 상대 깃발병이 있는 건물은 경합이라, 전투병이 뽑아 주기 전에는 깃발병 목표가 아니다
    free_targets = [b for b in others if b.pos not in enemy_flags]

    # 0) 위층: 국면 선택 → 이번 턴 아래층이 쓸 가중치
    pressured = pressured_buildings(world, enemy_flags, dist_to)
    active = phase_conditions(world, pressured)
    _phase["name"], _phase["calm"] = select_phase(active, _phase["name"], _phase["calm"])
    profile = PROFILES[_phase["name"]]

    # 1) 지금 있는 깃발병으로 이번 턴 점령할 건물을 정하고, 그 비용만 남긴다.
    flags = sorted(world.units_of(me, "F"), key=lambda u: key(u[0]))
    plan = assign(flags, free_targets, dists, values, threat, profile=profile)
    need = sum(stage_cost(world, b) for b in capturing(plan, dists))
    income = BASE_INCOME + HALL_BONUS * len(world.owned(me, "HALL"))
    budget = max(0, world.gold[me] - max(0, need - income))  # 점령은 이번 턴 수입 뒤에 치른다

    # 2) 생산: 전투병(적 + 1까지) → 깃발병(목표 수만큼) → 남으면 전투병
    wc = warrior_cost(world, me)
    fc = UNIT_COST["F"]
    nf = sum(n for _, n in flags)
    nw = sum(n for _, n in world.units_of(me, "W"))
    want_w = max(MIN_WARRIORS, sum(n for _, n in enemy_warriors) + profile.extra_warriors)
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
    tasks = warrior_tasks(world, enemy_flags, threat, values, capturing(plan, dists))
    tasks += guard_tasks(pressured, threat, values, profile)
    tasks.sort(key=lambda t: key(t.pos))
    w_plan, leftover, arrival = assign_warriors(warriors, tasks, dist_to)
    # 과제가 없는 전투병은 모두 같은 목표 집합으로 가므로, 목표 쪽에서 BFS를 한 번만 한다.
    # (전투병마다 BFS를 하면 유닛 수에 비례해 느려진다 — 서버에서 186명일 때 응답 214 ms)
    goals = set(enemy_flags) or {b.pos for b in free_targets}
    goal_dist = distance_map(goals, passable)
    moving: Counter[tuple[Pos, Pos | None]] = Counter()  # (출발 칸, 목표 칸 또는 None=공통 목표) → 인원
    moving.update(w_plan)
    moving.update((pos, None) for pos in leftover)
    w_after: Counter[Pos] = Counter()
    w_steps: Counter[tuple[Pos, Pos]] = Counter()
    for (pos, goal), n in moving.items():
        step = step_along(pos, goal_dist if goal is None else dist_to(goal), order)
        w_after[step or pos] += n
        if step:
            w_steps[(pos, step)] += n
    actions += [Move(src, "W", n, dst) for (src, dst), n in w_steps.items()]

    # 4) 깃발병: 전투병이 뽑아 줄 건물까지 목표에 넣어 다시 배정하고, 안전한 칸으로만 이동한다.
    pulled = {b.id for b in others if b.pos in enemy_flags and b.pos in arrival}
    targets = free_targets + [b for b in others if b.id in pulled]
    flags = with_spawned(flags, base, make_f, key)
    plan = assign(flags, targets, dists, values, threat, pulled, profile)

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
    """턴을 넘어 기억해야 하는 것: 보급소 보너스를 이미 받았는지, 직전 국면, 거리표 캐시."""
    if world.turn <= 1:
        _depots_taken.clear()
        _phase.update(name="EXPAND", calm=0)
    _depots_taken.update(b.id for b in world.owned(world.me, "DEPOT"))
    if _dist_cache_rows != [world.map.rows]:
        _dist_cache.clear()
        _dist_cache_rows[:] = [world.map.rows]


def note() -> str:
    """턴 로그에 남길 한 단어: 이번 턴 국면."""
    return _phase["name"]


# ------------------------------------------------------------------ 국면 (BT 위층)


def pressured_buildings(
    world: World, enemy_flags: dict[Pos, int], dist_to: Callable[[Pos], dict[Pos, int]],
) -> list[tuple[Building, int]]:
    """적 깃발병이 GUARD_RADIUS 안에 들어온 우리 건물과, 가장 가까운 적 깃발병까지의 거리."""
    found = []
    for b in world.owned(world.me):
        dist = dist_to(b.pos)
        near = min((dist[p] for p in enemy_flags if p in dist), default=None)
        if near is not None and near <= GUARD_RADIUS:
            found.append((b, near))
    return found


def phase_conditions(world: World, pressured: list[tuple[Building, int]]) -> dict[str, bool]:
    """국면마다 조건이 성립하는가. 확장은 늘 성립한다(기본 국면)."""
    me, enemy = world.me, world.enemy
    pressure = sum(estimated_score(world, b) for b, _ in pressured)
    mine = sum(estimated_score(world, b) for b in world.owned(me))
    theirs = sum(estimated_score(world, b) for b in world.owned(enemy))
    my_w = sum(n for _, n in world.units_of(me, "W"))
    enemy_w = sum(n for _, n in world.units_of(enemy, "W"))
    return {
        "THREAT": pressure >= THREAT_PRESSURE,
        "HOLD": world.turn >= LATE_TURN and mine > theirs,
        "ATTACK": my_w >= enemy_w + ATTACK_MARGIN and bool(world.owned(enemy)),
        "EXPAND": True,
    }


def select_phase(active: dict[str, bool], current: str, calm: int) -> tuple[str, int]:
    """BT Selector + 히스테리시스. 돌려주는 값: (이번 턴 국면, 갱신된 calm).

    조건이 성립하는 국면 중 우선순위가 가장 높은 것을 고른다. 그것이 지금 국면보다 급하거나 같으면
    바로 따르고, 덜 급하면 지금 국면의 조건이 HOLD_TURNS턴 연속 풀렸을 때만 내려간다.
    """
    wanted = next(p for p in PHASE_ORDER if active[p])
    if PHASE_ORDER.index(wanted) <= PHASE_ORDER.index(current):
        return wanted, 0
    if active[current]:
        return current, 0
    calm += 1
    return (wanted, 0) if calm >= HOLD_TURNS else (current, calm)


# ------------------------------------------------------------------ 깃발병


def assign(
    flags: list[tuple[Pos, int]],
    targets: list[Building],
    dists: dict[int, dict[Pos, int]],
    values: dict[int, float],
    threat: dict[Pos, int] | None = None,
    pulled: set[int] = frozenset(),
    profile: Profile = PROFILES["EXPAND"],
) -> list[tuple[Pos, Building]]:
    """깃발병 한 명씩 (칸, 목표 건물) 짝. 효용이 큰 짝부터 탐욕적으로 고르고, 한 건물엔 한 명.

    목표가 다 차면 남는 인원은 효용이 가장 높은 건물로 겹쳐 보낸다. 닿을 수 없으면 제자리.
    적 전투병이 닿는 건물은 가치를 깎고(× profile.danger), 상대 소유 건물은 가치를 곱한다(× profile.steal).
    전투병이 깃발을 뽑아 줄 건물(`pulled`)은 한 단계로 끝난다.
    """
    threat = threat or {}
    worth = {
        b.id: values[b.id]
        * (profile.danger if threat.get(b.pos, 0) and b.id not in pulled else 1.0)
        * (profile.steal if b.owner is not None else 1.0)
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


def guard_tasks(
    pressured: list[tuple[Building, int]], threat: dict[Pos, int], values: dict[int, float], profile: Profile,
) -> list[Task]:
    """지키기: 적 깃발병이 다가오는 우리 건물 위에 전투병을 세운다. 올라오는 적 깃발병을 그 칸에서 잡는다."""
    return [Task(b.pos, threat.get(b.pos, 0) + 1, values[b.id] * profile.guard) for b, _ in pressured]


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


def estimated_score(world: World, b: Building) -> float:
    """아는 점수, 모르면 기대값 (진영 건물 SIDE_SCORE_GUESS, 중앙 건물 CENTER_SCORE_GUESS)."""
    score = world.known_score(b)
    if score is None:
        return CENTER_SCORE_GUESS if is_center(world, b) else SIDE_SCORE_GUESS
    return score


def building_value(world: World, b: Building) -> float:
    """건물 하나의 가치(점수 단위) = 추정 점수 + 기능 가치."""
    score = estimated_score(world, b)
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
