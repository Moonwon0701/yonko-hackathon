"""게임 엔진: 규칙서(docs/rules-original.md B장)대로 한 턴씩 진행한다.

한 턴의 처리 순서 (규칙서 4장):
    1 명령 수신 → 2 생산 → 3 이동 → 4 전투 → 5 건물 효과 → 6 수입 → 7 점령 → 8 정보 공개 → 9 승리 판정

봇과의 입출력(프로세스·시간 제한)은 여기서 하지 않는다. 이 모듈은 텍스트 명령 줄을 받아 상태를
바꾸고, 봇에게 보낼 INIT·TURN 블록 텍스트를 만든다.

규칙서로 답이 정해지지 않아 우리가 정한 해석은 `ASSUMPTIONS`에 모아 두었다. 공식 엔진(devtool/)이 나온 뒤
tests/test_official.py가 이 엔진과 공식 엔진을 매 턴 비교하므로, 해석은 모두 공식 동작과 같다고 확인됐다.
엔진을 고치면 그 테스트가 통과하는지 꼭 본다.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from sim import rules
from sim.mapgen import MapSpec

Pos = tuple[int, int]
UnitKey = tuple[str, str, Pos]  # (팀, 병종, 칸)

ASSUMPTIONS = {
    "capture_shortage": "자원이 모자라 점령 못 한 건물은 건너뛰고, 순서상 다음 건물 중 비용을 낼 수 있는 것은 진행한다.",
    "tele_over_max": "TELE 인원이 5를 넘으면 5명까지만 옮긴다(명령 무효가 아님).",
    "tele_same_station": "출발·도착이 같은 역인 TELE는 무효.",
    "priority_last_valid": "PRIORITY가 여러 줄이면 형식이 올바른 마지막 줄을 쓴다.",
    "plaza_hidden": "중앙광장 점수도 다른 건물처럼 공개 전에는 -1로 보낸다.",
    "number_tokens": "좌표는 -?숫자, 인원은 숫자만 허용한다(+3 같은 표기는 무효).",
    "enemy_base": "상대 본진 칸도 평지처럼 들어갈 수 있고 특별한 효과가 없다.",
    "output_limits": "출력 한도(턴당 64 KiB·4,096줄, 줄당 1 KiB, stderr 경기당 1 MiB) 초과는 몰수패로 처리한다.",
}

_INT = re.compile(r"-?\d+")
_POSINT = re.compile(r"\d+")


def chebyshev(a: Pos, b: Pos) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# ------------------------------------------------------------------ 명령 파싱


@dataclass
class Command:
    """명령 한 줄과 처리 결과. status: ok · partial(일부만 처리) · ignored."""

    line: str
    op: str | None = None
    args: tuple = ()
    status: str = "ok"
    note: str = ""

    def ignore(self, why: str) -> None:
        self.status, self.note = "ignored", why

    def partial(self, why: str) -> None:
        self.status, self.note = "partial", why

    def to_json(self) -> dict:
        out = {"line": self.line, "status": self.status}
        if self.note:
            out["note"] = self.note
        return out


def _int(tok: str) -> int | None:
    return int(tok) if _INT.fullmatch(tok) else None


def _posint(tok: str) -> int | None:
    return int(tok) if _POSINT.fullmatch(tok) and int(tok) > 0 else None


def parse_command(line: str) -> Command:
    """규칙서 5장의 형식 검증. 형식이 틀리면 status=ignored인 Command를 돌려준다."""
    cmd = Command(line)
    tok = line.split()
    if not tok:
        cmd.ignore("빈 줄")
        return cmd
    op = tok[0]

    def bad(why: str) -> Command:
        cmd.ignore(why)
        return cmd

    if op == "SPAWN":
        if len(tok) not in (3, 5):
            return bad("토큰 수가 3 또는 5가 아님")
        kind, n = tok[1], _posint(tok[2])
        if kind not in rules.KINDS:
            return bad("병종이 F/W/S가 아님")
        if n is None:
            return bad("인원이 양의 정수가 아님")
        at = None
        if len(tok) == 5:
            x, y = _int(tok[3]), _int(tok[4])
            if x is None or y is None:
                return bad("좌표가 정수가 아님")
            at = (x, y)
        cmd.op, cmd.args = op, (kind, n, at)
    elif op == "MOVE":
        if len(tok) != 6:
            return bad("토큰 수가 6이 아님")
        x, y, kind, n, d = _int(tok[1]), _int(tok[2]), tok[3], _posint(tok[4]), tok[5]
        if x is None or y is None:
            return bad("좌표가 정수가 아님")
        if kind not in rules.KINDS:
            return bad("병종이 F/W/S가 아님")
        if n is None:
            return bad("인원이 양의 정수가 아님")
        if d not in rules.DIRS:
            return bad("방향이 U/D/L/R이 아님")
        cmd.op, cmd.args = op, ((x, y), kind, n, d)
    elif op == "MOVE2":
        if len(tok) != 7:
            return bad("토큰 수가 7이 아님")
        x, y, kind, n, d1, d2 = _int(tok[1]), _int(tok[2]), tok[3], _posint(tok[4]), tok[5], tok[6]
        if x is None or y is None:
            return bad("좌표가 정수가 아님")
        if kind != "S":
            return bad("MOVE2는 정찰병(S) 전용")
        if n is None:
            return bad("인원이 양의 정수가 아님")
        if d1 not in rules.DIRS or d2 not in rules.DIRS:
            return bad("방향이 U/D/L/R이 아님")
        cmd.op, cmd.args = op, ((x, y), n, d1, d2)
    elif op == "TELE":
        if len(tok) != 7:
            return bad("토큰 수가 7이 아님")
        x, y, kind, n = _int(tok[1]), _int(tok[2]), tok[3], _posint(tok[4])
        tx, ty = _int(tok[5]), _int(tok[6])
        if None in (x, y, tx, ty):
            return bad("좌표가 정수가 아님")
        if kind not in rules.KINDS:
            return bad("병종이 F/W/S가 아님")
        if n is None:
            return bad("인원이 양의 정수가 아님")
        cmd.op, cmd.args = op, ((x, y), kind, n, (tx, ty))
    elif op == "PRIORITY":
        nums = [_int(t) for t in tok[1:]]
        if len(nums) % 2:
            return bad("좌표 개수가 홀수")
        if any(v is None for v in nums):
            return bad("좌표가 정수가 아님")
        cmd.op, cmd.args = op, tuple(zip(nums[0::2], nums[1::2]))
    else:
        return bad("알 수 없는 명령")
    return cmd


# ------------------------------------------------------------------ 게임


@dataclass
class TurnLog:
    turn: int
    commands: dict[str, list[Command]]
    events: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "turn": self.turn,
            "commands": {t: [c.to_json() for c in cs] for t, cs in self.commands.items()},
            "events": self.events,
        }


class Game:
    def __init__(self, spec: MapSpec):
        self.spec = spec
        self.turn = 0  # 마지막으로 처리한 턴. 봇에게 다음에 보낼 턴은 turn + 1
        self.resource = {t: rules.START_RESOURCE for t in rules.TEAMS}
        self.units: dict[UnitKey, int] = {}
        self.owner: dict[int, str | None] = {b.id: None for b in spec.buildings}
        self.just_neutral: set[int] = set()  # 이번 턴에 소유 → 중립이 된 건물 (다음 입력의 단계 1)
        self.revealed: dict[str, set[int]] = {t: set() for t in rules.TEAMS}
        self.depot_claimed: dict[str, set[int]] = {t: set() for t in rules.TEAMS}
        self.occupation = {t: 0 for t in rules.TEAMS}
        self.result: dict | None = None
        self.by_id = {b.id: b for b in spec.buildings}
        self.by_pos = {b.pos: b for b in spec.buildings}

    # -------------------------------------------------------------- 조회

    @property
    def over(self) -> bool:
        return self.result is not None

    def owned(self, team: str, kind: str | None = None) -> list:
        return [b for b in self.spec.buildings
                if self.owner[b.id] == team and (kind is None or b.kind == kind)]

    def score(self, team: str) -> int:
        return sum(b.score for b in self.owned(team))

    def count(self, team: str, kind: str, pos: Pos) -> int:
        return self.units.get((team, kind, pos), 0)

    def unit_value(self, team: str) -> int:
        return sum(n * rules.UNIT_VALUE[k] for (t, k, _), n in self.units.items() if t == team)

    def _add(self, key: UnitKey, n: int) -> None:
        total = self.units.get(key, 0) + n
        if total > 0:
            self.units[key] = total
        else:
            self.units.pop(key, None)

    # -------------------------------------------------------------- 봇에게 보낼 텍스트

    def init_text(self, team: str) -> str:
        s = self.spec
        out = [f"INIT {s.size} {s.size}", f"TEAM {team}"]
        out += [f"MAP {row}" for row in s.rows]
        out.append(f"BUILDINGS {len(s.buildings)}")
        out += [f"{b.id} {b.pos[0]} {b.pos[1]} {b.kind}" for b in s.buildings]
        out += [f"BASE {t} {s.bases[t][0]} {s.bases[t][1]}" for t in rules.TEAMS]
        out.append("END")
        return "\n".join(out) + "\n"

    def turn_text(self, team: str) -> str:
        other = rules.OTHER[team]
        order = sorted(
            self.units.items(),
            key=lambda kv: (rules.TEAMS.index(kv[0][0]), rules.KINDS.index(kv[0][1]),
                            kv[0][2][1], kv[0][2][0]),
        )
        out = [
            f"TURN {self.turn + 1}",
            f"RESOURCE {self.resource[team]} {self.resource[other]}",
            f"UNITS {len(order)}",
        ]
        out += [f"{t} {k} {x} {y} {n}" for (t, k, (x, y)), n in order]
        out.append(f"BUILDINGS {len(self.spec.buildings)}")
        for b in self.spec.buildings:
            owner = self.owner[b.id]
            stage = 2 if owner else (1 if b.id in self.just_neutral else 0)
            score = b.score if b.id in self.revealed[team] else -1
            out.append(f"{b.id} {b.pos[0]} {b.pos[1]} {b.kind} {owner or 'N'} {stage} {score}")
        out.append("END")
        return "\n".join(out) + "\n"

    # -------------------------------------------------------------- 한 턴

    def step(self, lines: dict[str, list[str]]) -> TurnLog:
        """양 팀 명령 줄(END 제외)을 받아 한 턴을 처리한다."""
        if self.over:
            raise RuntimeError("이미 끝난 경기")
        self.turn += 1
        self.just_neutral.clear()
        log = TurnLog(self.turn, {t: [parse_command(ln) for ln in lines.get(t, [])]
                                  for t in rules.TEAMS})
        ev = log.events
        self._produce(log.commands, ev)
        self._move(log.commands, ev)
        self._combat(ev)
        self._income(ev)
        self._capture(log.commands, ev)
        self._reveal()
        self._judge()
        return log

    def forfeit(self, reasons: dict[str, str]) -> None:
        """시간 초과·비정상 종료·END 누락 등. 양 팀 동시면 무승부."""
        losers = sorted(reasons)
        winner = None if len(losers) == 2 else rules.OTHER[losers[0]]
        self._finish(winner, "forfeit", detail=reasons)

    # 2. 생산 ---------------------------------------------------------

    def _produce(self, commands: dict[str, list[Command]], ev: list[dict]) -> None:
        for team in rules.TEAMS:
            eng = len(self.owned(team, "ENG"))
            cost = dict(rules.UNIT_COST)
            cost["W"] = max(rules.ENG_COST_FLOOR, rules.UNIT_COST["W"] - eng * rules.ENG_DISCOUNT)
            hospitals = {b.pos for b in self.owned(team, "HOSPITAL")}
            for cmd in commands[team]:
                if cmd.op != "SPAWN":
                    continue
                kind, n, at = cmd.args
                if at is not None and at not in hospitals:
                    cmd.ignore("좌표가 내 병원이 아님 (본진은 좌표를 생략)")
                    continue
                pos = at or self.spec.bases[team]
                made = min(n, self.resource[team] // cost[kind])
                if made == 0:
                    cmd.ignore(f"자원 부족 (보유 {self.resource[team]}, 비용 {cost[kind]})")
                    continue
                if made < n:
                    cmd.partial(f"자원 부족으로 {made}/{n}명만 생산")
                self.resource[team] -= made * cost[kind]
                self._add((team, kind, pos), made)
                ev.append({"type": "spawn", "team": team, "kind": kind, "n": made, "pos": pos})

    # 3. 이동 ---------------------------------------------------------

    def _move(self, commands: dict[str, list[Command]], ev: list[dict]) -> None:
        moved: dict[UnitKey, int] = {}
        for team in rules.TEAMS:
            # 이동 전부터 있던(생산 포함) 인원만 움직일 수 있다. 이번 턴 도착한 인원은 다시 못 움직인다
            ready = {(k, p): n for (t, k, p), n in self.units.items() if t == team}
            arrived: dict[tuple[str, Pos], int] = defaultdict(int)
            stations = {b.pos for b in self.owned(team, "STATION")}
            tele_used = False
            for cmd in commands[team]:
                if cmd.op == "MOVE":
                    src, kind, n, d = cmd.args
                    dst = (src[0] + rules.DIRS[d][0], src[1] + rules.DIRS[d][1])
                    if not self.spec.passable(dst):
                        cmd.ignore("도착 칸이 장애물이거나 맵 밖")
                        continue
                    k = self._take(ready, src, kind, n)
                    if not self._note_taken(cmd, k, n):
                        continue
                    arrived[(kind, dst)] += k
                    ev.append({"type": "move", "team": team, "kind": kind, "n": k,
                               "path": [src, dst]})
                elif cmd.op == "MOVE2":
                    src, n, d1, d2 = cmd.args
                    via = (src[0] + rules.DIRS[d1][0], src[1] + rules.DIRS[d1][1])
                    dst = (via[0] + rules.DIRS[d2][0], via[1] + rules.DIRS[d2][1])
                    if not (self.spec.passable(via) and self.spec.passable(dst)):
                        cmd.ignore("경유 또는 도착 칸이 장애물이거나 맵 밖")
                        continue
                    k = self._take(ready, src, "S", n)
                    if not self._note_taken(cmd, k, n):
                        continue
                    arrived[("S", dst)] += k
                    ev.append({"type": "move", "team": team, "kind": "S", "n": k,
                               "path": [src, via, dst]})
                elif cmd.op == "TELE":
                    src, kind, n, dst = cmd.args
                    if tele_used:
                        cmd.ignore("이번 턴 TELE를 이미 사용함")
                        continue
                    if len(stations) < rules.TELE_MIN_STATIONS:
                        cmd.ignore("내 역이 2개 미만")
                        continue
                    if src not in stations or dst not in stations:
                        cmd.ignore("출발 또는 도착이 내 역이 아님")
                        continue
                    if src == dst:
                        cmd.ignore("출발과 도착이 같은 역")
                        continue
                    k = self._take(ready, src, kind, min(n, rules.TELE_MAX_UNITS))
                    if not self._note_taken(cmd, k, n):
                        continue  # 0명 이동은 횟수를 소모하지 않는다
                    tele_used = True
                    arrived[(kind, dst)] += k
                    ev.append({"type": "tele", "team": team, "kind": kind, "n": k,
                               "path": [src, dst]})
            for (kind, pos), n in ready.items():
                moved[(team, kind, pos)] = moved.get((team, kind, pos), 0) + n
            for (kind, pos), n in arrived.items():
                moved[(team, kind, pos)] = moved.get((team, kind, pos), 0) + n
        self.units = {key: n for key, n in moved.items() if n > 0}

    @staticmethod
    def _take(ready: dict, src: Pos, kind: str, n: int) -> int:
        k = min(n, ready.get((kind, src), 0))
        if k:
            ready[(kind, src)] -= k
        return k

    @staticmethod
    def _note_taken(cmd: Command, k: int, n: int) -> bool:
        if k == 0:
            cmd.ignore("그 칸에 움직일 수 있는 해당 병종이 없음 (이번 턴 도착한 인원 제외)")
            return False
        if k < n:
            cmd.partial(f"{k}/{n}명만 이동")
        return True

    # 4. 전투 ---------------------------------------------------------

    def _combat(self, ev: list[dict]) -> None:
        cells: dict[Pos, set[str]] = defaultdict(set)
        for (t, _, p) in self.units:
            cells[p].add(t)
        for pos in sorted(p for p, teams in cells.items() if len(teams) == 2):
            before = {t: {k: self.count(t, k, pos) for k in rules.KINDS} for t in rules.TEAMS}
            wy, wk = before["Y"]["W"], before["K"]["W"]
            if wy == 0 and wk == 0:
                ev.append({"type": "standoff", "pos": pos, "before": before})
                continue
            m = min(wy, wk)
            left = {"Y": wy - m, "K": wk - m}
            for t in rules.TEAMS:
                self._add((t, "W", pos), -m)
            for t in rules.TEAMS:
                if left[t] > 0:
                    loser = rules.OTHER[t]
                    had_flag = self.count(loser, "F", pos) > 0
                    self.units.pop((loser, "F", pos), None)
                    self.units.pop((loser, "S", pos), None)
                    b = self.by_pos.get(pos)
                    if had_flag and b and self.owner[b.id] == loser:
                        self.owner[b.id] = None  # 깃발 뽑힘
                        self.just_neutral.add(b.id)
                        ev.append({"type": "flag_pulled", "team": loser, "pos": pos, "id": b.id})
            after = {t: {k: self.count(t, k, pos) for k in rules.KINDS} for t in rules.TEAMS}
            ev.append({"type": "combat", "pos": pos, "before": before, "after": after})

    # 5·6. 건물 효과 · 수입 ------------------------------------------

    def _income(self, ev: list[dict]) -> None:
        for team in rules.TEAMS:
            gain = rules.BASE_INCOME + rules.HALL_BONUS * len(self.owned(team, "HALL"))
            self.resource[team] = min(rules.RESOURCE_CAP, self.resource[team] + gain)

    # 7. 점령 ---------------------------------------------------------

    def _capture(self, commands: dict[str, list[Command]], ev: list[dict]) -> None:
        library = {t: bool(self.owned(t, "LIBRARY")) for t in rules.TEAMS}  # 단계 진입 시점으로 고정
        newly: dict[str, list] = {t: [] for t in rules.TEAMS}
        contested_logged: set[Pos] = set()
        for team in rules.TEAMS:
            other = rules.OTHER[team]
            targets = []
            for b in self.spec.buildings:
                if self.count(team, "F", b.pos) == 0 or self.owner[b.id] == team:
                    continue
                if self.count(other, "F", b.pos) > 0:
                    if b.pos not in contested_logged:
                        contested_logged.add(b.pos)
                        ev.append({"type": "contested", "pos": b.pos, "id": b.id})
                    continue
                targets.append(b)
            for b in self._capture_order(team, targets, commands[team]):
                base = rules.CAPTURE_COST * (rules.PLAZA_MULTIPLIER if b.kind == "PLAZA" else 1)
                cost = max(rules.MIN_CAPTURE_COST,
                           base - (rules.LIBRARY_DISCOUNT if library[team] else 0))
                if self.resource[team] < cost:
                    ev.append({"type": "capture_blocked", "team": team, "pos": b.pos, "id": b.id,
                               "cost": cost, "have": self.resource[team]})
                    continue
                self.resource[team] -= cost
                if self.owner[b.id] == other:
                    self.owner[b.id] = None
                    self.just_neutral.add(b.id)
                    ev.append({"type": "neutralize", "team": team, "pos": b.pos, "id": b.id,
                               "cost": cost})
                else:
                    self.owner[b.id] = team
                    self.just_neutral.discard(b.id)
                    newly[team].append(b)
                    ev.append({"type": "capture", "team": team, "pos": b.pos, "id": b.id,
                               "cost": cost})
        # 보급소 보너스는 모든 점령이 끝난 뒤
        for team in rules.TEAMS:
            for b in newly[team]:
                if b.kind == "DEPOT" and b.id not in self.depot_claimed[team]:
                    self.depot_claimed[team].add(b.id)
                    self.resource[team] = min(rules.RESOURCE_CAP,
                                              self.resource[team] + rules.DEPOT_BONUS)
                    ev.append({"type": "depot_bonus", "team": team, "pos": b.pos, "id": b.id})
        for team in rules.TEAMS:
            self.occupation[team] += self.score(team)

    def _capture_order(self, team: str, targets: list, commands: list[Command]) -> list:
        prio: tuple[Pos, ...] = ()
        prio_cmds = [c for c in commands if c.op == "PRIORITY"]
        for c in prio_cmds[:-1]:
            c.ignore("뒤에 나온 PRIORITY가 우선")
        if prio_cmds:
            prio = prio_cmds[-1].args
        by_pos = {b.pos: b for b in targets}
        first = []
        for pos in prio:
            b = by_pos.pop(pos, None)  # 중복·건물 아님·점령 대상 아님은 무시
            if b is not None:
                first.append(b)

        def default_key(b):
            known = b.score if b.id in self.revealed[team] else 0
            x, y = b.pos
            norm = (y, x) if team == "Y" else (rules.SIZE - 1 - y, rules.SIZE - 1 - x)
            return (-known, norm)

        return first + sorted(by_pos.values(), key=default_key)

    # 8. 정보 공개 ----------------------------------------------------

    def _reveal(self) -> None:
        for team in rules.TEAMS:
            here = {p for (t, _, p) in self.units if t == team}
            scouts = [p for (t, k, p) in self.units if t == team and k == "S"]
            watches = [b.pos for b in self.owned(team, "WATCH")]
            for b in self.spec.buildings:
                if b.id in self.revealed[team]:
                    continue
                if (b.pos in here
                        or any(chebyshev(b.pos, s) <= rules.SCOUT_RANGE for s in scouts)
                        or any(chebyshev(b.pos, w) <= rules.WATCH_RANGE for w in watches)):
                    self.revealed[team].add(b.id)

    # 9. 승리 판정 ----------------------------------------------------

    def _judge(self) -> None:
        total = self.spec.total_score
        score = {t: self.score(t) for t in rules.TEAMS}
        for team in rules.TEAMS:
            if score[rules.OTHER[team]] == 0 and score[team] * 2 > total:
                self._finish(team, "instant")
                return
        if self.turn < rules.TOTAL_TURNS:
            return
        value = {t: self.unit_value(t) for t in rules.TEAMS}
        for reason, metric in (("score", score), ("occupation", self.occupation),
                               ("units", value)):
            if metric["Y"] != metric["K"]:
                self._finish("Y" if metric["Y"] > metric["K"] else "K", reason)
                return
        self._finish(None, "draw")

    def _finish(self, winner: str | None, reason: str, detail: dict | None = None) -> None:
        self.result = {
            "winner": winner,
            "reason": reason,
            "turn": self.turn,
            "score": {t: self.score(t) for t in rules.TEAMS},
            "occupation": dict(self.occupation),
            "unit_value": {t: self.unit_value(t) for t in rules.TEAMS},
        }
        if detail:
            self.result["detail"] = detail

    # -------------------------------------------------------------- 리플레이용

    def snapshot(self) -> dict:
        """이 턴 처리가 끝난 뒤의 전체 상태 (관전자 시점: 실제 점수 포함)."""
        return {
            "turn": self.turn,
            "resource": dict(self.resource),
            "units": [[t, k, p[0], p[1], n] for (t, k, p), n in sorted(self.units.items())],
            "owner": [self.owner[b.id] for b in self.spec.buildings],
            "just_neutral": sorted(self.just_neutral),
            "revealed": {t: sorted(self.revealed[t]) for t in rules.TEAMS},
            "score": {t: self.score(t) for t in rules.TEAMS},
            "occupation": dict(self.occupation),
            "unit_value": {t: self.unit_value(t) for t in rules.TEAMS},
        }
