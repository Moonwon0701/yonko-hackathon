"""게임 입출력 형식을 아는 유일한 모듈.

stdin 블록을 World로 바꾸고, strategy가 돌려준 행동을 명령 줄로 되돌린다. 전략 판단은 넣지
않는다. 형식은 docs/rules-original.md 11장(봇 입출력 규격)을 따른다.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TextIO

from agent.world import (
    Action,
    Building,
    GameMap,
    Move,
    Move2,
    Pos,
    Priority,
    Spawn,
    Team,
    Tele,
    World,
)

_DIRECTION: dict[Pos, str] = {(0, -1): "U", (0, 1): "D", (-1, 0): "L", (1, 0): "R"}


def read_block(stream: TextIO) -> list[str] | None:
    """END로 끝나는 한 블록의 줄들. EOF면 None (경기 종료 신호)."""
    lines: list[str] = []
    for line in stream:
        line = line.strip()
        if line == "END":
            return lines
        if line:
            lines.append(line)
    return None


def parse_init(lines: list[str]) -> tuple[GameMap, Team]:
    """INIT 블록 → (고정 맵 정보, 우리 팀). 건물 목록은 매 턴 블록에 다시 오므로 버린다."""
    _, w, h = lines[0].split()
    width, height = int(w), int(h)
    me = lines[1].split()[1]
    rows = tuple(lines[2 + y].split()[1] for y in range(height))
    idx = 2 + height
    idx += 1 + int(lines[idx].split()[1])  # BUILDINGS n 과 그 n줄
    bases: dict[Team, Pos] = {}
    for line in lines[idx:idx + 2]:
        _, team, x, y = line.split()
        bases[team] = (int(x), int(y))
    return GameMap(width, height, rows, bases), me


def parse_turn(lines: list[str], game_map: GameMap, me: Team) -> World:
    turn = int(lines[0].split()[1])
    _, mine, theirs = lines[1].split()
    enemy = "K" if me == "Y" else "Y"
    gold = {me: int(mine), enemy: int(theirs)}

    k = int(lines[2].split()[1])
    units = {}
    for line in lines[3:3 + k]:
        team, kind, x, y, n = line.split()
        units[(team, kind, (int(x), int(y)))] = int(n)

    idx = 3 + k
    nb = int(lines[idx].split()[1])
    buildings = {}
    for line in lines[idx + 1:idx + 1 + nb]:
        bid, x, y, kind, owner, stage, score = line.split()
        buildings[int(bid)] = Building(
            id=int(bid),
            pos=(int(x), int(y)),
            kind=kind,
            owner=None if owner == "N" else owner,
            just_neutralized=owner == "N" and stage == "1",
            score=None if score == "-1" else int(score),
        )
    return World(game_map, me, turn, gold, units, buildings)


def _direction(src: Pos, dst: Pos) -> str:
    delta = (dst[0] - src[0], dst[1] - src[1])
    if delta not in _DIRECTION:
        raise ValueError(f"상하좌우로 붙은 칸이 아님: {src} -> {dst}")
    return _DIRECTION[delta]


def to_line(action: Action) -> str:
    """행동 하나 → 명령 한 줄. 형식에 맞출 수 없는 행동이면 ValueError."""
    match action:
        case Spawn(kind, count, None):
            return f"SPAWN {kind} {count}"
        case Spawn(kind, count, (x, y)):
            return f"SPAWN {kind} {count} {x} {y}"
        case Move((x, y), kind, count, dst):
            return f"MOVE {x} {y} {kind} {count} {_direction((x, y), dst)}"
        case Move2((x, y), count, via, dst):
            return f"MOVE2 {x} {y} S {count} {_direction((x, y), via)} {_direction(via, dst)}"
        case Tele((x, y), kind, count, (tx, ty)):
            return f"TELE {x} {y} {kind} {count} {tx} {ty}"
        case Priority(order):
            return " ".join(["PRIORITY", *(f"{x} {y}" for x, y in order)])
    raise ValueError(f"알 수 없는 행동: {action!r}")


def write_turn(stream: TextIO, lines: Iterable[str]) -> None:
    """명령 줄들 + END를 쓰고 flush. 행동이 없어도 END는 반드시 나간다."""
    stream.writelines(line + "\n" for line in lines)
    stream.write("END\n")
    stream.flush()
