"""시뮬레이터가 실제 경기 환경과 맞물리는지 확인한다.

- 입출력: 운영진 스타터 킷의 파서(campus_bot)가 엔진이 만든 블록을 그대로 읽는다
- 공정성: 진영 기준으로 정규화된 스타터 봇끼리 붙이면 점대칭 맵에서 매 턴 상태가 점대칭이고 무승부
- 몰수: flush 누락 · END 누락 · 시간 초과 · 조기 종료를 서버처럼 몰수패로 처리
"""

import io
import sys
import textwrap
from pathlib import Path

import pytest

from agent import adapter
from sim import bots, mapgen, match, rules
from sim.engine import Game
from sim.mapgen import mirror

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "starter"))
import campus_bot
import example_lv1
import example_lv2


def blocks(text: str) -> list[str]:
    return campus_bot.read_block(io.StringIO(text))


def test_starter_parser_reads_engine_blocks():
    g = Game(mapgen.generate(4))
    g.units[("Y", "F", (3, 3))] = 2
    g.units[("K", "S", (10, 9))] = 1
    g.owner[0] = "K"
    g.revealed["Y"].add(0)
    for team in rules.TEAMS:
        init = campus_bot.parse_init(blocks(g.init_text(team)))
        assert init.team == team and init.bases == g.spec.bases
        assert ["".join(r) for r in init.terrain] == list(g.spec.rows)
        assert [(b["id"], (b["x"], b["y"]), b["type"]) for b in init.buildings] == \
               [(b.id, b.pos, b.kind) for b in g.spec.buildings]
        view = campus_bot.parse_turn(blocks(g.turn_text(team)), init)
        assert view.turn == 1 and view.my_resource == 10
        assert {(u["team"], u["kind"], u["x"], u["y"], u["count"]) for u in view.units} == \
               {("Y", "F", 3, 3, 2), ("K", "S", 10, 9, 1)}
        b0 = view.buildings[0]
        assert b0["owner"] == "K" and b0["stage"] == 2
        assert b0["score"] == (g.spec.buildings[0].score if team == "Y" else -1)
        # 우리 adapter도 같은 블록을 읽는다
        game_map, me = adapter.parse_init(blocks(g.init_text(team)))
        world = adapter.parse_turn(blocks(g.turn_text(team)), game_map, me)
        assert world.me == team and len(world.buildings) == 17


def play_inprocess(seed: int, decide) -> list[Game]:
    """스타터 decide(view, init)를 프로세스 없이 양쪽에 붙여 한 판. 매 턴 상태를 검사할 수 있게."""
    g = Game(mapgen.generate(seed))
    inits = {t: campus_bot.parse_init(blocks(g.init_text(t))) for t in rules.TEAMS}
    while not g.over:
        cmds = {t: decide(campus_bot.parse_turn(blocks(g.turn_text(t)), inits[t]), inits[t])
                for t in rules.TEAMS}
        g.step(cmds)
        yield g


def assert_mirrored(g: Game) -> None:
    for (t, k, p), n in g.units.items():
        assert g.units.get((rules.OTHER[t], k, mirror(p))) == n, (g.turn, t, k, p)
    for b in g.spec.buildings:
        twin = g.by_pos[mirror(b.pos)]
        o = g.owner[b.id]
        assert g.owner[twin.id] == (rules.OTHER[o] if o else None), (g.turn, b)
    assert g.resource["Y"] == g.resource["K"]
    assert g.occupation["Y"] == g.occupation["K"]


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("decide", [example_lv1.decide, example_lv2.decide], ids=["lv1", "lv2"])
def test_self_play_is_point_symmetric(seed, decide):
    g = None
    for g in play_inprocess(seed, decide):
        assert_mirrored(g)
    assert g.result["winner"] is None and g.result["reason"] == "draw"
    assert g.turn == rules.TOTAL_TURNS


# ------------------------------------------------------------------ 봇 프로세스


def test_our_main_vs_starter_full_game():
    spec = mapgen.generate(11)
    pair = {"Y": bots.resolve(str(ROOT)), "K": bots.resolve("starter:example_lv2")}
    replay = match.play(spec, pair)
    res = replay["result"]
    assert "detail" not in res, res  # 몰수 없음
    assert res["ignored_commands"] == {"Y": 0, "K": 0}
    assert len(replay["frames"]) == res["turn"] + 1


def write_bot(tmp_path: Path, name: str, body: str) -> bots.BotSpec:
    path = tmp_path / f"{name}.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return bots.resolve(str(path))


GOOD = """
    import sys
    def block():
        lines = []
        for line in sys.stdin:
            if line.strip() == "END":
                return lines
            lines.append(line)
        return None
    block()
    turn = 0
    while block() is not None:
        turn += 1
        {body}
"""


@pytest.mark.parametrize("name, body, why", [
    ("noflush", 'sys.stdout.write("END\\n")', "시간 초과"),
    ("noend", 'print("SPAWN F 1", flush=True)', "시간 초과"),
    ("slow", 'import time; time.sleep(0.2 if turn == 3 else 0); print("END", flush=True)',
     "시간 초과"),
    ("quits", 'print("END", flush=True); sys.exit(0) if turn == 2 else None',
     "END 전에 프로세스 종료"),
    ("crash", 'print("END", flush=True); 1 / 0 if turn == 2 else None',
     "END 전에 프로세스 종료"),
])
def test_misbehaving_bot_forfeits(tmp_path, name, body, why):
    bad = write_bot(tmp_path, name, GOOD.replace("{body}", body))
    pair = {"Y": bots.resolve("starter:example_lv1"), "K": bad}
    # 시간 제한을 0.3배로(첫 턴 900 ms, 이후 90 ms) 줄여 테스트를 빨리 끝낸다
    replay = match.play(mapgen.generate(0), pair, time_scale=0.3)
    res = replay["result"]
    assert res["reason"] == "forfeit" and res["winner"] == "Y"
    assert why in res["detail"]["K"]


def test_both_forfeit_is_draw(tmp_path):
    bad = write_bot(tmp_path, "noend", GOOD.replace("{body}", "pass"))
    replay = match.play(mapgen.generate(0), {"Y": bad, "K": bad}, time_scale=0.3)
    assert replay["result"]["winner"] is None and replay["result"]["reason"] == "forfeit"


def test_stderr_is_collected_per_turn(tmp_path):
    bot = write_bot(tmp_path, "chatty", GOOD.replace(
        "{body}", 'print("t", turn, file=sys.stderr, flush=True); print("END", flush=True)'))
    replay = match.play(mapgen.generate(0), {"Y": bot, "K": bots.resolve("starter:example_lv1")})
    said = "".join(t.get("stderr", {}).get("Y", "") for t in replay["turns"])
    assert "t 1" in said and "t 2" in said


def test_git_ref_bot_runs():
    spec = bots.resolve("git:HEAD")
    assert (Path(spec.cwd) / "main.py").exists() and (Path(spec.cwd) / "agent").is_dir()
    res = match.play(mapgen.generate(2), {"Y": spec, "K": bots.resolve("starter:example_lv1")},
                     record=False)["result"]
    assert "detail" not in res
