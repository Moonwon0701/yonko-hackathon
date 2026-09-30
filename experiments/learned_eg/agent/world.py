"""게임 상태를 담는 우리만의 데이터 구조(World) 정의.

입력 텍스트 형식은 모른다. 파싱은 adapter.py가 하고, 여기에는 결과를 담을 그릇과 규칙 수치,
strategy.py가 돌려줄 행동 타입만 있다. 세 파일이 공유하는 계약이므로 필드를 바꾸면 셋 다에게
알린다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Pos = tuple[int, int]  # (x, y). x = 열(왼→오), y = 행(위→아래)
Team = str  # "Y" 또는 "K"
Kind = str  # "F" 깃발병, "W" 전투병, "S" 정찰병

TEAMS: tuple[Team, Team] = ("Y", "K")
KINDS: tuple[Kind, Kind, Kind] = ("F", "W", "S")

# 규칙 수치 (docs/rules-original.md 부록). 대회 중 바뀌지 않는다.
UNIT_COST: dict[Kind, int] = {"F": 5, "W": 3, "S": 2}
CAPTURE_COST = 2  # 단계당
PLAZA_CAPTURE_COST = 4  # 중앙광장 단계당
MIN_CAPTURE_COST = 1  # 도서관 할인 뒤 최소값
LIBRARY_DISCOUNT = 1
ENG_DISCOUNT = 1  # 공학관 1개당 전투병 비용 할인
ENG_COST_FLOOR = 2
DEPOT_BONUS = 15
RESOURCE_CAP = 40
BASE_INCOME = 10
HALL_BONUS = 2
TOTAL_TURNS = 160
TELE_MAX_UNITS = 5
PLAZA_SCORE = 3  # 중앙광장은 항상 3점


@dataclass(frozen=True)
class GameMap:
    """경기 내내 변하지 않는 정보. INIT에서 한 번 만든다."""

    width: int
    height: int
    rows: tuple[str, ...]  # rows[y][x]: "." 평지, "#" 장애물, "B" 건물, "H" 본진
    bases: dict[Team, Pos]

    def in_bounds(self, pos: Pos) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def passable(self, pos: Pos) -> bool:
        return self.in_bounds(pos) and self.rows[pos[1]][pos[0]] != "#"

    def mirror(self, pos: Pos) -> Pos:
        """(7,7) 기준 180° 점대칭 칸. 대칭 짝 건물은 점수가 같다."""
        return (self.width - 1 - pos[0], self.height - 1 - pos[1])


@dataclass(frozen=True)
class Building:
    id: int
    pos: Pos
    kind: str  # PLAZA HALL STATION LIBRARY ENG HOSPITAL WATCH DEPOT
    owner: Team | None  # None = 중립
    just_neutralized: bool  # 직전 턴에 소유 상태에서 중립이 됨 (판정상 중립과 같음)
    score: int | None  # None = 아직 모름. -1이나 0으로 바꾸지 않는다


@dataclass
class World:
    """한 턴의 전체 상태. 매 턴 새로 만든다."""

    map: GameMap
    me: Team
    turn: int
    gold: dict[Team, int]
    units: dict[tuple[Team, Kind, Pos], int]  # (팀, 병종, 칸) -> 인원
    buildings: dict[int, Building]  # id -> 건물

    @property
    def enemy(self) -> Team:
        return "K" if self.me == "Y" else "Y"

    def units_of(self, team: Team, kind: Kind) -> list[tuple[Pos, int]]:
        """해당 팀·병종이 있는 칸과 인원. (y, x) 순서."""
        found = [(pos, n) for (t, k, pos), n in self.units.items() if t == team and k == kind]
        return sorted(found, key=lambda item: (item[0][1], item[0][0]))

    def building_at(self, pos: Pos) -> Building | None:
        for b in self.buildings.values():
            if b.pos == pos:
                return b
        return None

    def owned(self, team: Team, kind: str | None = None) -> list[Building]:
        return [
            b for b in self.buildings.values()
            if b.owner == team and (kind is None or b.kind == kind)
        ]

    def warrior_cost(self, team: Team) -> int:
        """그 팀의 전투병 한 명 값. 공학관 1개당 ENG_DISCOUNT 할인, ENG_COST_FLOOR 아래로는 안 내려간다."""
        return max(ENG_COST_FLOOR, UNIT_COST["W"] - len(self.owned(team, "ENG")) * ENG_DISCOUNT)

    def stage_cost(self, b: Building, team: Team | None = None) -> int:
        """그 팀(기본: 우리)이 이 건물을 한 단계 점령하는 비용. 도서관을 가지면 할인."""
        cost = PLAZA_CAPTURE_COST if b.kind == "PLAZA" else CAPTURE_COST
        if self.owned(team or self.me, "LIBRARY"):
            cost = max(MIN_CAPTURE_COST, cost - LIBRARY_DISCOUNT)
        return cost

    def known_score(self, b: Building) -> int | None:
        """확실히 아는 점수. 공개된 점수, 공개된 대칭 짝의 점수, 광장(항상 3점) 순. 모르면 None."""
        if b.score is not None:
            return b.score
        if b.kind == "PLAZA":
            return PLAZA_SCORE
        twin = self.building_at(self.map.mirror(b.pos))
        return twin.score if twin else None


# ------------------------------------------------------------------ 행동
# strategy.decide가 돌려주는 값. 명령 문자열로 바꾸는 일은 adapter.py가 한다.


@dataclass(frozen=True)
class Spawn:
    kind: Kind
    count: int
    at: Pos | None = None  # None = 본진. 좌표는 내가 점령 중인 병원일 때만


@dataclass(frozen=True)
class Move:
    src: Pos
    kind: Kind
    count: int
    dst: Pos  # src와 상하좌우로 붙은 칸


@dataclass(frozen=True)
class Move2:
    """정찰병 전용 2칸 이동. src → via → dst 모두 상하좌우로 한 칸씩."""

    src: Pos
    count: int
    via: Pos
    dst: Pos


@dataclass(frozen=True)
class Tele:
    src: Pos  # 내가 점령 중인 역
    kind: Kind
    count: int
    dst: Pos  # 내가 점령 중인 다른 역


@dataclass(frozen=True)
class Priority:
    order: tuple[Pos, ...] = field(default_factory=tuple)


Action = Spawn | Move | Move2 | Tele | Priority
