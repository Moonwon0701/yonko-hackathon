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
    w = world([building(0, (7, 7), "PLAZA")], units={("Y", "F", (7, 7)): 1}, gold=5)
    assert Spawn("W", 1) in strategy.decide(w)


def test_priority_orders_simultaneous_captures_by_value():
    w = world([building(0, (3, 3), "LIBRARY", score=1), building(1, (5, 5), "WATCH", score=4)],
              units={("Y", "F", (3, 3)): 1, ("Y", "F", (5, 5)): 1}, gold=0)
    assert Priority(((5, 5), (3, 3))) in strategy.decide(w)
