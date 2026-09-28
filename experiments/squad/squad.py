"""실험 변형 (현진): 별동대 — 깃발병 1명 + 전투병 SQUAD_SIZE명이 한 목표에 집중한다.

- 깃발병 1차 배정(assign_flags)에서, 위험한 목표(적 소유이거나 적 전투병이 닿는 건물)를 맡은 깃발병 중 과제
  가치가 가장 큰 한 명을 별동대 깃발병으로 고른다
- 그 깃발병이 이번 턴 들어갈 칸(목표 쪽 한 칸, 이미 목표 위면 목표)에 "별동대" 과제: 전투병 SQUAD_SIZE명,
  가치 = 점령 과제 가치 × SQUAD_WEIGHT. 전투병이 그 칸을 먼저 차지하므로 깃발병의 안전 판단(적 위협 ≤ 우리
  전투병)이 통과되어, 가는 길에서도 함께 움직인다. main의 호위는 점령을 시작한 뒤에만 붙는다
- SECOND_SQUAD_TURN턴부터는 별동대를 2개(목표 건물이 서로 다른 깃발병 2명) 운용한다
- 나머지는 main 그대로. strategy.py는 고치지 않는다
"""

from __future__ import annotations

from agent.algorithms import step_along
from agent.bt import Act, Node, Selector, Sequence
from agent.strategy import TURN_TREE, Task, Turn, assign_flags, plan_warrior_tasks
from agent.world import Action, World

# main(`a15e589`) 상대 시드 100~124 50경기: 인원 1 / 2 / 3 / 5 × 가중치 1 → 44 / 56 / 28 / 76%, × 3 → 40 / 60 / 68 / 64%.
# 5 × 1: 시드 0~99 75%, 200~299 66%, 300~399 59%, 서버 맵 83% (docs/benchmarks.md)
SQUAD_SIZE = 5
SQUAD_WEIGHT = 1.0
# 이 턴부터 별동대를 2개 운용한다 (목표 건물이 서로 다른 깃발병 2명). 10**6이면 늘 1개.
# 1개 대비 30턴: 직접 대결 62%, main 상대 69% (1개 66%), 흉내 봇 풀 평균 62% (55%), 문원 테마 브랜치 상대 50% (41%),
# 서버 맵 67% (75.5%). 1 / 60 / 100턴은 main 상대 50경기 56 / 68 / 76%, 60턴은 1개 상대 57% (docs/benchmarks.md)
SECOND_SQUAD_TURN = 30


def squad_tasks(t: Turn) -> list[Task]:
    """별동대 과제. 위험한 목표로 가는 깃발병을 과제 가치 순(동점이면 정규화 좌표 순)으로, 목표 건물이 겹치지 않게
    1명(SECOND_SQUAD_TURN부터 2명) 골라 각자 다음 칸에 전투병 SQUAD_SIZE명."""
    world = t.world
    count = 2 if world.turn >= SECOND_SQUAD_TURN else 1
    cands = []
    for pos, task in assign_flags(t.flags, t.f_tasks, t.dist_to):
        b = task.building
        if b.owner == world.enemy or t.threat.get(b.pos, 0):
            cands.append((-task.value, t.key(pos), pos, task))
    cands.sort(key=lambda c: c[:2])  # 안정 정렬 = 동점이면 배정 순서 (한 개일 때 예전과 같은 깃발병)
    tasks, taken = [], set()
    for *_, pos, task in cands:
        if len(tasks) == count:
            break
        if task.building.id in taken:
            continue
        taken.add(task.building.id)
        cell = step_along(pos, t.dist_to(task.pos), t.order) or pos
        tasks.append(Task("별동대", "W", cell, SQUAD_SIZE, task.value * SQUAD_WEIGHT))
    return tasks


def plan_warrior_tasks_squad(t: Turn) -> None:
    plan_warrior_tasks(t)
    tasks = squad_tasks(t)
    if tasks:
        t.w_tasks = sorted(t.w_tasks + tasks, key=lambda x: t.key(x.pos))


def swap(node: Node, table: dict) -> Node:
    """트리를 복사하며 행동 잎의 함수가 `table`에 있으면 그 잎으로 바꾼다."""
    run = getattr(node, "run", None)
    if run in table:
        return table[run]
    if type(node) in (Sequence, Selector):
        return type(node)(node.name, *(swap(child, table) for child in node.children))
    return node


SQUAD_TREE = swap(TURN_TREE, {
    plan_warrior_tasks: Act("전투병 과제 목록 + 별동대 (위험한 목표로 가는 깃발병 1명의 다음 칸에 전투병)",
                            plan_warrior_tasks_squad),
})


def decide(world: World) -> list[Action]:
    turn = Turn(world)
    SQUAD_TREE.tick(turn)
    return turn.actions
