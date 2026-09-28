"""실험 변형 (현진): 과제 없는 전투병(w_idle)의 공격 경로가 반드시 예비대 지점(집결지)을 거치게 한다.
기본 전략은 agent/strategy.py 그대로.

main의 동작 — 과제 없는 전투병은 공통 목표(t.goals: 적 깃발병 칸, 없으면 우리 것이 아닌 건물 칸)로 곧장 간다.
이 변형 — 공통 목표는 main과 같지만, 아직 집결지를 거치지 않은 전투병은 먼저 집결지로 간다.
- 집결지 = 우리 건물들까지의 최대 걸음 거리가 가장 작은 칸 (격자 위의 1-center). 우리 역도 후보로 넣고,
  역 후보는 역끼리 순간이동(비용 1)을 포함한 거리로 잰다. 동점이면 칸 → 역, 그다음 정규화 좌표 순
- 집결지에 선 전투병은 "거쳤음"이 되어 그 턴부터 공통 목표로 간다. 우리 건물이 없으면 모두 거친 것으로 본다
- 단 집결지를 거치는 추가 거리가 DETOUR_MAX보다 크면 거친 것으로 보고 곧장 간다 (조금만 돌아가면 될 때만 경유)
- 유닛은 칸별 인원으로만 보이므로, "거친 인원"은 칸별 인원(_passed)으로 턴을 넘어 기억한다. 이번 턴 이동 뒤
  칸으로 옮겨 적고, 다음 턴 실제 인원보다 많으면 줄인다(전투 손실·합류를 근사)
- 과제를 받은 전투병(처치·호위·지키기·몰아내기·전선·급습)은 main처럼 곧장 간다

트리는 strategy.TURN_TREE에서 "전투병" 가지의 잎 두 개만 바꿔 끼운다. 실행: experiments/rally/main.py
"""

from __future__ import annotations

from collections import Counter

from agent.algorithms import step_along
from agent.bt import Act, Node, Selector, Sequence
from agent.strategy import TURN_TREE, Turn, move_warriors, plan_warriors
from agent.world import Action, Pos, Tele, World

# 집결지를 거치는 추가 거리(칸 → 집결지 → 목표 − 칸 → 목표)가 이보다 크면 집결지를 건너뛰고 곧장 간다.
# 늘 거치게 하면 main 상대 50경기 10승 40패였다(docs/llm-log/2026-09-28-hyunjin-rally-reserve.md)
DETOUR_MAX = 2  # main 상대 50경기씩: 0 → 36%, 2 → 48%, 4 → 32%, 6 → 24%
_passed: Counter[Pos] = Counter()  # 칸 → 집결지를 거친 과제 없는 전투병 수 (이번 턴 시작 기준). 한 프로세스 = 한 경기


def rally_point(t: Turn) -> Pos | None:
    """우리 건물들까지의 최대 거리가 가장 작은 칸. 우리 건물이 없으면 None."""
    world = t.world
    homes = sorted((b.pos for b in world.owned(world.me)), key=t.key)
    if not homes:
        return None
    walks = [t.dist_to(h) for h in homes]
    best: tuple[int, int, Pos, Pos] | None = None
    for cell in walks[0]:
        if all(cell in w for w in walks):
            cand = (max(w[cell] for w in walks), 0, t.key(cell), cell)
            best = cand if best is None or cand < best else best
    if t.gates:
        teles = [t.tele_to(h) for h in homes]
        for gate in t.gates:
            if all(gate in d for d in teles):
                cand = (max(d[gate] for d in teles), 1, t.key(gate), gate)
                best = cand if best is None or cand < best else best
    return best[3] if best else None


def plan_warriors_via_rally(t: Turn) -> None:
    """main의 과제 배정 뒤, 과제 없는 전투병 중 집결지를 아직 안 거친 인원은 집결지로 보낸다."""
    plan_warriors(t)
    t.rally = rally = rally_point(t)
    idle = Counter(t.w_idle)
    t.released = Counter()  # 칸 → 이번 턴 공통 목표로 가는(거친) 인원
    if rally is None:
        t.released = idle
        return
    to_rally = []
    far = t.goal_dist.get(rally)
    for pos, n in sorted(idle.items(), key=lambda item: t.key(item[0])):
        direct = t.goal_dist.get(pos)
        detour = None if far is None or direct is None else t.dist_to(rally).get(pos, 10**6) + far - direct
        if pos == rally or detour is None or detour > DETOUR_MAX:
            done = n  # 집결지 위이거나, 돌아가는 거리가 한도를 넘으면 거친 것으로 보고 곧장 간다
        else:
            done = min(n, _passed[pos])
        t.released[pos] = done
        to_rally += [pos] * (n - done)
    t.w_plan = t.w_plan + [(pos, rally) for pos in to_rally]
    t.w_idle = [pos for pos, n in t.released.items() for _ in range(n)]


def move_and_remember(t: Turn) -> None:
    """main의 이동 뒤, 거친 인원이 이번 턴 도착할 칸을 적어 둔다(순간이동이 있으면 그 인원부터 태운 것으로 본다)."""
    move_warriors(t)
    jumps = {a.src: a for a in t.actions if isinstance(a, Tele) and a.kind == "W"}
    nxt: Counter[Pos] = Counter()
    for pos, n in t.released.items():
        jump = jumps.get(pos)
        flown = min(n, jump.count) if jump else 0
        if flown:
            nxt[jump.dst] += flown
        nxt[step_along(pos, t.goal_dist, t.order) or pos] += n - flown
    # 다음 턴에 실제 인원보다 많이 적혀 있으면 plan_warriors_via_rally의 min(n, _passed[pos])이 잘라 준다
    _passed.clear()
    _passed.update(nxt)


def swap(node: Node, table: dict) -> Node:
    """트리를 복사하며 행동 잎의 함수가 `table`에 있으면 그 잎으로 바꾼다."""
    run = getattr(node, "run", None)
    if run in table:
        return table[run]
    if type(node) in (Sequence, Selector):
        return type(node)(node.name, *(swap(child, table) for child in node.children))
    return node


RALLY_TURN_TREE = swap(TURN_TREE, {
    plan_warriors: Act("과제 배정 (과제 없는 전투병은 집결지를 거친 뒤 공통 목표로)", plan_warriors_via_rally),
    move_warriors: Act("이동 (역 순간이동) + 집결지를 거친 인원 기억", move_and_remember),
})


def decide(world: World) -> list[Action]:
    turn = Turn(world)
    RALLY_TURN_TREE.tick(turn)
    return turn.actions
