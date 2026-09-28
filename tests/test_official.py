"""시뮬레이터가 운영진 공식 개발도구(devtool/)와 같은지 확인한다.

- 맵: 공개 시드 맵의 실제 점수가 INIT 블록에 들어간다
- 입출력: 우리 엔진이 봇에게 보내는 INIT·TURN 블록이 공식 직렬화와 글자까지 같다
- 엔진: 같은 명령 줄을 두 엔진에 넣으면 매 턴 상태(유닛·자원·소유·단계·공개 점수)와 결과가 같다.
  명령은 스타터 봇, 우리 봇, 그리고 규칙 경계를 두드리는 무작위 명령(잘못된 줄 포함)에서 뽑는다.

알려진 차이 하나는 일부러 비교하지 않는다: 공식 파서는 int()로 숫자를 읽어 `+3`, `1_0`도 받지만
우리 파서는 무효로 본다. 봇이 그런 표기를 낼 일이 없어 그대로 둔다.
"""

import hashlib
import io
import json
import random
import sys
from pathlib import Path

import pytest

from agent import adapter
from agent.strategy import decide as our_decide
from sim import mapgen, official, rules
from sim.engine import Game

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "starter"))
import campus_bot
import example_lv1
import example_lv2

REASON = {"occupation_turns": "occupation"}  # 공식 결과 사유 → 우리 이름


def blocks(text: str) -> list[str]:
    return campus_bot.read_block(io.StringIO(text))


# ------------------------------------------------------------------ devtool 원본


