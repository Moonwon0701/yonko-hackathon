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

구조 — 행동 트리(BT). decide는 TURN_TREE를 한 번 실행한다(트리 전체: tree_text(), 조립은 파일 맨 끝,
노드 정의는 agent/bt.py). 유닛이 하는 일은 모두 과제(Task) 하나로 나타낸다: 점령(깃발병 1명)과
처치·호위·지키기(전투병 need명).
- TURN_TREE(Sequence): 상황 읽기 → PHASE_TREE → 깃발병 1차 → 전투병 → 깃발병 2차 → 우선순위
- PHASE_TREE(Selector): 처음 성립하는 국면 가지가 이번 턴 과제 목록의 구성(과제 종류와 가중치)을 정한다
- 배정·생산·이동 단계는 국면이 정한 과제 목록만 보고 움직인다(국면별 분기가 트리 밖에 없다)
- FLAG_TREE(Selector): 깃발병 한 명의 다음 칸 — 안전하게 다가가기 → 대기 → 피하기 → 그래도 다가가기
- 효용 배정기(assign_flags, assign_warriors)는 트리의 행동 잎 안에서 호출하는 부품이다.

M3 — 국면 선택 (위층). 국면 = 이번 턴 과제 목록을 만드는 방법(과제 종류 + 가중치).
- Selector: 위협 대응 → 굳히기 → 공격 → 확장. 위에서부터 처음 조건이 성립하는 국면을 고른다.
  - 위협 대응(THREAT): 적 깃발병이 GUARD_RADIUS 안에 들어온 우리 건물의 점수 합 ≥ THREAT_PRESSURE
  - 굳히기(HOLD): LATE_TURN 이후이고 추정 점수가 앞섬
  - 공격(ATTACK): 우리 전투병이 적보다 ATTACK_MARGIN 이상 많고 상대가 건물을 갖고 있음
  - 확장(EXPAND): 그 밖 (M2까지의 동작)
- 국면 유지(Latch 노드): 더 급한 국면으로는 바로 바꾸고, 덜 급한 국면으로는 지금 국면의 조건이 HOLD_TURNS턴
  연속 풀렸을 때만 내려간다(국면이 턴마다 흔들리지 않게).
- 지키기 과제: 적 깃발병이 GUARD_RADIUS 안에 있는 우리 건물에 전투병을 세운다(가치 × 국면별 배수).
- 몰아내기 과제: 적 전투병이 EVICT_RADIUS 안에 온 우리 핵심 건물(학생회관·공학관·병원)에 전투병을 세운다.
  적이 전투병을 먼저 모아 두고 깃발병을 나중에 들이는 경우를 막는다(9/28 리더보드 패배 분석).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

from agent.algorithms import DEFAULT_ORDER, distance_map, manhattan, step_along, threat_map
from agent.bt import Act, Condition, Latch, Node, Selector, Sequence
from agent.world import (
    BASE_INCOME,
    HALL_BONUS,
    TELE_MAX_UNITS,
    TOTAL_TURNS,
    UNIT_COST,
    Action,
    Building,
    Move,
    Pos,
    Priority,
    Spawn,
    Tele,
    World,
)

MIN_WARRIORS = 3  # 전투병 최소 인원 (적 전투병이 적어도 이만큼은 둔다)
SPARE_FLAGS = 1  # 목표 건물 수보다 이만큼 더 많은 깃발병까지만 만든다
MIN_FLAGS = 2  # 깃발병이 이보다 적으면 전투병보다 먼저 만든다 (목표가 있을 때만)
BEHIND_EXTRA_FLAGS = 1  # 상대가 건물을 더 가지면 깃발병 최소 인원에 더한다

# 점수를 모를 때의 기대값. 규칙: 신촌·안암 건물 1~2점, 중앙 건물 2~4점
SIDE_SCORE_GUESS = 1.5
CENTER_SCORE_GUESS = 3.0
SIDE_KINDS = {"HALL", "LIBRARY", "ENG", "HOSPITAL"}  # 역은 위치로 가린다(campus_stations)
CENTER_KINDS = {"WATCH", "DEPOT"}

# 기능 가치 (점수 단위)
HALL_VALUE_PER_TURN = 0.02  # 학생회관: 남은 턴 × 이 값 (초반일수록 크다)
DEPOT_VALUE = 2.0  # 보급소: 최초 점령 +15 자원, 팀별 건물당 1회
# 공학관: 전투병 값 3 → 2, 같은 자원으로 전투병 1.5배. 진 경기는 전투병(= 생산량) 차이로 벌어지므로
# 0.5 → 2.0으로 올렸다(main 상대 400경기 약 61% — docs/benchmarks.md)
FUNCTION_VALUE = {"LIBRARY": 0.5, "ENG": 2.0, "HOSPITAL": 0.5, "STATION": 0.3, "WATCH": 0.3}

ETA_OFFSET = 2  # 효용 분모에 더하는 값. 클수록 거리보다 건물 가치를 중시한다
KILL_VALUE = 1.0  # 적 깃발병 한 명 제거의 가치 (점수 단위)
DANGER_DISCOUNT = 0.5  # 적 전투병이 닿는 건물은 깃발병 목표로서 가치를 이만큼 곱한다


