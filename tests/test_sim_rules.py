"""시뮬레이터 엔진이 규칙서(docs/rules-original.md B장)대로 동작하는지 확인한다.

각 테스트 이름 옆 주석의 "N장"은 규칙서 장 번호다. 규칙서로 답이 정해지지 않은 부분(엔진의
ASSUMPTIONS)을 확인하는 테스트는 이름에 `assumed`를 붙였다. 서버 동작이 다르면 그 테스트와
엔진을 같이 고친다.
"""

import importlib.util
from collections import Counter, deque
from pathlib import Path

import pytest

from sim import engine, mapgen, rules
from sim.engine import Game, parse_command
from sim.mapgen import BuildingSpec, MapSpec, mirror

ROOT = Path(__file__).resolve().parent.parent
Y_BASE, K_BASE = (0, 0), (14, 14)


def make_game(buildings=(), obstacles=(), anchor=False) -> Game:
    """빈 15×15 맵에 건물·장애물만 놓은 시험용 게임. 대칭일 필요는 없다.

    anchor=True면 (14, 0)에 K 소유 4점 건물을 마지막 id로 둔다. 건물이 적은 시험 맵에서 첫
    점령만으로 즉시 승리가 나 경기가 끝나 버리는 것을 막는다.
    """
    buildings = list(buildings) + ([((14, 0), "DEPOT", 4)] if anchor else [])
    grid = [["."] * 15 for _ in range(15)]
    for x, y in obstacles:
        grid[y][x] = "#"
    specs = []
    for i, (pos, kind, score) in enumerate(buildings):
        grid[pos[1]][pos[0]] = "B"
        specs.append(BuildingSpec(i, pos, kind, score))
    for x, y in (Y_BASE, K_BASE):
        grid[y][x] = "H"
    rows = tuple("".join(r) for r in grid)
    g = Game(MapSpec(rows, tuple(specs), {"Y": Y_BASE, "K": K_BASE}))
    if anchor:
        g.owner[len(specs) - 1] = "K"
    return g


def step(g: Game, Y=(), K=()):
    return g.step({"Y": list(Y), "K": list(K)})


def put(g: Game, team, kind, pos, n):
    g.units[(team, kind, pos)] = n


def statuses(log, team="Y"):
    return [c.status for c in log.commands[team]]


def bline(g: Game, team, bid):
    """turn_text에서 건물 한 줄: (소유, 단계, 점수)."""
    for line in g.turn_text(team).splitlines():
        tok = line.split()
        if len(tok) == 7 and tok[0] == str(bid):
            return tok[4], int(tok[5]), int(tok[6])
    raise AssertionError(bid)


# ------------------------------------------------------------------ 수치


