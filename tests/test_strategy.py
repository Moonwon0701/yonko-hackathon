"""M1 전략의 부품(거리표, 점수 추론, 목표 분산, 점령 비용 예약) 단위 테스트."""

from agent import strategy
from agent.algorithms import distance_map, step_along
from agent.world import Building, GameMap, Move, Priority, Spawn, World

EMPTY = GameMap(15, 15, tuple("." * 15 for _ in range(15)), {"Y": (0, 7), "K": (14, 7)})


def building(bid, pos, kind="HALL", owner=None, score=None):
    return Building(bid, pos, kind, owner, False, score)


def world(buildings, units=None, gold=10, turn=5):
    return World(EMPTY, "Y", turn, {"Y": gold, "K": 10}, units or {}, {b.id: b for b in buildings})


def test_distance_map_goes_around_walls():
    rows = [list("." * 15) for _ in range(15)]
    rows[0][1] = rows[1][1] = "#"
    game_map = GameMap(15, 15, tuple("".join(r) for r in rows), {})
    dist = distance_map([(0, 0)], game_map.passable)
    assert dist[(2, 0)] == 6  # (0,0)→(0,2)→(2,2)→(2,0)
    assert (1, 0) not in dist
    assert step_along((2, 0), dist) == (2, 1)
    assert step_along((0, 0), dist) is None


def test_known_score_uses_mirror_twin_and_plaza():
    w = world([building(0, (2, 3), score=2), building(1, (12, 11)), building(2, (7, 7), "PLAZA"),
               building(3, (4, 4))])
    assert w.known_score(w.buildings[1]) == 2
    assert w.known_score(w.buildings[2]) == 3
    assert w.known_score(w.buildings[3]) is None


def test_flags_split_across_buildings():
    w = world([building(0, (3, 5)), building(1, (3, 9))], units={("Y", "F", (1, 7)): 2}, gold=0)
    moves = [a for a in strategy.decide(w) if isinstance(a, Move) and a.kind == "F"]
    assert sorted((m.dst, m.count) for m in moves) == [((1, 6), 1), ((1, 8), 1)]


def test_reserves_capture_cost_after_income():
    # 깃발병이 중립 광장 위에 있다: 비용 4는 이번 턴 수입(10)으로 충분하므로 자원 5를 모두 생산에 쓴다.
    # (깃발병이 MIN_FLAGS보다 적으므로 깃발병 1명)
    w = world([building(0, (7, 7), "PLAZA")], units={("Y", "F", (7, 7)): 1}, gold=5)
    assert Spawn("F", 1) in strategy.decide(w)


def test_flags_come_before_warriors_when_below_minimum():
    # 적 전투병이 훨씬 많아 전투병을 다 채울 수 없어도, 깃발병이 없으면 먼저 만든다 (9/27 리더보드 패배 경기)
    w = world([building(0, (3, 7)), building(1, (5, 3))],
              units={("Y", "W", (1, 7)): 5, ("K", "W", (12, 7)): 20}, gold=12)
    spawns = [a for a in strategy.decide(w) if isinstance(a, Spawn)]
    assert spawns == [Spawn("F", 2)]  # 자원 12 = 깃발병 2명(10) + 남은 2 (전투병 값 3에 모자람)


def test_more_flags_first_when_enemy_owns_more_buildings():
    # 상대가 건물을 더 가지면 깃발병 최소 인원이 하나 늘어난다 (9/28 리더보드 패배 경기)
    w = world([building(0, (3, 7), owner="K"), building(1, (5, 3), owner="K")],
              units={("Y", "W", (1, 7)): 5, ("K", "W", (12, 7)): 20}, gold=17)
    spawns = [a for a in strategy.decide(w) if isinstance(a, Spawn)]
    assert spawns == [Spawn("F", 3)]


def test_priority_orders_simultaneous_captures_by_value():
    w = world([building(0, (3, 3), "LIBRARY", score=1), building(1, (5, 5), "WATCH", score=4)],
              units={("Y", "F", (3, 3)): 1, ("Y", "F", (5, 5)): 1}, gold=0)
    assert Priority(((5, 5), (3, 3))) in strategy.decide(w)


