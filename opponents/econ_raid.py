"""흉내 봇: 중반 경제 급습 (AIKU).

AIKU는 9/28 10:00 경기에서 40턴에 우리 학생회관을, 22:00 경기에서 62턴에 우리 공학관을 빼앗았고, 20~80턴 전투병을
343~393명 만들어 우리(284~294명)보다 50~100명 많았다. 이 봇은 RAID_FROM턴부터 상대가 가진 공학관·학생회관·병원에
전투병을 "위협 + RAID_EXTRA"명 보내고 깃발병이 뒤따라 빼앗는다. 강팀 운용(깃발병 호위, 상대 건물 초소)을 함께 켠다.
"""

from mimic import Task, add_tasks, escort_flags, pickets, run, s, scale_capture

RAID_FROM = 30
RAID_KINDS = {"ENG", "HALL", "HOSPITAL"}
RAID_EXTRA = 3
RAID_WEIGHT = 3.0  # 급습 과제 가치 = 건물 가치 × 이 값
RAID_CAPTURE = 2.0  # 급습 대상 점령 가치 배수


def raid(t):
    if t.world.turn < RAID_FROM:
        return []
    enemy = t.world.enemy
    return [Task("급습", "W", b.pos, t.threat.get(b.pos, 0) + RAID_EXTRA, t.values[b.id] * RAID_WEIGHT)
            for b in sorted(t.world.owned(enemy), key=lambda b: t.key(b.pos)) if b.kind in RAID_KINDS]


def target(t, b):
    hit = t.world.turn >= RAID_FROM and b.owner == t.world.enemy and b.kind in RAID_KINDS
    return RAID_CAPTURE if hit else 1.0


s.ATTACK_MARGIN = 0
add_tasks("W", raid)
scale_capture(target)
escort_flags(1.0)
pickets(0.5, enemy_only=True)

if __name__ == "__main__":
    run()