# 국면별 과제 구성(종류·가중치)은 파일 끝 PHASE_TREE에 가지마다 적는다.
HOLD_TURNS = 3  # 덜 급한 국면으로 내려가려면 지금 국면의 조건이 이만큼 연속으로 풀려야 한다
GUARD_RADIUS = 3  # 적 깃발병이 이 거리 안에 있는 우리 건물은 위협받는 것으로 본다
THREAT_PRESSURE = 2.0  # 위협받는 우리 건물의 추정 점수 합이 이 이상이면 위협 대응
LATE_TURN = 110  # 굳히기: 이 턴 이후 추정 점수가 앞서면
ATTACK_MARGIN = 2  # 공격: 우리 전투병이 적보다 이만큼 많으면
# 몰아내기: 적 전투병이 이 거리 안에 온 우리 핵심 건물에 전투병을 세운다. 적 깃발병만 보던 지키기로는 적이 전투병을
# 먼저 건물 위·옆에 모아 두고 깃발병을 나중에 들이는 경우를 못 막았다(9/28 리더보드 패배 4경기 중 3경기)
EVICT_KINDS = {"HALL", "ENG", "HOSPITAL"}
EVICT_RADIUS = 2
EVICT_WEIGHT = 1.0
# 전선: 적이 오기 전에, 점령을 끝낸 우리 건물 중 가장 노출된 곳에 전투병을 미리 세운다.
# 노출 순위 = 가장 가까운 적·중립 건물까지 거리 + FRONT_MARGIN_WEIGHT × (적 본진 거리 − 우리 본진 거리). 작을수록 전선
FRONT_COUNT = 3
FRONT_MARGIN_WEIGHT = 0.5
FRONT_NEED = 1  # 호위 없는 적 깃발병은 전투병 한 명으로 막힌다

_phase = {"name": "EXPAND", "calm": 0}  # 직전 국면과, 그 국면의 조건이 연속으로 풀린 턴 수

_depots_taken: set[int] = set()  # 우리가 소유했던 보급소 id (보너스는 1회뿐). 한 프로세스 = 한 경기
_dist_cache: dict[Pos, dict[Pos, int]] = {}  # 칸 → 그 칸까지의 거리표. 맵은 경기 내내 같으므로 턴을 넘어 재사용
_tele_cache: dict[tuple[Pos, tuple[Pos, ...]], dict[Pos, int]] = {}  # (칸, 우리 역들) → 역 포함 거리표
_dist_cache_rows: list[tuple[str, ...]] = []  # 캐시를 만든 맵의 지형 (맵이 바뀌면 캐시를 비운다)


@dataclass(frozen=True)
class Task:
    """과제: `unit` 병종을 `pos`에 `need`명 이상 보내면 `value`만큼 얻는다.

    점령 과제는 깃발병 한 명이 맡고, 대상 건물과 남은 점령 단계 수(`stages`)를 함께 적는다.
    """

    kind: str  # 점령 · 처치 · 호위 · 지키기
    unit: str  # "F" | "W"
    pos: Pos
    need: int
    value: float
    building: Building | None = None
    stages: int = 0


# ------------------------------------------------------------------ 한 턴 (루트 Sequence)