# ------------------------------------------------------------------ M2


def test_threat_map_adds_up_stacks_that_can_meet():
    from agent.algorithms import threat_map
    threat = threat_map([((3, 3), 2), ((5, 3), 1)], EMPTY.passable)
    assert threat[(4, 3)] == 3  # 두 무리 모두 한 칸이면 닿는다
    assert threat[(3, 3)] == 2 and threat[(3, 4)] == 2
    assert (7, 3) not in threat


def test_flag_waits_instead_of_walking_into_enemy_warrior():
    w = world([building(0, (5, 5))], units={("Y", "F", (4, 5)): 1, ("K", "W", (6, 5)): 1}, gold=0)
    assert not [a for a in strategy.decide(w) if isinstance(a, Move) and a.kind == "F"]


def test_flag_pull_sends_warrior_and_flag_together():
    w = world([building(0, (5, 5), owner="K")],
              units={("Y", "F", (4, 5)): 1, ("Y", "W", (5, 6)): 1, ("K", "F", (5, 5)): 1}, gold=0)
    actions = strategy.decide(w)
    assert Move((5, 6), "W", 1, (5, 5)) in actions
    assert Move((4, 5), "F", 1, (5, 5)) in actions


def test_flag_holds_until_warrior_arrives_for_pull():
    w = world([building(0, (5, 5), owner="K")],
              units={("Y", "F", (4, 5)): 1, ("Y", "W", (5, 8)): 1, ("K", "F", (5, 5)): 1}, gold=0)
    actions = strategy.decide(w)
    assert Move((5, 8), "W", 1, (5, 7)) in actions
    assert not [a for a in actions if isinstance(a, Move) and a.kind == "F"]


def test_self_play_is_mirror_symmetric():
    """같은 봇끼리 두면 매 턴 두 진영의 명령이 점대칭이어야 한다 (동점 처리가 진영에 따라 다르면 깨진다)."""
    from sim import bots, mapgen, match

    def mirror(line):
        t = line.split()
        flip = {"U": "D", "D": "U", "L": "R", "R": "L"}
        if t[0] == "MOVE":
            return f"MOVE {14 - int(t[1])} {14 - int(t[2])} {t[3]} {t[4]} {flip[t[5]]}"
        if t[0] == "TELE":
            return f"TELE {14 - int(t[1])} {14 - int(t[2])} {t[3]} {t[4]} {14 - int(t[5])} {14 - int(t[6])}"
        if t[0] == "SPAWN" and len(t) == 5:  # 병원 생산
            return f"SPAWN {t[1]} {t[2]} {14 - int(t[3])} {14 - int(t[4])}"
        if t[0] == "PRIORITY":
            xy = [14 - int(v) for v in t[1:]]
            return " ".join(["PRIORITY", *map(str, xy)])
        return line

    me = bots.resolve(".")
    for seed in (0, 2, 25):  # 동점 처리 버그로 대칭이 깨졌던 맵들
        rep = match.play(mapgen.generate(seed), {"Y": me, "K": me}, time_scale=None)
        for entry in rep["turns"]:
            y = sorted(c["line"] for c in entry["commands"].get("Y", []))
            k = sorted(mirror(c["line"]) for c in entry["commands"].get("K", []))
            assert y == k, (seed, entry["turn"])


# ------------------------------------------------------------------ M3


def test_selector_takes_most_urgent_phase_immediately():
    active = {"THREAT": True, "HOLD": True, "ATTACK": True, "EXPAND": True}
    assert strategy.select_phase(active, "EXPAND", 0) == ("THREAT", 0)


def test_selector_steps_down_only_after_hold_turns():
    calm_down = {"THREAT": False, "HOLD": False, "ATTACK": False, "EXPAND": True}
    phase, calm = "THREAT", 0
    seen = []
    for _ in range(strategy.HOLD_TURNS):
        phase, calm = strategy.select_phase(calm_down, phase, calm)
        seen.append(phase)
    assert seen == ["THREAT"] * (strategy.HOLD_TURNS - 1) + ["EXPAND"]


