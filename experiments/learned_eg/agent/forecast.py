"""한 턴 앞 예측에 쓰는 규칙 계산: 한 팀의 생산·이동 명령을 적용한 뒤의 유닛 위치.

strategy.py가 상대 시점으로 자기 판단을 한 번 더 돌려 "상대가 이번 턴 둘 수"를 얻고(상대 모델 = 우리 봇), 여기서 그
명령을 적용해 상대 유닛이 이번 턴 이동 뒤 어디에 설지 구한다. 규칙 원문 5장(생산 → 이동) 그대로이고 판단은 없다.
"""

from __future__ import annotations

from collections import Counter

from agent.world import TELE_MAX_UNITS, UNIT_COST, Action, Move, Move2, Pos, Spawn, Tele, World


def after_moves(world: World, team: str, actions: list[Action]) -> Counter[tuple[str, Pos]]:
    """`team`이 `actions`를 두면 이동 단계 뒤 (병종, 칸) → 인원. 생산은 자원이 되는 만큼, 이동은 있던 인원만큼."""
    gold = world.gold[team]
    cost = dict(UNIT_COST, W=world.warrior_cost(team))
    hospitals = {b.pos for b in world.owned(team, "HOSPITAL")}
    ready: Counter[tuple[str, Pos]] = Counter()
    for (t, kind, pos), n in world.units.items():
        if t == team:
            ready[(kind, pos)] += n
    for a in actions:
        if isinstance(a, Spawn):
            if a.at is not None and a.at not in hospitals:
                continue
            made = min(a.count, gold // cost[a.kind])
            gold -= made * cost[a.kind]
            ready[(a.kind, a.at or world.map.bases[team])] += made
    arrived: Counter[tuple[str, Pos]] = Counter()
    stations = {b.pos for b in world.owned(team, "STATION")}
    tele_used = False
    for a in actions:
        if isinstance(a, Move):
            k = min(a.count, ready[(a.kind, a.src)])
            ready[(a.kind, a.src)] -= k
            arrived[(a.kind, a.dst)] += k
        elif isinstance(a, Move2):
            k = min(a.count, ready[("S", a.src)])
            ready[("S", a.src)] -= k
            arrived[("S", a.dst)] += k
        elif isinstance(a, Tele):
            if tele_used or len(stations) < 2 or a.src not in stations or a.dst not in stations or a.src == a.dst:
                continue
            k = min(a.count, TELE_MAX_UNITS, ready[(a.kind, a.src)])
            if k:
                tele_used = True
                ready[(a.kind, a.src)] -= k
                arrived[(a.kind, a.dst)] += k
    out = ready + arrived
    return +out
