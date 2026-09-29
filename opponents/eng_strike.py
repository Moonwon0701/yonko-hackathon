"""흉내 봇: 공학관 강습 (신촌도 우리땅·치명ㄷ·페이커).

리더보드 48판(9/27~9/29)에서 21~80턴 우리만 공학관이 없던 턴이 더 많은 경기는 진 15판 중 8판, 이긴 33판 중 0판이었다.
잃는 방식은 15~18턴 강습이었다: 우리 공학관 2칸 안에 적 전투병 11·16·3~6명 + 깃발병 2~4명이 한꺼번에 오고, 우리 근처는
0~7명 (docs/benchmarks.md "서버 리더보드" 표 9/29 자원 흐름 분석). `eng_rush`는 전투병을 도착하는 대로 한두 명씩 보내서
우리 봇이 공학관을 잃는 턴이 21~80턴 중 평균 4.4턴뿐이라, 이 강습을 흉내 내지 못했다.

이 봇은 STRIKE_UNTIL턴까지 전투병을 넉넉히 뽑아 상대 공학관 STAGE_DIST걸음 앞 칸(우리 본진에서 가장 가까운 칸)에 모은다.
STRIKE_EARLIEST턴부터 그 칸 한 걸음 안에 STRIKE_W명이 모이면(늦어도 STRIKE_LATEST턴) 한꺼번에 공학관으로 들어가고,
깃발병은 FLAG_FROM턴부터 그 공학관을 노려 먼저 출발한다(적 전투병이 닿는 칸 앞에서 기다리다 같이 들어간다).
빼앗은 공학관과 자기 공학관에는 전투병을 세워 지킨다. 깃발병 호위를 켠다.
"""

from mimic import Task, add_tasks, each_turn, escort_flags, run, s, scale_capture

STRIKE_W = 16  # 한꺼번에 들어갈 전투병 수
STRIKE_EARLIEST, STRIKE_LATEST = 12, 18  # 모이면 이 턴부터, 덜 모여도 이 턴에는 들어간다
STRIKE_UNTIL = 60  # 이 턴까지 강습·수비 과제를 낸다
STAGE_DIST = 3  # 집결 칸: 상대 공학관에서 이만큼 떨어진 칸
STAGE_VALUE = 8.0
STRIKE_EXTRA = 3  # 들어갈 인원 = 그 칸 위협 + 이 값 (가진 인원까지)
STRIKE_VALUE = 12.0
HOLD_EXTRA = 2
HOLD_VALUE = 6.0
STRIKE_CAPTURE = 5.0  # 그 공학관의 점령 가치 배수. FLAG_FROM턴부터 깃발병이 먼저 출발해 적 전투병이 닿는 칸 앞에서 기다린다
FLAG_FROM = 8
# 자기 공학관: GUARD_REACH걸음 안 적 전투병 + GUARD_EXTRA명. 기준 봇은 자기 공학관을 비워 두어 강습하는 동안 빼앗겼고,
# 한 걸음 위협만 세면 멀리서 계속 오는 러시에 2명씩 상쇄되어 사라졌다
GUARD_REACH = 4
GUARD_EXTRA = 2
GUARD_VALUE = 6.0

_strike = {"launched": False}
DEFAULTS = {"MIN_WARRIORS": s.MIN_WARRIORS, "MIN_FLAGS": s.MIN_FLAGS, "MAX_FLAGS": s.MAX_FLAGS}


def campus_eng(t, team):
    """`team` 본진에 더 가까운 공학관. 칠판을 만들 때 부르므로 `t.key`(상황 읽기에서 채움) 대신 좌표 순."""
    world = t.world
    home, away = world.map.bases[team], world.map.bases[world.enemy if team == world.me else world.me]
    engs = [b for b in world.buildings.values()
            if b.kind == "ENG" and t.dist_to(b.pos).get(home, 99) < t.dist_to(b.pos).get(away, 99)]
    return min(engs, key=lambda b: b.pos) if engs else None


def stage_cell(t, eng):
    """상대 공학관에서 STAGE_DIST걸음인 칸 중 우리 본진에서 가장 가까운 칸 (없으면 공학관 칸)."""
    to_eng, to_home = t.dist_to(eng.pos), t.dist_to(t.world.map.bases[t.world.me])
    cells = [c for c, d in to_eng.items() if d == STAGE_DIST and c in to_home]
    return min(cells, key=lambda c: (to_home[c], c)) if cells else eng.pos


def warriors(t):
    return sum(n for _, n in t.world.units_of(t.world.me, "W"))


def update(t):
    """매 턴: 강습 시작 여부와, 강습 전 생산(전투병을 넉넉히, 깃발병은 적게)."""
    turn = t.world.turn
    if turn <= 1:
        _strike["launched"] = False
    eng = campus_eng(t, t.world.enemy)
    t.strike_eng, t.own_eng = eng, campus_eng(t, t.world.me)
    if eng and not _strike["launched"] and STRIKE_EARLIEST <= turn:
        stage = stage_cell(t, eng)
        near = sum(n for pos, n in t.world.units_of(t.world.me, "W")
                   if abs(pos[0] - stage[0]) + abs(pos[1] - stage[1]) <= 1)
        _strike["launched"] = near >= STRIKE_W or turn >= STRIKE_LATEST
    waiting = eng is not None and not _strike["launched"]
    s.MIN_WARRIORS = STRIKE_W + 4 if waiting else DEFAULTS["MIN_WARRIORS"]
    s.MIN_FLAGS = 3 if turn <= STRIKE_UNTIL else DEFAULTS["MIN_FLAGS"]
    s.MAX_FLAGS = 4 if waiting else DEFAULTS["MAX_FLAGS"]


def guard(t):
    own = t.own_eng
    if own is None or own.owner != t.world.me:
        return []
    dist = t.dist_to(own.pos)
    coming = sum(n for pos, n in t.enemy_warriors if dist.get(pos, 99) <= GUARD_REACH)
    return [Task("수비", "W", own.pos, max(coming, t.threat.get(own.pos, 0)) + GUARD_EXTRA, GUARD_VALUE)]


def strike(t):
    eng, turn = t.strike_eng, t.world.turn
    if eng is None or turn > STRIKE_UNTIL:
        return []
    have = warriors(t)
    if not have:
        return []
    if eng.owner == t.world.me:
        return [Task("수비", "W", eng.pos, t.threat.get(eng.pos, 0) + HOLD_EXTRA, HOLD_VALUE)]
    if not _strike["launched"]:
        return [Task("집결", "W", stage_cell(t, eng), min(STRIKE_W, have), STAGE_VALUE)]
    return [Task("강습", "W", eng.pos, max(1, min(t.threat.get(eng.pos, 0) + STRIKE_EXTRA, have)), STRIKE_VALUE)]


def capture_scale(t, b):
    eng = t.strike_eng
    hit = eng is not None and b.id == eng.id and FLAG_FROM <= t.world.turn <= STRIKE_UNTIL
    return STRIKE_CAPTURE if hit else 1.0


each_turn(update)
add_tasks("W", strike)
add_tasks("W", guard)
scale_capture(capture_scale)
escort_flags(1.0)

if __name__ == "__main__":
    run()