def test_selector_resets_calm_when_condition_returns():
    threat = {"THREAT": True, "HOLD": False, "ATTACK": False, "EXPAND": True}
    calm_down = {**threat, "THREAT": False}
    phase, calm = strategy.select_phase(calm_down, "THREAT", 0)
    phase, calm = strategy.select_phase(threat, phase, calm)
    assert (phase, calm) == ("THREAT", 0)


def test_warrior_guards_our_building_when_enemy_flag_approaches():
    # 전투병이 우리 건물 위에 있고 적 깃발병이 3칸 밖에서 다가온다: 쫓아가지 않고 건물을 지킨다.
    w = world([building(0, (5, 5), owner="Y", score=2)],
              units={("Y", "W", (5, 5)): 1, ("K", "F", (8, 5)): 1}, gold=0)
    actions = strategy.decide(w)
    assert strategy.note() == "THREAT"
    assert not [a for a in actions if isinstance(a, Move) and a.kind == "W"]


def test_frontline_warrior_waits_on_most_exposed_building(monkeypatch):
    # 적이 아직 오지 않아도 앞쪽 건물(6,7)을 지킨다: 그 위의 전투병은 중립 건물(9,7) 쪽으로 가지 않고 남고,
    # 뒤쪽 건물(1,7) 위의 전투병은 과제가 없어 앞으로 나간다. (전선 과제가 없으면 둘 다 (9,7) 쪽으로 간다)
    w = world([building(0, (1, 7), owner="Y", score=1), building(1, (6, 7), owner="Y", score=1),
               building(2, (9, 7))],
              units={("Y", "W", (1, 7)): 1, ("Y", "W", (6, 7)): 1, ("K", "W", (14, 0)): 1}, gold=0)
    monkeypatch.setattr(strategy, "FRONT_COUNT", 1)
    t = strategy.Turn(w)
    strategy.read_situation(t)
    ranks = {b.pos: strategy.front_rank(w, b, t.dist_to(b.pos), t.others) for b in w.owned("Y")}
    assert ranks[(6, 7)] < ranks[(1, 7)]
    moves = [a for a in strategy.decide(w) if isinstance(a, Move) and a.kind == "W"]
    assert moves == [Move((1, 7), "W", 1, (2, 7))]