def test_constants_match_official_balance():
    spec = importlib.util.spec_from_file_location("gen", ROOT / "starter" / "_generated.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    B = gen.BALANCE
    assert B["grid"] == {"width": rules.SIZE, "height": rules.SIZE}
    assert B["total_turns"] == rules.TOTAL_TURNS
    assert B["first_turn_timeout_ms"] == rules.FIRST_TURN_MS
    assert B["min_base_distance"] == rules.MIN_BASE_DISTANCE
    assert {k: tuple(v) for k, v in B["regions"].items()} == rules.REGIONS
    for kind in rules.KINDS:
        assert B["units"][kind]["cost"] == rules.UNIT_COST[kind]
        assert B["tiebreak_values"][kind] == rules.UNIT_VALUE[kind]
    assert B["units"]["S"]["vision"] == rules.SCOUT_RANGE
    assert B["resource"] == {"base_income": rules.BASE_INCOME, "hall_bonus": rules.HALL_BONUS,
                             "resource_cap": rules.RESOURCE_CAP,
                             "start_resource": rules.START_RESOURCE}
    assert B["capture"] == {"capture_cost": rules.CAPTURE_COST,
                            "plaza_multiplier": rules.PLAZA_MULTIPLIER,
                            "min_capture_cost": rules.MIN_CAPTURE_COST}
    b = B["buildings"]
    assert (b["plaza_score"], b["library_discount"], b["eng_discount_per"], b["eng_cost_floor"],
            b["depot_bonus"], b["watch_reveal_range"], b["scout_reveal_range"]) == (
        rules.PLAZA_SCORE, rules.LIBRARY_DISCOUNT, rules.ENG_DISCOUNT, rules.ENG_COST_FLOOR,
        rules.DEPOT_BONUS, rules.WATCH_RANGE, rules.SCOUT_RANGE)
    assert b["library_stacking"] is False
    assert B["tele"] == {"max_units": rules.TELE_MAX_UNITS,
                         "min_stations": rules.TELE_MIN_STATIONS, "per_turn": 1}
    m = B["mapgen"]
    assert tuple(m["center"]) == rules.CENTER
    assert m["obstacle_pairs"] == rules.OBSTACLE_PAIRS
    assert m["max_place_attempts"] == rules.MAX_PLACE_ATTEMPTS
    assert tuple(m["sinchon_building_score"]) == rules.SIDE_SCORE
    assert tuple(m["center_building_score"]) == rules.CENTER_SCORE
    assert m["central_y_margin"] == rules.CENTRAL_Y_MARGIN


# ------------------------------------------------------------------ 1장 맵


@pytest.mark.parametrize("seed", range(300))
def test_generated_map_follows_chapter_1(seed):
    m = mapgen.generate(seed)
    assert len(m.rows) == 15 and all(len(r) == 15 for r in m.rows)
    for y in range(15):
        for x in range(15):
            mx, my = mirror((x, y))
            assert (m.rows[y][x] == "#") == (m.rows[my][mx] == "#")
    assert sum(r.count("#") for r in m.rows) == 2 * rules.OBSTACLE_PAIRS
    assert m.bases["K"] == mirror(m.bases["Y"])
    by, bk = m.bases["Y"], m.bases["K"]
    assert abs(by[0] - bk[0]) + abs(by[1] - bk[1]) >= rules.MIN_BASE_DISTANCE
    assert m.rows[by[1]][by[0]] == "H" and m.rows[bk[1]][bk[0]] == "H"

    assert len(m.buildings) == 17
    assert [b.id for b in m.buildings] == list(range(17))
    kinds = Counter(b.kind for b in m.buildings)
    assert kinds == {"PLAZA": 1, "STATION": 4, "HALL": 2, "LIBRARY": 2, "ENG": 2,
                     "HOSPITAL": 2, "WATCH": 2, "DEPOT": 2}
    at = {b.pos: b for b in m.buildings}
    assert at[(7, 7)].kind == "PLAZA" and at[(7, 7)].score == 3
    for b in m.buildings:
        assert m.rows[b.pos[1]][b.pos[0]] == "B"
        twin = at[mirror(b.pos)]
        assert (twin.kind, twin.score) == (b.kind, b.score)  # 대칭 짝은 같은 점수
        x, y = b.pos
        if b.kind == "PLAZA":
            continue
        if 5 <= x <= 9:  # 중앙
            assert b.kind in rules.CENTER_KINDS and 2 <= y <= 12 and 2 <= b.score <= 4
        else:
            assert b.kind in rules.SIDE_KINDS and 1 <= b.score <= 2
    # 신촌 쪽 5종은 Y 본진 쪽(x 0~4)에 하나씩
    assert sorted(b.kind for b in m.buildings if b.pos[0] <= 4) == sorted(rules.SIDE_KINDS)
    assert m.total_score % 2 == 1

    # 모든 건물과 본진이 서로 도달 가능
    start = by
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in rules.DIRS.values():
            n = (x + dx, y + dy)
            if m.passable(n) and n not in seen:
                seen.add(n)
                queue.append(n)
    assert all(b.pos in seen for b in m.buildings) and bk in seen


def test_same_seed_same_map():
    assert mapgen.generate(7) == mapgen.generate(7)
    assert mapgen.generate(7).rows != mapgen.generate(8).rows


def test_map_from_server_init_block():
    g = Game(mapgen.generate(5))
    m = mapgen.from_init(g.init_text("Y"), seed=1)
    assert m.rows == g.spec.rows and m.bases == g.spec.bases
    assert [(b.id, b.pos, b.kind) for b in m.buildings] == \
           [(b.id, b.pos, b.kind) for b in g.spec.buildings]
    at = {b.pos: b.score for b in m.buildings}
    assert all(at[p] == at[mirror(p)] for p in at) and at[(7, 7)] == 3


# ------------------------------------------------------------------ 5장 명령 형식


@pytest.mark.parametrize("line", [
    "SPAWN F 1 junk", "MOVE 0 7 F 1 R EXTRA", "MOVE2 0 7 W 1 R R", "PRIORITY 1 2 3", "SPAWN F 0",
    "SPAWN X 1", "MOVE 0 7 F 1 X", "MOVE 0 7 F -1 R", "TELE 1 1 F 1 2", "HELLO", "",
])
def test_malformed_lines_are_ignored(line):  # 5장 예시 + 같은 원리의 변형
    assert parse_command(line).status == "ignored"


@pytest.mark.parametrize("line", [
    "SPAWN F 1", "SPAWN W 2 3 4", "MOVE 0 7 F 1 R", "MOVE2 0 7 S 1 R D", "TELE 1 1 W 2 3 3",
    "PRIORITY", "PRIORITY 1 2 3 4",
])
def test_wellformed_lines_parse(line):
    assert parse_command(line).status == "ok"


def test_bad_line_does_not_affect_others():  # 5장: 잘못된 줄만 무시
    g = make_game()
    log = step(g, Y=["SPAWN F 1 junk", "SPAWN F 1"])
    assert statuses(log) == ["ignored", "ok"]
    assert g.count("Y", "F", Y_BASE) == 1


# ------------------------------------------------------------------ 4장 턴 순서 · 생산


def test_spawn_uses_last_turns_resource_only():  # 4장: 생산은 수입보다 먼저
    g = make_game()
    log = step(g, Y=["SPAWN F 3"])
    assert statuses(log) == ["partial"]
    assert g.count("Y", "F", Y_BASE) == 2
    assert g.resource["Y"] == 0 + 10


def test_spawned_units_move_same_turn():  # 4장
    g = make_game()
    step(g, Y=["MOVE 0 0 F 1 R", "SPAWN F 1"])  # 출력 순서와 무관하게 생산이 먼저
    assert g.count("Y", "F", (1, 0)) == 1 and g.count("Y", "F", Y_BASE) == 0


def test_eng_discount_floor():  # 8장 공학관
    g = make_game([((3, 3), "ENG", 1), ((4, 4), "ENG", 1)])
    g.owner[0] = "Y"
    step(g, Y=["SPAWN W 5"])
    assert g.count("Y", "W", Y_BASE) == 5  # 비용 2
    g.owner[1] = "Y"
    g.resource["Y"] = 10
    step(g, Y=["SPAWN W 10"])
    assert g.count("Y", "W", Y_BASE) == 10  # 2개여도 2 (최소 2)


def test_hospital_spawn_rules():  # 5장 SPAWN
    g = make_game([((3, 3), "HOSPITAL", 1), ((4, 4), "HOSPITAL", 1)])
    g.owner[0] = "Y"
    g.owner[1] = "K"
    log = step(g, Y=["SPAWN F 1 3 3", "SPAWN F 1 4 4", "SPAWN F 1 0 0"])
    assert statuses(log) == ["ok", "ignored", "ignored"]  # 상대 병원, 본진 좌표 명시
    assert g.count("Y", "F", (3, 3)) == 1


# ------------------------------------------------------------------ 이동


def test_move_into_obstacle_or_outside_is_ignored():
    g = make_game(obstacles=[(1, 0)])
    put(g, "Y", "F", (0, 0), 1)
    log = step(g, Y=["MOVE 0 0 F 1 R", "MOVE 0 0 F 1 U"])
    assert statuses(log) == ["ignored", "ignored"]
    assert g.count("Y", "F", (0, 0)) == 1


def test_arrived_units_cannot_move_again():  # 4장
    g = make_game()
    put(g, "Y", "F", (5, 5), 2)
    log = step(g, Y=["MOVE 5 5 F 2 R", "MOVE 6 5 F 2 R"])
    assert statuses(log) == ["ok", "ignored"]
    assert g.count("Y", "F", (6, 5)) == 2


def test_move_counts_remaining_units():  # 5장 공통 규칙
    g = make_game()
    put(g, "Y", "F", (5, 5), 3)
    log = step(g, Y=["MOVE 5 5 F 2 R", "MOVE 5 5 F 2 D"])
    assert statuses(log) == ["ok", "partial"]
    assert (g.count("Y", "F", (6, 5)), g.count("Y", "F", (5, 6))) == (2, 1)


def test_swap_moves_have_no_collision():  # 4장: 이동 중 충돌 없음
    g = make_game()
    put(g, "Y", "W", (5, 5), 1)
    put(g, "K", "W", (6, 5), 1)
    step(g, Y=["MOVE 5 5 W 1 R"], K=["MOVE 6 5 W 1 L"])
    assert g.count("Y", "W", (6, 5)) == 1 and g.count("K", "W", (5, 5)) == 1


def test_move2_path_rules():  # 2장, 5장 MOVE2
    g = make_game(obstacles=[(6, 5)])
    put(g, "Y", "S", (5, 5), 3)
    log = step(g, Y=["MOVE2 5 5 S 1 R D", "MOVE2 5 5 S 1 D R", "MOVE2 5 5 S 1 U U"])
    assert statuses(log) == ["ignored", "ok", "ok"]  # 경유 칸이 장애물이면 무효, 꺾기 가능
    assert g.count("Y", "S", (6, 6)) == 1 and g.count("Y", "S", (5, 3)) == 1


def test_scout_passes_through_enemy_without_combat():  # 2장: 경유 칸 전투 없음
    g = make_game()
    put(g, "Y", "S", (5, 5), 1)
    put(g, "K", "W", (6, 5), 3)
    step(g, Y=["MOVE2 5 5 S 1 R R"])
    assert g.count("Y", "S", (7, 5)) == 1


def test_tele_rules():  # 5장 TELE, 8장 역
    g = make_game([((3, 3), "STATION", 1), ((10, 10), "STATION", 1), ((12, 3), "STATION", 2)])
    put(g, "Y", "W", (3, 3), 7)
    log = step(g, Y=["TELE 3 3 W 7 10 10"])
    assert statuses(log) == ["ignored"]  # 역 0개
    g.owner[0] = g.owner[1] = "Y"
    log = step(g, Y=["TELE 12 3 W 1 10 10", "TELE 3 3 F 1 10 10", "TELE 3 3 W 7 10 10",
                     "TELE 3 3 W 1 10 10"])
    # 내 역 아님 · 0명(횟수 소모 없음) · 5명까지(가정) · 턴당 1회
    assert statuses(log) == ["ignored", "ignored", "partial", "ignored"]
    assert g.count("Y", "W", (10, 10)) == 5 and g.count("Y", "W", (3, 3)) == 2


def test_tele_needs_station_owned_at_move_stage():  # 4장 적용 시점
    g = make_game([((3, 3), "STATION", 1), ((10, 10), "STATION", 1)])
    g.owner[0] = "Y"
    put(g, "Y", "F", (10, 10), 1)
    put(g, "Y", "W", (3, 3), 1)
    log = step(g, Y=["TELE 3 3 W 1 10 10"])
    assert statuses(log) == ["ignored"]
    assert g.owner[1] == "Y"  # 이번 턴에 점령은 됨


def test_tele_arrivals_fight():  # 5장 TELE
    g = make_game([((3, 3), "STATION", 1), ((10, 10), "STATION", 1)])
    g.owner[0] = g.owner[1] = "Y"
    put(g, "Y", "W", (3, 3), 2)
    put(g, "K", "F", (10, 10), 1)
    step(g, Y=["TELE 3 3 W 2 10 10"])
    assert g.count("K", "F", (10, 10)) == 0 and g.count("Y", "W", (10, 10)) == 2


# ------------------------------------------------------------------ 6장 전투


def test_combat_table_row1():  # Y F1+W2 / K W1 → Y W1 생존, 깃발병 점령 진행
    g = make_game([((5, 5), "HALL", 1)])
    put(g, "Y", "F", (5, 5), 1)
    put(g, "Y", "W", (5, 5), 2)
    put(g, "K", "W", (5, 5), 1)
    step(g)
    assert g.count("Y", "W", (5, 5)) == 1 and g.count("K", "W", (5, 5)) == 0
    assert g.owner[0] == "Y"


def test_combat_table_row2_contest():  # 전투병 상호 전멸 → 경합, 점령 불가
    g = make_game([((5, 5), "HALL", 1)])
    for t in "YK":
        put(g, t, "F", (5, 5), 1)
        put(g, t, "W", (5, 5), 1)
    log = step(g)
    assert g.owner[0] is None
    assert g.count("Y", "F", (5, 5)) == 1 and g.count("K", "F", (5, 5)) == 1
    assert any(e["type"] == "contested" for e in log.events)


def test_combat_table_row3_flag_pulled():  # Y 소유 건물의 Y 깃발병 / K W1 → 중립
    g = make_game([((5, 5), "HALL", 1)])
    g.owner[0] = "Y"
    put(g, "Y", "F", (5, 5), 1)
    put(g, "K", "W", (5, 5), 1)
    step(g)
    assert g.owner[0] is None and g.count("Y", "F", (5, 5)) == 0
    assert bline(g, "K", 0)[:2] == ("N", 1)  # 11장: 직전 턴에 중립이 됨
    step(g)
    assert bline(g, "K", 0)[:2] == ("N", 0)


def test_combat_table_row4_scouts_die():
    g = make_game()
    put(g, "Y", "S", (5, 5), 2)
    put(g, "K", "W", (5, 5), 1)
    step(g)
    assert g.count("Y", "S", (5, 5)) == 0 and g.count("K", "W", (5, 5)) == 1


def test_equal_warriors_cancel_and_nothing_else():  # C1, C3
    g = make_game()
    put(g, "Y", "W", (5, 5), 2)
    put(g, "Y", "S", (5, 5), 1)
    put(g, "K", "W", (5, 5), 2)
    step(g)
    assert g.count("Y", "S", (5, 5)) == 1
    assert g.count("Y", "W", (5, 5)) == 0 and g.count("K", "W", (5, 5)) == 0


# ------------------------------------------------------------------ 7장 점령


def test_neutral_and_plaza_capture_cost():
    g = make_game([((5, 5), "HALL", 1), ((7, 7), "PLAZA", 3)])
    put(g, "Y", "F", (5, 5), 1)
    put(g, "K", "F", (7, 7), 1)
    step(g)
    assert g.owner == {0: "Y", 1: "K"}
    assert g.resource == {"Y": 20 - 2, "K": 20 - 4}


def test_library_discount():  # 8장: 단계 비용 −1, 최소 1
    g = make_game([((1, 1), "LIBRARY", 1), ((5, 5), "HALL", 1), ((7, 7), "PLAZA", 3)])
    g.owner[0] = "Y"
    put(g, "Y", "F", (5, 5), 1)
    put(g, "Y", "F", (7, 7), 1)
    step(g)
    assert g.resource["Y"] == 20 - 1 - 3


def test_library_discount_fixed_at_capture_stage_start():  # 8장
    g = make_game([((1, 1), "LIBRARY", 1), ((5, 5), "HALL", 1)])
    g.owner[0] = "K"
    put(g, "Y", "F", (1, 1), 1)  # Y가 K 도서관을 중립화하는 같은 단계에서
    put(g, "K", "F", (5, 5), 1)  # K는 할인 받은 비용으로 점령
    step(g)
    assert g.owner == {0: None, 1: "K"}
    assert g.resource["K"] == 20 - 1


def test_enemy_building_takes_two_turns():
    g = make_game([((5, 5), "HALL", 1)])
    g.owner[0] = "K"
    put(g, "Y", "F", (5, 5), 1)
    step(g)
    assert g.owner[0] is None and bline(g, "Y", 0)[:2] == ("N", 1)
    step(g)
    assert g.owner[0] == "Y"


def test_combat_neutralized_building_captured_same_turn():  # 7장
    g = make_game([((5, 5), "HALL", 1)])
    g.owner[0] = "K"
    put(g, "K", "F", (5, 5), 1)
    put(g, "Y", "F", (5, 4), 1)
    put(g, "Y", "W", (5, 4), 1)
    step(g, Y=["MOVE 5 4 F 1 D", "MOVE 5 4 W 1 D"])
    assert g.owner[0] == "Y"
    assert g.resource["Y"] == 20 - 2


def test_flag_stays_when_flagbearer_leaves():  # 7장
    g = make_game([((5, 5), "HALL", 1)], anchor=True)
    put(g, "Y", "F", (5, 5), 1)
    step(g)
    step(g, Y=["MOVE 5 5 F 1 R"])
    assert g.owner[0] == "Y"


def _six_targets(team):
    cells = [(3, 2), (9, 2), (2, 6), (12, 6), (4, 11), (10, 11)]
    g = make_game([(c, "HALL", 1) for c in cells])
    for c in cells:
        put(g, team, "F", c, 1)
    g.resource[team] = 0  # 수입 10 → 5개만 점령 가능
    return g, cells


def test_shortage_default_order_is_normalized_coordinates():  # 7장 기본 순서 3
    g, _ = _six_targets("Y")
    step(g)
    assert [g.owner[i] for i in range(6)] == ["Y"] * 5 + [None]  # (y, x) 사전순 마지막이 밀림
    g, _ = _six_targets("K")
    step(g)
    assert [g.owner[i] for i in range(6)] == [None] + ["K"] * 5  # K는 (14−y, 14−x)


def test_shortage_prefers_known_high_score():  # 7장 기본 순서 2
    cells = [(3, 2), (9, 2), (2, 6), (12, 6), (4, 11), (10, 11)]
    g = make_game([(c, "HALL", 1) for c in cells[:5]] + [(cells[5], "DEPOT", 4)])
    for c in cells:
        put(g, "Y", "F", c, 1)
    g.resource["Y"] = 0
    g.revealed["Y"].add(5)
    step(g)
    assert g.owner[5] == "Y" and g.owner[4] is None


def test_shortage_priority_first_and_last_line_wins():  # 5장 PRIORITY
    g, _ = _six_targets("Y")
    log = step(g, Y=["PRIORITY 3 2", "PRIORITY 10 11 5 5 10 11"])
    assert statuses(log) == ["ignored", "ok"]
    assert g.owner[5] == "Y" and g.owner[4] is None


def test_shortage_skips_to_cheaper_building_assumed():
    g = make_game([((7, 7), "PLAZA", 3), ((9, 9), "HALL", 1)])
    put(g, "Y", "F", (7, 7), 1)
    put(g, "Y", "F", (9, 9), 1)
    g.resource["Y"] = -7  # 수입 뒤 3: 광장(4)은 못 하고 회관(2)은 가능
    step(g, Y=["PRIORITY 7 7"])
    assert g.owner == {0: None, 1: "Y"}
    assert engine.ASSUMPTIONS["capture_shortage"]


def test_depot_bonus_after_all_captures_once_per_team():  # 8장 보급소
    cells = [(3, 2), (9, 2), (2, 6), (12, 6), (4, 11), (10, 11)]
    g = make_game([(cells[0], "DEPOT", 3)] + [(c, "HALL", 1) for c in cells[1:]], anchor=True)
    for c in cells:
        put(g, "Y", "F", c, 1)
    g.resource["Y"] = 0
    step(g, Y=["PRIORITY 3 2"])
    assert g.owner[0] == "Y"
    assert sum(g.owner[i] == "Y" for i in range(6)) == 5  # 보너스로 6번째를 같은 턴에 못 먹음
    assert g.resource["Y"] == 15
    # 빼앗겼다 되찾아도 다시 받지 못한다
    g.owner[0] = None
    before = g.resource["Y"]
    step(g, Y=["MOVE 10 11 F 1 R"])  # 남은 회관 위 깃발병은 비켜서 보급소만 점령
    assert g.owner[0] == "Y"
    assert g.resource["Y"] == min(40, before + 10 + 2 * 4) - 2


def test_depot_bonus_for_other_team_too_and_capped():
    g = make_game([((5, 5), "DEPOT", 3)])
    g.depot_claimed["Y"].add(0)
    put(g, "K", "F", (5, 5), 1)
    g.resource["K"] = 38
    step(g)
    assert g.resource["K"] == 40  # 38 → 수입 40(상한) → 점령 38 → +15 → 40(상한)


def test_hall_income_from_next_turn_and_cap():  # 4장 적용 시점
    g = make_game([((5, 5), "HALL", 1)], anchor=True)
    put(g, "Y", "F", (5, 5), 1)
    step(g)
    assert g.resource["Y"] == 10 + 10 - 2
    step(g)
    assert g.resource["Y"] == 18 + 12
    step(g)
    assert g.resource["Y"] == 40


# ------------------------------------------------------------------ 9장 정보 공개


def test_reveal_by_unit_on_building_team_only():
    g = make_game([((5, 5), "HALL", 2)], anchor=True)
    put(g, "Y", "F", (5, 4), 1)
    assert bline(g, "Y", 0)[2] == -1
    step(g, Y=["MOVE 5 4 F 1 D"])
    assert bline(g, "Y", 0)[2] == 2 and bline(g, "K", 0)[2] == -1
    step(g, Y=["MOVE 5 5 F 1 U"])
    assert bline(g, "Y", 0)[2] == 2  # 영구


def test_reveal_by_scout_range_2():
    g = make_game([((5, 5), "HALL", 2), ((5, 10), "HALL", 1)])  # 거리 2 · 3
    put(g, "Y", "S", (7, 7), 1)
    step(g)
    assert bline(g, "Y", 0)[2] == 2 and bline(g, "Y", 1)[2] == -1


def test_reveal_by_watch_range_3_on_capture_turn():
    g = make_game([((5, 5), "WATCH", 3), ((8, 8), "HALL", 2), ((9, 9), "HALL", 1)])
    put(g, "Y", "F", (5, 5), 1)
    step(g)
    assert bline(g, "Y", 1)[2] == 2 and bline(g, "Y", 2)[2] == -1


def test_dead_units_do_not_reveal():
    g = make_game([((5, 5), "HALL", 2)])
    put(g, "Y", "F", (5, 4), 1)
    put(g, "K", "W", (5, 5), 1)
    step(g, Y=["MOVE 5 4 F 1 D"])
    assert bline(g, "Y", 0)[2] == -1


# ------------------------------------------------------------------ 10장 승부


def test_instant_win():
    g = make_game([((5, 5), "HALL", 2), ((9, 9), "HALL", 2), ((7, 7), "PLAZA", 3)])
    g.owner[0] = "Y"
    put(g, "Y", "F", (7, 7), 1)
    step(g)
    assert g.result["winner"] == "Y" and g.result["reason"] == "instant"


def test_no_instant_win_while_enemy_owns_something():
    g = make_game([((5, 5), "HALL", 2), ((9, 9), "HALL", 1), ((7, 7), "PLAZA", 3)])
    g.owner[0], g.owner[1] = "Y", "K"
    put(g, "Y", "F", (7, 7), 1)
    step(g)
    assert g.result is None


@pytest.mark.parametrize("setup, reason, winner", [
    ({"owner": {0: "Y", 1: "K"}, "occ": (5, 9)}, "score", "Y"),
    ({"owner": {0: "Y", 2: "K"}, "occ": (5, 9)}, "occupation", "K"),
    ({"owner": {0: "Y", 2: "K"}, "occ": (9, 9), "units": ("K", "W")}, "units", "K"),
    ({"owner": {0: "Y", 2: "K"}, "occ": (9, 9)}, "draw", None),
])
def test_final_tiebreaks(setup, reason, winner):
    g = make_game([((1, 1), "HALL", 2), ((2, 2), "HALL", 1), ((13, 13), "HALL", 2)])
    g.owner.update(setup["owner"])
    g.occupation = {"Y": setup["occ"][0], "K": setup["occ"][1]}
    if "units" in setup:
        put(g, setup["units"][0], setup["units"][1], (7, 7), 1)
    g.turn = rules.TOTAL_TURNS - 1
    step(g)
    assert (g.result["reason"], g.result["winner"]) == (reason, winner)


def test_forfeit_and_double_forfeit():
    g = make_game()
    g.forfeit({"K": "시간 초과"})
    assert g.result["winner"] == "Y"
    g = make_game()
    g.forfeit({"Y": "x", "K": "y"})
    assert g.result["winner"] is None and g.result["reason"] == "forfeit"


# ------------------------------------------------------------------ 11장 입출력 블록


def test_turn_block_format_and_order():
    g = make_game([((5, 5), "HALL", 2)])
    put(g, "K", "S", (1, 1), 1)
    put(g, "Y", "W", (3, 2), 2)
    put(g, "Y", "F", (9, 1), 1)
    put(g, "Y", "F", (2, 1), 4)
    lines = g.turn_text("K").splitlines()
    assert lines[:3] == ["TURN 1", "RESOURCE 10 10", "UNITS 4"]
    assert lines[3:7] == ["Y F 2 1 4", "Y F 9 1 1", "Y W 3 2 2", "K S 1 1 1"]
    assert lines[7:] == ["BUILDINGS 1", "0 5 5 HALL N 0 -1", "END"]


def test_init_block_format():
    g = Game(mapgen.generate(0))
    lines = g.init_text("K").splitlines()
    assert lines[0] == "INIT 15 15" and lines[1] == "TEAM K"
    assert all(ln.startswith("MAP ") and len(ln) == 19 for ln in lines[2:17])
    assert lines[17] == "BUILDINGS 17"
    assert all(len(ln.split()) == 4 for ln in lines[18:35])
    assert lines[35].startswith("BASE Y ") and lines[36].startswith("BASE K ")
    assert lines[37] == "END" and len(lines) == 38
