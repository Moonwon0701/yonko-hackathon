"""흉내 봇: 빈 경제 건물 훔치기 (9/29 22:00 리더보드 붉은 산호초·참새튀김기·탈락도 락이다·참새 사냥꾼).

9/29 22:00 리더보드에서 우리가 학생회관·공학관을 잃은 56번 중 30번은 적 전투병 없이 깃발병 혼자 들어온 경우였다.
우리 깃발병은 점령을 마치면 전투병을 남기지 않고 떠나고, 지키기는 적 깃발병이 3걸음 안에 와야 켜져 4~8걸음 밖의 우리
전투병이 1~2턴 늦었다(붉은 산호초전 12턴 점령 → 13턴 떠남 → 15턴 지키기 → 17턴 빼앗김).
이 봇은 상대 소유 건물 중 STEAL_REACH걸음 안에 상대 전투병이 없는 곳의 점령 가치를 올린다(학생회관·공학관은 더 크게).
깃발병을 넉넉히 두어 여러 곳을 동시에 노린다.
"""

from mimic import each_turn, escort_flags, run, s, scale_capture

STEAL_FROM = 10
STEAL_REACH = 2  # 이 걸음 안에 상대 전투병이 없으면 빈 건물
STEAL_ECON = 6.0  # 빈 학생회관·공학관 점령 가치 배수
STEAL_OTHER = 2.0  # 빈 다른 건물
FLAGS = 5  # 깃발병 최소 인원 (STEAL_FROM턴부터)
DEFAULTS = {"MIN_FLAGS": s.MIN_FLAGS}


def update(t):
    s.MIN_FLAGS = FLAGS if t.world.turn >= STEAL_FROM else DEFAULTS["MIN_FLAGS"]


def steal_scale(t, b):
    world = t.world
    if world.turn < STEAL_FROM or b.owner != world.enemy:
        return 1.0
    dist = t.dist_to(b.pos)
    if any(dist.get(p, 99) <= STEAL_REACH for p, _ in world.units_of(world.enemy, "W")):
        return 1.0
    return STEAL_ECON if b.kind in ("HALL", "ENG") else STEAL_OTHER


each_turn(update)
scale_capture(steal_scale)
escort_flags(1.0)

if __name__ == "__main__":
    run()