def test_decide_stays_fast_with_huge_army():
    """전투병이 수백 명이어도 계산이 유닛 수에 비례해 늘지 않아야 한다 (서버는 로컬보다 약 12배 느리다).

    적 깃발병이 멀리 한 명뿐이라 과제 없는 전투병 수백 명이 모두 그쪽으로 간다. 전투병마다 BFS를 하던
    이전 코드는 여기서 로컬 약 17 ms, 지금은 1 ms 미만.
    """
    import time
    buildings = [building(i, (1 + i % 4, 1 + 3 * (i // 4)), owner="Y", score=1) for i in range(16)]
    buildings.append(building(16, (14, 14), owner="K", score=1))
    taken = {b.pos for b in buildings}
    units = {("Y", "W", (x, y)): 4 for x in range(8) for y in range(0, 15, 2) if (x, y) not in taken}  # 224명
    units[("K", "F", (14, 13))] = 1
    w = world(buildings, units=units, gold=40, turn=80)
    strategy.decide(w)  # 거리표 캐시 채우기 (실제 경기에서는 앞 턴들이 채운다)
    start = time.perf_counter()
    strategy.decide(w)
    assert (time.perf_counter() - start) * 1000 < 5


# ------------------------------------------------------------------ M4


def test_spawns_at_hospital_closer_to_targets():
    w = world([building(0, (10, 7), "HOSPITAL", owner="Y", score=1), building(1, (12, 7), "LIBRARY")], gold=10)
    spawns = [a for a in strategy.decide(w) if isinstance(a, Spawn)]
    assert spawns and all(a.at == (10, 7) for a in spawns)


def test_flags_skip_hospital_that_enemy_warriors_can_reach_but_warriors_do_not():
    # 깃발병은 적 전투병이 닿는 병원을 피해 본진에서, 전투병은 그 병원에서 만든다(1:1 상쇄라 손해가 없고 병원을 지킨다)
    w = world([building(0, (10, 7), "HOSPITAL", owner="Y", score=1), building(1, (12, 7), "LIBRARY")],
              units={("K", "W", (10, 8)): 2}, gold=19)
    spawns = {a.kind: a.at for a in strategy.decide(w) if isinstance(a, Spawn)}
    assert spawns == {"F": None, "W": (10, 7)}


def test_warriors_go_to_key_building_when_enemy_warriors_come_near():
    # 적 깃발병 없이 적 전투병만 우리 학생회관 2칸 안에 왔다: 전투병이 학생회관으로 간다 (9/28 리더보드 패배 경기)
    w = world([building(0, (5, 5), owner="Y", score=1)],
              units={("Y", "W", (5, 8)): 3, ("K", "W", (5, 3)): 2}, gold=0)
    assert Move((5, 8), "W", 1, (5, 7)) in strategy.decide(w)


def test_distance_map_links_stations_with_cost_one():
    gates = ((1, 1), (13, 13))
    dist = distance_map([(13, 12)], EMPTY.passable, gates)
    assert dist[(13, 13)] == 1 and dist[(1, 1)] == 2  # 역에서 역으로 한 턴
    assert dist[(1, 0)] == 3
    assert distance_map([(13, 12)], EMPTY.passable) == distance_map([(13, 12)], EMPTY.passable, ())
    assert step_along((1, 1), dist, portals=gates) == (13, 13)  # 붙어 있지 않은 칸 = 순간이동
    assert step_along((1, 1), dist) is None or step_along((1, 1), dist) != (13, 13)


def test_warriors_teleport_to_far_front_at_most_five():
    from agent.world import Tele
    w = world([building(0, (1, 1), "STATION", owner="Y", score=1),
               building(1, (13, 13), "STATION", owner="Y", score=1)],
              units={("Y", "W", (1, 1)): 7, ("K", "F", (13, 11)): 1}, gold=0)
    actions = strategy.decide(w)
    assert Tele((1, 1), "W", 5, (13, 13)) in actions
    # 나머지 2명은 걸으면 22턴, 다음 턴 순간이동하면 4턴이라 역에서 기다린다
    assert not [a for a in actions if isinstance(a, Move) and a.src == (1, 1)]


def test_warriors_beyond_teleport_queue_walk_and_do_not_bounce(monkeypatch):
    # 걸으면 8칸, 순간이동 경로는 5턴(역 → 역 1 + 걷기 4) → 3턴 이득. 턴당 5명이라 대기열이 15명을 넘으면
    # 기다리는 것보다 걷는 게 빠르다. 역 옆 칸의 인원은 역으로 들어오지 않는다(들어왔다 물러나기를 반복했다).
    from agent.world import Tele
    monkeypatch.setattr(strategy, "FRONT_COUNT", 0)  # 역이 전선 건물이라 한 명이 남는다. 여기서는 이동만 본다
    w = world([building(0, (7, 1), "STATION", owner="Y", score=1),
               building(1, (7, 13), "STATION", owner="Y", score=1)],
              units={("Y", "W", (7, 1)): 30, ("Y", "W", (6, 1)): 10, ("K", "F", (7, 9)): 1}, gold=0)
    actions = strategy.decide(w)
    assert Tele((7, 1), "W", 5, (7, 13)) in actions
    moves = [a for a in actions if isinstance(a, Move) and a.kind == "W"]
    assert sum(m.count for m in moves if m.src == (7, 1)) == 15  # 10명은 역에서 기다리고 15명은 걷는다
    assert all(m.dst == (7, 2) for m in moves if m.src == (7, 1))
    assert not [m for m in moves if m.src == (6, 1) and m.dst == (7, 1)]
