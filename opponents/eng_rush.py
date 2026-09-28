"""흉내 봇: 공학관 러시 (참새튀김기·페이커).

9/28 리더보드에서 참새튀김기는 14턴, 페이커는 19턴에 우리 공학관을 빼앗았고, 그 뒤 우리 전투병 값이 3인 턴이
57%·74%였다. 이 봇은 RUSH_UNTIL턴까지 상대 캠퍼스 공학관에 전투병을 "위협 + RUSH_EXTRA"명 보내고, 깃발병이
그 공학관을 먼저 노리게 한다. 강팀 운용(깃발병 호위, 상대 건물 초소)을 함께 켠다.
"""

from mimic import Task, add_tasks, enemy_campus, escort_flags, pickets, run, scale_capture

RUSH_UNTIL = 40
RUSH_EXTRA = 2
RUSH_VALUE = 6.0
RUSH_CAPTURE = 3.0  # 러시 중 공학관 점령 가치 배수


def rush(t):
    if t.world.turn > RUSH_UNTIL:
        return []
    return [Task("급습", "W", b.pos, t.threat.get(b.pos, 0) + RUSH_EXTRA, RUSH_VALUE)
            for b in enemy_campus(t, {"ENG"}) if b.owner != t.world.me]


add_tasks("W", rush)
scale_capture(lambda t, b: RUSH_CAPTURE if b.kind == "ENG" and t.world.turn <= RUSH_UNTIL else 1.0)
escort_flags(1.0)
pickets(0.5, enemy_only=True)

if __name__ == "__main__":
    run()