def test_devtool_is_unmodified():
    """devtool/은 배포본 그대로 둔다. 운영진이 해시를 적어 둔 파일로 확인한다."""
    provenance = json.loads(
        (official.DEVTOOL / "docs" / "platform-sdk-provenance.json").read_text(encoding="utf-8"))
    for name, digest in provenance["modifiedFiles"].items():
        data = (official.DEVTOOL / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest["after"], name


def test_official_config_matches_starter_balance():
    import _generated
    assert official.config() == _generated.BALANCE


# ------------------------------------------------------------------ 맵


def test_public_scores_fill_server_init_block():
    m = mapgen.generate(3)
    init = Game(m).init_text("Y")
    assert mapgen.from_init(init, seed=99).buildings == m.buildings
    assert mapgen.public_scores(("." * 15,) * 15) is None


# ------------------------------------------------------------------ 엔진


def assert_same(g: Game, state, result) -> None:
    for team in rules.TEAMS:
        assert g.turn_text(team) == official.protocol().serialize_turn(state, team, g.turn + 1), (
            g.turn, team)
    assert g.occupation == state.occupation_score_turns, g.turn
    if result is None:
        assert not g.over, (g.turn, g.result)
        return
    assert g.over, (g.turn, result)
    winner = None if result["winner"] == "DRAW" else result["winner"]
    assert (g.result["winner"], g.result["reason"], g.result["score"]) == (
        winner, REASON.get(result["reason"], result["reason"]), result["score"]), g.turn


def play_both(seed: int, choose, inject=None) -> Game:
    """같은 시드에서 두 엔진을 나란히 돌린다. choose(game, team) → 그 팀 명령 줄 목록.

    inject(game, put)를 주면 매 턴 명령 전에 불린다. put(team, kind, pos, n)은 두 엔진에 같은 유닛을 놓는다.
    """
    g = Game(mapgen.generate(seed))
    state = official.new_state(seed)
    for team in rules.TEAMS:
        assert g.init_text(team) == official.protocol().serialize_init(state, team)

    def put(team, kind, pos, n):
        g.units[(team, kind, pos)] = g.units.get((team, kind, pos), 0) + n
        state.add_unit(pos[0], pos[1], team, kind, n)

    result = None
    while result is None:
        if inject:
            inject(g, put)
        assert_same(g, state, None)
        lines = {t: choose(g, t) for t in rules.TEAMS}
        g.step(lines)
        state, result = official.run_turn(state, lines["Y"], lines["K"])
        assert_same(g, state, result)
    return g


def starter(decide_y, decide_k):
    inits = {}
    decides = {"Y": decide_y, "K": decide_k}

    def choose(g: Game, team: str) -> list[str]:
        if team not in inits:
            inits[team] = campus_bot.parse_init(blocks(g.init_text(team)))
        view = campus_bot.parse_turn(blocks(g.turn_text(team)), inits[team])
        return list(decides[team](view, inits[team]))

    return choose


def ours_vs(decide_other):
    """Y는 우리 봇(agent), K는 스타터 봇."""
    other = starter(None, decide_other)
    maps = {}

    def choose(g: Game, team: str) -> list[str]:
        if team == "K":
            return other(g, team)
        if team not in maps:
            maps[team] = adapter.parse_init(blocks(g.init_text(team)))
        game_map, me = maps[team]
        world = adapter.parse_turn(blocks(g.turn_text(team)), game_map, me)
        return [adapter.to_line(a) for a in our_decide(world)]

    return choose


@pytest.mark.parametrize("seed", mapgen.PUBLIC_SEEDS)
def test_engine_matches_official_starter_games(seed):
    play_both(seed, starter(example_lv2.decide, example_lv1.decide))


@pytest.mark.parametrize("seed", mapgen.PUBLIC_SEEDS)
def test_engine_matches_official_our_bot(seed):
    play_both(seed, ours_vs(example_lv2.decide))


def fuzzer(seed: int):
    """규칙 경계를 두드리는 무작위 명령. 깃발병을 건물 쪽으로 몰아 점령·역·병원·도서관 상황을 만든다."""
    rng = random.Random(seed)
    garbage = ["SPAWN F 1 junk", "MOVE 0 7 F 1 R EXTRA", "MOVE2 0 7 W 1 R R", "PRIORITY 1 2 3",
               "SPAWN F 0", "SPAWN X 1", "MOVE 1 1 F -1 U", "TELE 1 1 F 1 2", "HELLO", "END"]

    def toward(src, dst):
        options = []
        if dst[0] != src[0]:
            options.append("R" if dst[0] > src[0] else "L")
        if dst[1] != src[1]:
            options.append("D" if dst[1] > src[1] else "U")
        return rng.choice(options or list(rules.DIRS))

    def choose(g: Game, team: str) -> list[str]:
        spec = g.spec
        buildings = [b.pos for b in spec.buildings]
        stations = [b.pos for b in spec.buildings if b.kind == "STATION"]
        out = []
        for _ in range(rng.randint(0, 3)):
            kind = rng.choice("FFWWS")
            n = rng.randint(1, 4)
            r = rng.random()
            if r < 0.15:  # 병원(또는 아무 건물) 좌표 생산
                x, y = rng.choice([b.pos for b in spec.buildings if b.kind == "HOSPITAL"]
                                  + buildings[:3])
                out.append(f"SPAWN {kind} {n} {x} {y}")
            elif r < 0.2:  # 본진 좌표 명시 → 무시돼야 한다
                x, y = spec.bases[team]
                out.append(f"SPAWN {kind} {n} {x} {y}")
            else:
                out.append(f"SPAWN {kind} {n}")
        stacks = [(k, p, n) for (t, k, p), n in g.units.items() if t == team]
        rng.shuffle(stacks)
        for kind, (x, y), n in stacks:
            r = rng.random()
            count = rng.randint(1, n + 1)  # 가끔 가진 것보다 많이
            if (x, y) in stations and r < 0.3:
                tx, ty = rng.choice(stations)
                out.append(f"TELE {x} {y} {kind} {rng.randint(1, 7)} {tx} {ty}")
            elif kind == "S" and r < 0.6:
                out.append(f"MOVE2 {x} {y} S {count} {rng.choice('UDLR')} {rng.choice('UDLR')}")
            elif r < 0.85:
                if kind == "F" and (x, y) in buildings and rng.random() < 0.5:
                    continue  # 점령하도록 잠시 머문다
                d = toward((x, y), rng.choice(buildings)) if rng.random() < 0.8 else \
                    rng.choice("UDLR")
                out.append(f"MOVE {x} {y} {kind} {count} {d}")
        if rng.random() < 0.3:
            coords = [c for p in rng.sample(buildings, rng.randint(1, 6)) for c in p]
            if rng.random() < 0.1:
                coords.append(1)  # 홀수 → 줄 전체 무시
            out.append("PRIORITY " + " ".join(map(str, coords)))
        if rng.random() < 0.1:
            out.append(rng.choice(garbage))
        rng.shuffle(out)
        return out

    return choose


@pytest.mark.parametrize("seed", range(30))
def test_engine_matches_official_random_commands(seed):
    g = play_both(seed, fuzzer(seed))
    assert g.turn >= 1


@pytest.mark.parametrize("seed", range(20))
def test_engine_matches_official_capture_shortage(seed):
    """점령 자원이 모자랄 때의 순서(7장): PRIORITY, 공개 점수 높은 순, 자기 본진 기준 정규화 좌표.

    무작위 명령만으로는 점령 단계 자원이 늘 10 이상이라 부족 상황이 안 생긴다. 1턴에 정찰병으로 점수를
    공개하고, 2·5턴에 깃발병을 여러 건물에 놓은 뒤 생산으로 자원을 비운다. 5턴에는 상대 소유 건물에도
    깃발병을 놓아 중립화 단계와 섞는다.
    """
    rng = random.Random(seed)
    fuzz = fuzzer(seed)

    def inject(g: Game, put):
        buildings = g.spec.buildings
        if g.turn == 0:
            for b in buildings:
                if rng.random() < 0.7:
                    for team in rules.TEAMS:
                        put(team, "S", b.pos, 1)
        if g.turn in (1, 4):
            for b in buildings:
                r = rng.random()
                team = "Y" if r < 0.45 else "K" if r < 0.9 else None
                if team:
                    put(team, "F", b.pos, 1)
                    if rng.random() < 0.1:  # 가끔 경합
                        put(rules.OTHER[team], "F", b.pos, 1)

    def choose(g: Game, team: str) -> list[str]:
        if g.turn >= 8:
            return fuzz(g, team)
        out = [f"SPAWN {rng.choice('FWS')} 20"]  # 자원을 비운다(생산은 수입보다 먼저)
        if rng.random() < 0.5:
            picks = rng.sample([b.pos for b in g.spec.buildings], rng.randint(1, 8))
            out.append("PRIORITY " + " ".join(f"{x} {y}" for x, y in picks))
        return out

    play_both(seed, choose, inject)
