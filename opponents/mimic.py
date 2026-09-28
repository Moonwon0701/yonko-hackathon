"""흉내 봇 공용 부품: 고정한 기준 봇(`opponents/base/`) 위에 리더보드 강팀의 운용을 얹는다.

기준 봇은 `main` `8fd93ee`(2026-09-28)의 `main.py`·`agent/`를 그대로 복사한 것이다. 우리 전략을 고쳐도 흉내 봇은
바뀌지 않게 하려고 복사본을 쓴다. 흉내 봇 파일은 이 모듈을 불러 부품을 켜고 `run()`을 부른다.

근거는 `docs/benchmarks.md` "서버 리더보드" 표의 2026-09-28 분석 두 줄(`scripts/profile_opponents.py`):
- 강팀은 10~30턴에 깃발병 옆에 전투병을 붙이고(62%), 자기 건물에 전투병을 세우고(43%), 전투병을 넓게 깐다(20칸)
- 진 경기는 우리 공학관·학생회관을 빼앗겨 생산량이 벌어졌다
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "base"))

# 경로를 먼저 넣어야 기준 봇(opponents/base)의 agent를 불러온다
from agent import strategy as s
from agent.strategy import Task, Turn
from agent.world import Building

Maker = Callable[[Turn], list[Task]]
Scale = Callable[[Turn, Building], float]


def add_tasks(unit: str, maker: Maker) -> None:
    """모든 국면에서 `unit` 병종 과제 목록에 `maker`가 만드는 과제를 더한다."""
    original = Turn.tasks

    def tasks(self: Turn, u: str) -> list[Task]:
        found = original(self, u)
        return found + maker(self) if u == unit else found

    Turn.tasks = tasks


def scale_capture(scale: Scale) -> None:
    """점령 과제의 가치에 `scale(t, 건물)`을 곱한다 (깃발병이 어느 건물로 가는가)."""
    original = Turn.tasks

    def tasks(self: Turn, u: str) -> list[Task]:
        found = original(self, u)
        if u != "F":
            return found
        return [replace(task, value=task.value * scale(self, task.building)) if task.building else task
                for task in found]

    Turn.tasks = tasks


def escort_flags(value: float) -> None:
    """호위: 우리 깃발병이 있는 칸마다 전투병 1명 (기준 봇은 이번 턴 점령 중이고 위협받는 깃발병만 호위한다)."""

    def maker(t: Turn) -> list[Task]:
        return [Task("호위", "W", pos, 1, value) for pos, _ in t.flags]

    add_tasks("W", maker)


def garrison(count: int) -> None:
    """수비 배치: 전선 과제를 늘 켜고, 노출 순위가 앞선 우리 건물 `count`곳에 전투병 1명을 세운다
    (강팀은 10~30턴에 자기 건물의 43%에 전투병)."""
    s.FRONT_SURPLUS = -10**6
    s.FRONT_COUNT = count


def pickets(value: float, enemy_only: bool = False) -> None:
    """초소: 우리 것이 아닌 건물(`enemy_only`면 상대 건물만)마다 전투병 1명. 전투병을 넓게, 앞으로 깐다."""

    def maker(t: Turn) -> list[Task]:
        return [Task("초소", "W", b.pos, 1, value) for b in t.others
                if b.pos not in t.enemy_flags and (b.owner == t.world.enemy or not enemy_only)]

    add_tasks("W", maker)


def enemy_campus(t: Turn, kinds: set[str]) -> list[Building]:
    """상대 캠퍼스 쪽 `kinds` 건물: 상대 본진까지 걸음이 우리 본진까지보다 짧은 것."""
    world = t.world
    home, away = world.map.bases[world.me], world.map.bases[world.enemy]
    found = []
    for b in world.buildings.values():
        dist = t.dist_to(b.pos)
        if b.kind in kinds and dist.get(away, 99) < dist.get(home, 99):
            found.append(b)
    return sorted(found, key=lambda b: t.key(b.pos))


def run() -> None:
    import main  # 기준 봇의 main.py (opponents/base)

    main.main()
