"""흉내 봇: 옆 칸에 쌓았다가 동수에 들어가기 (9/29 22:00 리더보드 참새튀김기·탈락도 락이다·뉴비들).

9/29 22:00 리더보드에서 우리가 학생회관·공학관을 잃은 56번 중 23번은 상쇄 패배였다. 상대는 우리 건물 바로 옆 칸에
전투병을 턴마다 한두 명씩 더 쌓고(참새튀김기전 30~32턴 9 → 10 → 11명), 우리 칸 위 인원과 같아지는 턴에 깃발병과 함께
들어왔다. 동수면 서로 상쇄되어 남은 전투병이 없으므로 공격 쪽 깃발병이 살아남아 중립화한다. 우리 봇은 "위협 + 1"을
맞게 계산했지만 증원이 2걸음 밖이라 한 턴씩 늦었다.
이 봇은 HOVER_FROM턴부터 상대 학생회관·공학관 하나를 골라, 그 옆 칸(우리 본진에서 가장 가까운 칸)에 전투병을 모은다.
옆 칸 인원이 그 건물 위 상대 전투병 이상이고 HOVER_MIN명 이상이면 들어가고, 깃발병이 그 건물을 노린다.
"""

from mimic import Task, add_tasks, each_turn, escort_flags, run, s, scale_capture

TARGET_KINDS = ("HALL", "ENG")
HOVER_FROM = 15
HOVER_MIN = 4  # 들어가는 최소 인원
HOVER_EXTRA = 1  # 모으는 인원 = 건물 위 상대 전투병 + 이 값 (모이는 동안 상대가 더 세우므로 조금 넉넉히)
HOVER_VALUE = 8.0
STRIKE_VALUE = 12.0
CAPTURE_SCALE = 4.0
_state = {"target": None}


def target(t):
    """노릴 상대 경제 건물: 지금 노리는 것이 아직 상대 것이면 그대로, 아니면 건물 위 상대 전투병이 가장 적은 것
    (같으면 우리 본진에서 가까운 것)."""
    world = t.world
    if world.turn <= 1:
        _state["target"] = None
    cands = [b for b in world.buildings.values() if b.kind in TARGET_KINDS and b.owner == world.enemy]
    if not cands:
        return None
    for b in cands:
        if b.id == _state["target"]:
            return b
    home = world.map.bases[world.me]
    guard = {b.id: world.units.get((world.enemy, "W", b.pos), 0) for b in cands}
    best = min(cands, key=lambda b: (guard[b.id], t.dist_to(b.pos).get(home, 99), b.pos))
    _state["target"] = best.id
    return best


def stage_cell(t, b):
    """건물 옆 칸 중 우리 본진에서 가장 가까운 칸."""
    world = t.world
    home = t.dist_to(world.map.bases[world.me])
    x, y = b.pos
    cells = [c for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
             if world.map.in_bounds(c) and world.map.passable(c) and c in home]
    return min(cells, key=lambda c: (home[c], c)) if cells else None


def update(t):
    t.hover_target = target(t) if t.world.turn >= HOVER_FROM else None


def hover(t):
    b = t.hover_target
    if b is None:
        return []
    stage = stage_cell(t, b)
    if stage is None:
        return []
    world = t.world
    guard = world.units.get((world.enemy, "W", b.pos), 0)
    have = world.units.get((world.me, "W", stage), 0)
    if have >= max(HOVER_MIN, guard):
        return [Task("강습", "W", b.pos, max(1, guard), STRIKE_VALUE)]
    return [Task("집결", "W", stage, max(HOVER_MIN, guard + HOVER_EXTRA), HOVER_VALUE)]


def capture_scale(t, b):
    return CAPTURE_SCALE if t.hover_target is not None and b.id == t.hover_target.id else 1.0


each_turn(update)
add_tasks("W", hover)
scale_capture(capture_scale)
escort_flags(1.0)

if __name__ == "__main__":
    run()
