"""흉내 봇: 뭉쳐서 밀기 (Team 24, 9/28 22:00 8위).

크아앙 시점 리플레이(`data/server-replays/2026-09-28_not_faced/02_*`)에서 Team 24는 넓게 까는 강팀들과 달랐다.
10~30턴 수비 배치 24%, 전투병 칸 13.8곳·칸당 5.5명(뭉침), 전투의 58%가 상대 진영. 초반 깃발병 8명으로 10턴 건물 9:5,
30턴부터 깃발병 4명. 70~80턴 상대 학생회관을 빼앗고 생산 352:322로 이겼다.

이 봇은 FLAGS_UNTIL턴까지 깃발병 총원 EARLY_FLAGS명, 그 뒤 LATE_FLAGS명. 수비 배치·초소·추가 호위 없이 전투병을 공통
목표로 뭉쳐 보내고, RAID_FROM턴부터 상대 학생회관·공학관에 "위협 + RAID_EXTRA"명을 보내 빼앗는다. 공격 국면 문턱을 낮춘다.
"""

from mimic import Task, add_tasks, each_turn, run, s, scale_capture

EARLY_FLAGS, LATE_FLAGS, FLAGS_UNTIL = 8, 4, 25
RAID_FROM = 40
RAID_KINDS = {"HALL", "ENG"}
RAID_EXTRA = 5
RAID_WEIGHT = 3.0
RAID_CAPTURE = 2.0


def flags(t):
    s.MAX_FLAGS = EARLY_FLAGS if t.world.turn <= FLAGS_UNTIL else LATE_FLAGS
    s.MIN_FLAGS = 4 if t.world.turn <= FLAGS_UNTIL else 2


def raid(t):
    if t.world.turn < RAID_FROM:
        return []
    return [Task("급습", "W", b.pos, t.threat.get(b.pos, 0) + RAID_EXTRA, t.values[b.id] * RAID_WEIGHT)
            for b in sorted(t.world.owned(t.world.enemy), key=lambda b: t.key(b.pos)) if b.kind in RAID_KINDS]


def target(t, b):
    hit = t.world.turn >= RAID_FROM and b.owner == t.world.enemy and b.kind in RAID_KINDS
    return RAID_CAPTURE if hit else 1.0


s.ATTACK_MARGIN = 0
each_turn(flags)
add_tasks("W", raid)
scale_capture(target)

if __name__ == "__main__":
    run()