class Turn:
    """한 턴의 칠판(blackboard). 트리의 각 단계가 앞 단계의 결과를 여기서 읽고, 자기 결과를 적는다."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.phase = _phase
        self.actions: list[Action] = []
        # 국면 가지가 채운다: 병종별 과제 만들기 함수, 전투병 목표 인원의 추가분
        self.makers: dict[str, list[Maker]] = {"F": [], "W": []}
        self.extra_warriors = 0

    def tasks(self, unit: str) -> list[Task]:
        """이번 국면이 켠 과제 만들기 함수로 `unit` 병종의 과제 목록을 만든다."""
        return [task for maker in self.makers[unit] for task in maker(self)]

    def dist_to(self, pos: Pos) -> dict[Pos, int]:
        """걸어서 `pos`까지의 거리표 (경기 내내 캐시)."""
        if pos not in _dist_cache:
            _dist_cache[pos] = distance_map([pos], self.world.map.passable)
        return _dist_cache[pos]

    def tele_to(self, pos: Pos) -> dict[Pos, int]:
        """우리 역끼리 순간이동(비용 1)을 포함한 `pos`까지의 거리표. 역이 2개 미만이면 걸어서만."""
        if not self.gates:
            return self.dist_to(pos)
        if (pos, self.gates) not in _tele_cache:
            _tele_cache[(pos, self.gates)] = distance_map([pos], self.world.map.passable, self.gates)
        return _tele_cache[(pos, self.gates)]


Maker = Callable[[Turn], list[Task]]  # 과제 만들기 함수: 칠판을 읽고 과제 목록을 돌려준다


def decide(world: World) -> list[Action]:
    turn = Turn(world)
    TURN_TREE.tick(turn)
    return turn.actions


def read_situation(t: Turn) -> None:
    """상황 읽기: 적 위치·위협 맵·건물 가치·목표 후보·국면 조건."""
    world = t.world
    me, enemy = world.me, world.enemy
    remember(world)
    t.order = direction_order(world)
    t.key = key = normalizer(world)  # 동점일 때의 순서를 자기 본진 기준으로 맞춘다 → 양 진영이 거울처럼 움직인다
    # 역 순간이동: 우리 역이 2개 이상이면 역끼리 비용 1로 이어진 경로도 최단거리에 넣는다 (전투병 이동에만.
    # 깃발병에 쓰면 효과가 없었다 — docs/benchmarks.md)
    stations = sorted((b.pos for b in world.owned(me, "STATION")), key=key)
    t.gates = tuple(stations) if len(stations) >= 2 else ()
    t.enemy_flags = dict(sorted(world.units_of(enemy, "F"), key=lambda u: key(u[0])))
    t.enemy_warriors = world.units_of(enemy, "W")
    t.threat = threat_map(t.enemy_warriors + enemy_spawnable(world), world.map.passable)
    t.values = {b.id: building_value(world, b) for b in world.buildings.values()}
    t.others = sorted((b for b in world.buildings.values() if b.owner != me), key=lambda b: key(b.pos))
    # 상대 깃발병이 있는 건물은 경합이라, 전투병이 뽑아 주기 전에는 깃발병 목표가 아니다
    t.free_targets = [b for b in t.others if b.pos not in t.enemy_flags]
    t.pressured = pressured_buildings(world, t.enemy_flags, t.dist_to)
    t.active = phase_conditions(world, t.pressured)


def enter_phase(t: Turn, name: str) -> None:
    """국면 가지의 첫 행동 잎: 지금 국면을 기록한다(다음 턴 Latch가 읽는다)."""
    if t.phase["name"] != name:
        t.phase.update(name=name, calm=0)


def plan_flags(t: Turn) -> None:
    """깃발병 1차: 지금 있는 깃발병을 점령 과제에 배정해, 이번 턴 점령 단계가 진행될 건물을 정한다."""
    t.flags = sorted(t.world.units_of(t.world.me, "F"), key=lambda u: t.key(u[0]))
    t.targets, t.pulled = t.free_targets, set()
    t.f_tasks = t.tasks("F")
    t.capturing_now = capturing(assign_flags(t.flags, t.f_tasks, t.dist_to), t.dist_to)


def reserve_capture_cost(t: Turn) -> None:
    """이번 턴 점령 비용만 남기고 나머지를 생산 예산으로."""
    world, me = t.world, t.world.me
    need = sum(world.stage_cost(task.building) for task in t.capturing_now)
    income = BASE_INCOME + HALL_BONUS * len(world.owned(me, "HALL"))
    t.budget = max(0, world.gold[me] - max(0, need - income))  # 점령은 이번 턴 수입 뒤에 치른다


def plan_warrior_tasks(t: Turn) -> None:
    """전투병 과제 목록(이번 국면이 켠 종류)과, 과제가 없는 전투병의 공통 목표."""
    t.w_tasks = sorted(t.tasks("W"), key=lambda task: t.key(task.pos))
    # 과제가 없는 전투병은 모두 같은 목표 집합으로 가므로, 목표 쪽에서 BFS를 한 번만 한다.
    # (전투병마다 BFS를 하면 유닛 수에 비례해 느려진다 — 서버에서 186명일 때 응답 214 ms)
    t.goals = set(t.enemy_flags) or {b.pos for b in t.free_targets}
    t.goal_dist = distance_map(t.goals, t.world.map.passable)


def produce(t: Turn) -> None:
    """생산: 깃발병(MIN_FLAGS까지) → 전투병(적 + 추가 인원까지) → 깃발병(점령 과제 수만큼) → 남으면 전투병.
    위치는 M4 병원 생산."""
    world, me, key = t.world, t.world.me, t.key
    budget = t.budget
    wc = world.warrior_cost(me)
    fc = UNIT_COST["F"]
    nf = sum(n for _, n in t.flags)
    nw = sum(n for _, n in world.units_of(me, "W"))
    want_w = max(MIN_WARRIORS, sum(n for _, n in t.enemy_warriors) + t.extra_warriors)
    want_f = max(0, len(t.f_tasks) + SPARE_FLAGS - nf)
    # 깃발병 최소 인원은 전투병보다 먼저 채운다. 전투병을 "적 + 추가 인원"까지 먼저 채우면, 상대가 전투병을
    # 더 뽑는 경기에서는 자원이 전부 전투병으로 가서 깃발병을 다시 만들지 못했다(9/27 리더보드 패배 경기:
    # 깃발병 0명인 22턴 중 21턴을 전투병만 생산, 건물 6 → 15개를 내줌)
    # 건물이 밀리면 최소 인원을 늘린다: 적 전투병이 훨씬 많으면 전투병 목표를 끝내 못 채워, 깃발병이 최소 인원에
    # 묶인 채 건물을 되찾지 못했다(9/28 리더보드 패배 28·29: 20턴 이후 깃발병 2명 이하 81·75턴)
    behind = len(world.owned(world.enemy)) > len(world.owned(me))
    min_f = MIN_FLAGS + (BEHIND_EXTRA_FLAGS if behind else 0)
    make_f = min(want_f, max(0, min_f - nf), budget // fc)
    budget -= make_f * fc
    make_w = min(max(0, want_w - nw), budget // wc)
    budget -= make_w * wc
    more_f = min(budget // fc, want_f - make_f)
    make_f += more_f
    budget -= more_f * fc
    if make_f == want_f:  # 깃발병이 충분하면 남는 자원은 쌓아 두지 않고 전투병으로
        make_w += budget // wc
    t.make_w, t.make_f = make_w, make_f
    # M4: 생산 위치 — 본진 또는 우리 병원 중 목표에 가장 가까운 안전한 곳 (동점이면 본진)
    passable = world.map.passable
    sites = [world.map.bases[me]] + sorted((b.pos for b in world.owned(me, "HOSPITAL")), key=key)
    # 전투병은 위협받는 병원에서도 만든다: 전투병끼리는 1:1로 상쇄되어 손해가 없고, 그 자리에서 병원을 지킨다.
    # (위협받는 병원을 빼던 때는 적이 다가오는 턴마다 먼 본진에서 생산했다 — 9/28 리더보드 패배 3경기에서 22~27턴)
    t.w_site = spawn_site(sites, distance_map(t.goals | {task.pos for task in t.w_tasks}, passable), {})
    t.f_site = spawn_site(sites, distance_map({task.pos for task in t.f_tasks}, passable), t.threat)
    if make_w:
        t.actions.append(Spawn("W", make_w, None if t.w_site == sites[0] else t.w_site))
    if make_f:
        t.actions.append(Spawn("F", make_f, None if t.f_site == sites[0] else t.f_site))


def plan_warriors(t: Turn) -> None:
    """전투병 배정: 과제마다 가장 가까운 전투병을 붙인다(이번 턴 새로 만든 전투병 포함)."""
    warriors = with_spawned(t.world.units_of(t.world.me, "W"), t.w_site, t.make_w, t.key)
    t.w_plan, t.w_idle, t.arrival = assign_warriors(warriors, t.w_tasks, t.dist_to)


def move_warriors(t: Turn) -> None:
    """전투병 이동(역 순간이동 포함). 이동 뒤 칸별 인원(w_after)은 깃발병 안전 판단에 쓴다."""
    world, key, order, gates = t.world, t.key, t.order, t.gates
    moving: Counter[tuple[Pos, Pos | None]] = Counter()  # (출발 칸, 목표 칸 또는 None=공통 목표) → 인원
    moving.update(t.w_plan)
    moving.update((pos, None) for pos in t.w_idle)
    goal_tele = distance_map(t.goals, world.map.passable, gates) if gates else t.goal_dist
    w_after: Counter[Pos] = Counter()
    w_steps: Counter[tuple[Pos, Pos]] = Counter()
    w_jumps: Counter[tuple[Pos, Pos]] = Counter()  # 순간이동을 원하는 (출발 역, 도착 역) → 인원
    groups = []
    for i, ((pos, goal), n) in enumerate(moving.items()):
        walk = t.goal_dist if goal is None else t.dist_to(goal)
        tele = goal_tele if goal is None else t.tele_to(goal)
        groups.append((pos not in gates, tele.get(pos, 0), key(pos), i, pos, n, walk, tele))
    queued = 0  # 이번 턴 순간이동 경로에 태운 인원 = 대기열. 역에 이미 선 인원부터 센다
    for *_, pos, n, walk, tele in sorted(groups):
        # 순간이동은 턴당 TELE_MAX_UNITS명뿐이다. 대기열에서 기다릴 턴까지 더해도 걷기보다 빠른 인원만
        # 역으로 보낸다. (전원을 역으로 보내면 못 탄 인원이 걸어서 물러났다가 다음 턴 돌아오기를 반복했다 —
        # 9/27 리더보드 리플레이에서 역 옆 두 칸을 오간 전투병 최대 66명)
        via = 0
        if gates and pos in tele:
            gain = walk.get(pos, 10**6) - tele[pos]
            via = min(n, max(0, TELE_MAX_UNITS * gain - queued))
        queued += via
        step = step_along(pos, tele, order, gates) if via else None
        if step and manhattan(pos, step) > 1:
            w_jumps[(pos, step)] += via  # 도착 인원(w_after)은 순간이동 한 쌍을 고른 뒤에 센다
        else:
            if step:
                w_steps[(pos, step)] += via
            w_after[step or pos] += via
        step = step_along(pos, walk, order)
        if step and n - via:
            w_steps[(pos, step)] += n - via
        w_after[step or pos] += n - via
    jump = pick_jump(w_jumps, key)
    for (src, dst), n in w_jumps.items():
        sent = min(n, TELE_MAX_UNITS) if (src, dst) == jump else 0
        if sent:
            t.actions.append(Tele(src, "W", sent, dst))
            w_after[dst] += sent
        w_after[src] += n - sent  # 못 탄 인원은 역에서 다음 차례를 기다린다
    t.actions += [Move(src, "W", n, dst) for (src, dst), n in w_steps.items()]
    t.w_after = w_after


def replan_flags(t: Turn) -> None:
    """깃발병 2차: 전투병이 깃발을 뽑아 줄 건물을 점령 과제에 넣고, 새로 만든 깃발병까지 다시 배정한다."""
    t.pulled = {b.id for b in t.others if b.pos in t.enemy_flags and b.pos in t.arrival}
    t.targets = t.free_targets + [b for b in t.others if b.id in t.pulled]
    flags = with_spawned(t.flags, t.f_site, t.make_f, t.key)
    t.plan = assign_flags(flags, t.tasks("F"), t.dist_to)


def move_flags(t: Turn) -> None:
    """깃발병 이동: 한 명씩 FLAG_TREE로 다음 칸을 정한다."""
    threat, w_after = t.threat, t.w_after

    def safe(pos: Pos) -> bool:
        # 전투병 수가 같으면 서로 상쇄되고 남은 전투병이 없어 깃발병은 살아남는다
        return threat.get(pos, 0) <= w_after[pos]

    f_steps: Counter[tuple[Pos, Pos]] = Counter()
    for pos, task in t.plan:
        # 전투병이 이번 턴에 못 오면 한 칸 앞에서 대기
        hold = task.building.id in t.pulled and t.arrival[task.pos] > 1
        step = flag_step(pos, task.pos, t.dist_to(task.pos), t.order, safe, hold)
        if step:
            f_steps[(pos, step)] += 1
    t.actions += [Move(src, "F", n, dst) for (src, dst), n in f_steps.items()]


def set_priority(t: Turn) -> None:
    """이번 턴 점령할 건물이 둘 이상이면 가치 순으로 PRIORITY."""
    now = sorted(capturing(t.plan, t.dist_to), key=lambda task: -t.values[task.building.id])
    if len(now) >= 2:
        t.actions.append(Priority(tuple(task.pos for task in now)))


def remember(world: World) -> None:
    """턴을 넘어 기억해야 하는 것: 보급소 보너스를 이미 받았는지, 직전 국면, 거리표 캐시."""
    if world.turn <= 1:
        _depots_taken.clear()
        _phase.update(name="EXPAND", calm=0)
    _depots_taken.update(b.id for b in world.owned(world.me, "DEPOT"))
    if _dist_cache_rows != [world.map.rows]:
        _dist_cache.clear()
        _tele_cache.clear()
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
    """PHASE_TREE만 따로 실행한다(테스트용). 돌려주는 값: (이번 턴 국면, 갱신된 calm).

    조건이 성립하는 국면 중 우선순위가 가장 높은 것을 고른다. 그것이 지금 국면보다 급하거나 같으면
    바로 따르고, 덜 급하면 지금 국면의 조건이 HOLD_TURNS턴 연속 풀렸을 때만 내려간다(Latch).
    """
    ctx = SimpleNamespace(active=active, phase={"name": current, "calm": calm}, makers={"F": [], "W": []})
    PHASE_TREE.tick(ctx)
    return ctx.phase["name"], ctx.phase["calm"]


# ------------------------------------------------------------------ 과제 만들기 (국면 가지가 켠다)


def capture_tasks(t: Turn, steal: float, danger: float) -> list[Task]:
    """점령: 목표 건물마다 깃발병 한 명. 상대 소유 건물은 가치 × steal(빼앗으면 상대 점수도 준다), 적 전투병이
    닿는 건물은 × danger(작을수록 조심한다. 전투병이 깃발을 뽑아 줄 건물은 빼고).
    남은 점령 단계: 뽑아 줄 건물·중립은 1, 상대 건물은 중립화 → 점령 2 (목표에 우리 건물은 없다).
    """
    tasks = []
    for b in t.targets:
        pulled = b.id in t.pulled
        value = (t.values[b.id]
                 * (danger if t.threat.get(b.pos, 0) and not pulled else 1.0)
                 * (steal if b.owner is not None else 1.0))
        tasks.append(Task("점령", "F", b.pos, 1, value, b, 1 if pulled or b.owner is None else 2))
    return tasks


def kill_tasks(t: Turn) -> list[Task]:
    """처치: 적 깃발병. 이기려면 그 칸에 모일 수 있는 적 전투병보다 한 명 많아야 한다.
    건물 위면 그 건물 가치를 더한다: 우리 건물이면 방어, 중립이면 점령 저지, 상대 건물이면 깃발 뽑기."""
    tasks = []
    for pos, n in t.enemy_flags.items():
        b = t.world.building_at(pos)
        bonus = t.values[b.id] if b else 0.0
        tasks.append(Task("처치", "W", pos, t.threat.get(pos, 0) + 1, KILL_VALUE * n + bonus))
    return tasks


def escort_tasks(t: Turn) -> list[Task]:
    """호위: 이번 턴 점령 중인 우리 깃발병. 같은 수만 있어도 상쇄되어 깃발병이 산다."""
    tasks = []
    for c in t.capturing_now:
        b = c.building
        if t.threat.get(b.pos, 0) and b.pos not in t.enemy_flags:
            tasks.append(Task("호위", "W", b.pos, t.threat[b.pos], t.values[b.id]))
    return tasks


def guard_tasks(t: Turn, weight: float) -> list[Task]:
    """지키기: 적 깃발병이 다가오는 우리 건물 위에 전투병을 세운다(가치 × weight). 올라오는 적 깃발병을
    그 칸에서 잡는다."""
    return [Task("지키기", "W", b.pos, t.threat.get(b.pos, 0) + 1, t.values[b.id] * weight) for b, _ in t.pressured]


def evict_tasks(t: Turn) -> list[Task]:
    """몰아내기: 적 전투병이 EVICT_RADIUS 안에 온 우리 핵심 건물(EVICT_KINDS) 위에 전투병을 세운다. 건물 위의 적
    전투병은 이겨서 몰아내고, 옆의 적은 올라오지 못하게 한다. 지키기 과제가 이미 있는 건물은 뺀다."""
    guarded = {b.id for b, _ in t.pressured}
    tasks = []
    for b in t.world.owned(t.world.me):
        if b.kind not in EVICT_KINDS or b.id in guarded:
            continue
        dist = t.dist_to(b.pos)
        if any(dist.get(p, 99) <= EVICT_RADIUS for p, _ in t.enemy_warriors):
            tasks.append(Task("몰아내기", "W", b.pos, t.threat.get(b.pos, 0) + 1, t.values[b.id] * EVICT_WEIGHT))
    return tasks


def frontline_tasks(t: Turn, weight: float) -> list[Task]:
    """전선: 점령을 끝낸 우리 건물 중 노출 순위(front_rank)가 앞선 FRONT_COUNT곳에 전투병 FRONT_NEED명을 미리
    세운다(가치 × weight). 적 깃발병이 다가온 뒤 움직이는 지키기와 달리 상대의 움직임을 기다리지 않는다.
    지키기 과제가 있는 건물과 적 전투병이 EVICT_RADIUS 안에 온 건물은 뺀다(한 명으로는 못 지킨다 — 지키기·몰아내기·
    처치가 맡는다)."""
    world = t.world
    guarded = {b.id for b, _ in t.pressured}
    ranked = []
    for b in world.owned(world.me):
        if b.id in guarded:
            continue
        dist = t.dist_to(b.pos)
        if any(dist.get(p, 99) <= EVICT_RADIUS for p, _ in t.enemy_warriors):
            continue
        ranked.append((front_rank(world, b, dist, t.others), t.key(b.pos), b))
    ranked.sort(key=lambda r: r[:2])
    return [Task("전선", "W", b.pos, FRONT_NEED, t.values[b.id] * weight) for *_, b in ranked[:FRONT_COUNT]]


def front_rank(world: World, b: Building, dist: dict[Pos, int], others: list[Building]) -> float:
    """우리 건물 `b`의 노출 순위(작을수록 전선). `dist`는 `b`에서 각 칸까지의 거리, `others`는 우리 것이 아닌 건물.
    = 가장 가까운 적·중립 건물까지 거리 + FRONT_MARGIN_WEIGHT × (적 본진 거리 − 우리 본진 거리).
    앞 항은 지금 맞닿은 경계, 뒤 항은 진영(상대 쪽으로 나가 있을수록 작다)."""
    far = world.map.width + world.map.height
    front = min((dist[o.pos] for o in others if o.pos in dist), default=far)
    bases = world.map.bases
    margin = dist.get(bases[world.enemy], far) - dist.get(bases[world.me], far)
    return front + FRONT_MARGIN_WEIGHT * margin


# ------------------------------------------------------------------ 깃발병


def assign_flags(
    flags: list[tuple[Pos, int]], tasks: list[Task], dist_to: Callable[[Pos], dict[Pos, int]],
) -> list[tuple[Pos, Task]]:
    """깃발병 한 명씩 (칸, 점령 과제) 짝. 효용 = 가치 / (거리 + 남은 점령 단계 + ETA_OFFSET)이 큰 짝부터
    탐욕적으로 고르고, 한 과제엔 한 명. 과제가 다 차면 남는 인원은 효용이 가장 높은 과제로 겹쳐 보낸다.
    닿을 수 없으면 제자리.
    """
    dists = {task.pos: dist_to(task.pos) for task in tasks}
    pool = [pos for pos, n in flags for _ in range(n)]
    free = list(tasks)
    plan: list[tuple[Pos, Task]] = []
    while pool:
        best: tuple[float, int, Task] | None = None
        for i, pos in enumerate(pool):
            for task in free or tasks:
                d = dists[task.pos].get(pos)
                if d is None:
                    continue
                u = task.value / (d + task.stages + ETA_OFFSET)
                if best is None or u > best[0]:
                    best = (u, i, task)
        if best is None:
            break
        _, i, task = best
        plan.append((pool.pop(i), task))
        if free:
            free.remove(task)
    return plan


class FlagMove:
    """깃발병 한 명의 칠판. FLAG_TREE가 `step`(다음 칸, None = 제자리)을 정한다."""

    def __init__(
        self, pos: Pos, goal: Pos, dist: dict[Pos, int], order: tuple[Pos, ...],
        safe: Callable[[Pos], bool], hold: bool,
    ) -> None:
        self.pos, self.goal, self.dist, self.safe, self.hold = pos, goal, dist, safe, hold
        self.here = dist.get(pos)
        neighbors = [(pos[0] + dx, pos[1] + dy) for dx, dy in order]
        self.neighbors = [n for n in neighbors if n in dist]
        # 목표 쪽으로 한 칸 줄이는 칸. 이미 목표 위(거리 0)면 없다
        self.closer = [n for n in self.neighbors if self.here and dist[n] == self.here - 1]
        self.step: Pos | None = None

    def enterable(self, n: Pos) -> bool:
        """`hold`(전투병이 아직 못 옴)면 목표 칸에는 들어가지 않고 한 칸 앞에서 기다린다."""
        return not (self.hold and n == self.goal)

    def go(self, n: Pos | None) -> bool:
        if n is None:
            return False
        self.step = n
        return True


def flag_step(
    pos: Pos,
    goal: Pos,
    dist: dict[Pos, int],
    order: tuple[Pos, ...],
    safe: Callable[[Pos], bool],
    hold: bool,
) -> Pos | None:
    """깃발병 한 명의 다음 칸 (None = 제자리). 판단은 FLAG_TREE:

    목표 쪽으로 한 칸 줄이는 칸 중 안전한 곳 → 없으면 지금 칸이 안전할 때 대기 → 아니면 안전한 이웃으로
    피한다 → 그것도 없으면 그냥 목표 쪽으로 간다. `hold`면 목표 칸에 들어가지 않고 앞에서 기다린다.
    """
    m = FlagMove(pos, goal, dist, order, safe, hold)
    FLAG_TREE.tick(m)
    return m.step


def capturing(plan: list[tuple[Pos, Task]], dist_to: Callable[[Pos], dict[Pos, int]]) -> list[Task]:
    """이번 턴 이동 뒤 깃발병이 올라가 있을 점령 과제 (= 이번 턴 점령 단계가 진행될 건물)."""
    found: dict[Pos, Task] = {}
    for pos, task in plan:
        if dist_to(task.pos).get(pos, 99) <= 1:
            found[task.pos] = task
    return list(found.values())


# ------------------------------------------------------------------ 전투병


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


def pick_jump(jumps: Counter[tuple[Pos, Pos]], key: Callable[[Pos], Pos]) -> tuple[Pos, Pos] | None:
    """순간이동은 턴당 1회: 인원이 가장 많은 (출발 역, 도착 역) 하나. 동점이면 정규화 좌표 순."""
    if not jumps:
        return None
    return min(jumps, key=lambda pair: (-min(jumps[pair], TELE_MAX_UNITS), key(pair[0]), key(pair[1])))


def spawn_site(sites: list[Pos], goal_dist: dict[Pos, int], threat: dict[Pos, int]) -> Pos:
    """생산할 칸. `sites[0]`은 본진, 나머지는 우리 병원. `threat`에서 적 전투병이 닿는 병원은 빼고(새 깃발병이 바로
    잡힌다. 전투병은 빈 위협 맵을 넘겨 빼지 않는다), 목표까지 가장 가까운 곳. 거리가 같으면 앞의 것(본진)."""
    usable = [s for i, s in enumerate(sites) if i == 0 or not threat.get(s, 0)]
    return min(usable, key=lambda s: goal_dist.get(s, 10**6))


def enemy_spawnable(world: World) -> list[tuple[Pos, int]]:
    """상대가 이번 턴 본진에서 새로 만들 수 있는 전투병 (생산한 유닛은 같은 턴에 바로 움직인다)."""
    enemy = world.enemy
    n = world.gold[enemy] // world.warrior_cost(enemy)
    return [(world.map.bases[enemy], n)] if n else []


def with_spawned(
    units: list[tuple[Pos, int]], base: Pos, count: int, key: Callable[[Pos], Pos],
) -> list[tuple[Pos, int]]:
    """이번 턴 본진에서 새로 만든 유닛을 더한 목록 (정규화 좌표 순서)."""
    merged = Counter(dict(units))
    if count:
        merged[base] += count
    return sorted(merged.items(), key=lambda item: key(item[0]))


# ------------------------------------------------------------------ 건물 가치·비용


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


# ------------------------------------------------------------------ 트리 조립
#
# 트리 전체를 글로 보려면 tree_text(). 노드 이름이 곧 보고서의 판단 조건 설명이다.


def phase_branch(name: str, condition: str | None, *recipe: Node) -> Node:
    """국면 가지: [조건(국면 유지 포함)] → [국면 기록] → [이번 턴 과제 구성]. 조건이 없으면 늘 성립(기본 국면)."""
    record = Act(f"국면 = {name}", lambda ctx: enter_phase(ctx, name))
    if condition is None:
        return Sequence(name, record, *recipe)
    test = Condition(condition, lambda ctx: ctx.active[name])
    return Sequence(name, Latch(name, test, HOLD_TURNS), record, *recipe)


def enable(name: str, unit: str, maker: Maker) -> Node:
    """과제 구성 잎: 이번 턴 `unit` 병종의 과제 목록에 `maker`가 만드는 과제를 넣는다."""
    return Act(name, lambda t: t.makers[unit].append(maker))


def capture(steal: float, danger: float) -> Node:
    return enable(f"점령 과제 (상대 건물 가치 ×{steal:g}, 적 전투병이 닿는 건물 ×{danger:g})",
                  "F", lambda t: capture_tasks(t, steal, danger))


def kill() -> Node:
    return enable("처치 과제: 적 깃발병 (건물 위면 방어·저지·깃발 뽑기)", "W", kill_tasks)


def escort() -> Node:
    return enable("호위 과제: 점령 중인 우리 깃발병", "W", escort_tasks)


def guard(weight: float) -> Node:
    return enable(f"지키기 과제: 적 깃발병이 {GUARD_RADIUS}칸 안에 온 우리 건물 (가치 ×{weight:g})",
                  "W", lambda t: guard_tasks(t, weight))


def evict() -> Node:
    return enable(f"몰아내기 과제: 적 전투병이 {EVICT_RADIUS}칸 안에 온 우리 핵심 건물 ({'·'.join(sorted(EVICT_KINDS))})",
                  "W", evict_tasks)


def frontline(weight: float) -> Node:
    return enable(f"전선 과제: 노출 순위가 앞선 우리 건물 {FRONT_COUNT}곳에 전투병 {FRONT_NEED}명 (가치 ×{weight:g})",
                  "W", lambda t: frontline_tasks(t, weight))


def warriors(extra: int) -> Node:
    return Act(f"전투병 목표 인원 = 적 전투병 + {extra}", lambda t: setattr(t, "extra_warriors", extra))


PHASE_TREE = Selector(
    "국면 선택 → 이번 턴 과제 구성 (위에서부터 처음 성립하는 가지)",
    phase_branch(
        "THREAT", f"적 깃발병이 {GUARD_RADIUS}칸 안에 온 우리 건물의 추정 점수 합 ≥ {THREAT_PRESSURE:g}",
        capture(steal=1.0, danger=0.5), kill(), escort(), guard(2.0), evict(), frontline(1.0), warriors(2),
    ),
    phase_branch(
        "HOLD", f"{LATE_TURN}턴 이후이고 추정 점수가 앞섬",
        capture(steal=1.0, danger=0.3), kill(), escort(), guard(1.5), evict(), frontline(1.5), warriors(2),
    ),
    phase_branch(
        "ATTACK", f"우리 전투병 ≥ 적 전투병 + {ATTACK_MARGIN}이고 상대가 건물을 가짐",
        capture(steal=1.5, danger=0.5), kill(), escort(), guard(0.5), evict(), frontline(0.5), warriors(1),
    ),
    phase_branch(
        "EXPAND", None,
        capture(steal=1.0, danger=DANGER_DISCOUNT), kill(), escort(), guard(1.0), evict(), frontline(1.0), warriors(1),
    ),
)

TURN_TREE = Sequence(
    "한 턴",
    Act("상황 읽기 (위협 맵·건물 가치·국면 조건)", read_situation),
    PHASE_TREE,
    Sequence(
        "깃발병 1차: 이번 턴 점령할 건물",
        Act("지금 있는 깃발병을 점령 과제에 배정", plan_flags),
        Act("점령 비용 예약", reserve_capture_cost),
    ),
    Act("전투병 과제 목록", plan_warrior_tasks),
    Act("생산 (깃발병 최소 인원 → 전투병 목표 인원 → 점령 과제 수만큼 깃발병 → 남으면 전투병, 병원 위치 — 적 전투병이 닿는 병원은 깃발병만 피함)", produce),
    Sequence(
        "전투병",
        Act("과제 배정 (새로 만든 전투병 포함)", plan_warriors),
        Act("이동 (역 순간이동)", move_warriors),
    ),
    Sequence(
        "깃발병 2차",
        Act("전투병이 깃발을 뽑아 줄 건물을 점령 과제에 넣고 재배정", replan_flags),
        Act("한 명씩 깃발병 트리", move_flags),
    ),
    Act("동시 점령 우선순위", set_priority),
)

FLAG_TREE = Selector(
    "깃발병 한 칸",
    Sequence("목표에 닿을 수 없음", Condition("목표까지 경로 없음", lambda m: m.here is None), Act("제자리", lambda m: None)),
    Act("목표 쪽 안전한 칸으로", lambda m: m.go(next(
        (n for n in m.closer if m.safe(n) and m.enterable(n)), None))),
    Sequence("대기", Condition("지금 칸이 안전", lambda m: m.safe(m.pos)), Act("제자리", lambda m: None)),
    Act("가장 목표에 가까운 안전한 이웃으로 피하기", lambda m: m.go(min(
        (n for n in m.neighbors if m.safe(n)), key=lambda n: m.dist[n], default=None))),
    Act("위험해도 목표 쪽으로", lambda m: m.go(
        m.closer[0] if m.closer and m.enterable(m.closer[0]) else None)),
    Act("제자리", lambda m: None),
)


def tree_text() -> str:
    """판단 트리 전체를 글로 (보고서·문서용): python -c "from agent.strategy import tree_text; print(tree_text())" """
    return "\n".join(TURN_TREE.lines() + [""] + FLAG_TREE.lines())
