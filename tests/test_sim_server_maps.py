"""서버 리플레이(data/server-replays)에서 뽑은 맵이 규칙서 1장 조건을 지키고, 시뮬레이터에서 한 판이 끝까지 돌아가는지."""

import sys
from collections import deque
from pathlib import Path

import pytest

from sim import bots, mapgen, match, rules
from sim.mapgen import mirror

ROOT = Path(__file__).resolve().parent.parent
REPLAYS = ROOT / "data" / "server-replays"
SERVER_MAPS = mapgen.load_server_maps(REPLAYS)
sys.path.insert(0, str(ROOT / "starter"))


def test_same_terrain_replays_become_one_map():
    # 2026-09-27 모의 전투: 중·상 봇 19경기가 같은 10개 맵을 썼다
    assert len(SERVER_MAPS) == 10


@pytest.mark.parametrize(("name", "spec"), SERVER_MAPS, ids=[n for n, _ in SERVER_MAPS])
def test_server_map_follows_rules(name, spec):
    size = rules.SIZE
    assert spec.size == size
    for y in range(size):
        for x in range(size):
            mx, my = mirror((x, y))
            assert (spec.rows[y][x] == "#") == (spec.rows[my][mx] == "#")
    assert len(spec.buildings) == 17
    by_pos = {b.pos: b for b in spec.buildings}
    for b in spec.buildings:
        twin = by_pos[mirror(b.pos)]
        assert twin.kind == b.kind and twin.score == b.score
        assert 1 <= b.score <= 4
    assert by_pos[(7, 7)].kind == "PLAZA" and by_pos[(7, 7)].score == rules.PLAZA_SCORE
    assert spec.total_score % 2 == 1
    assert spec.bases["K"] == mirror(spec.bases["Y"])
    seen = {spec.bases["Y"]}
    queue = deque(seen)
    while queue:
        x, y = queue.popleft()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt not in seen and spec.passable(nxt):
                seen.add(nxt)
                queue.append(nxt)
    assert {b.pos for b in spec.buildings} | {spec.bases["K"]} <= seen


def test_single_replay_file_gives_the_same_map():
    name, spec = SERVER_MAPS[0]
    one = mapgen.from_server_replay(REPLAYS / name)
    assert one.rows == spec.rows and one.bases == spec.bases and one.buildings == spec.buildings


def test_match_runs_on_server_map():
    _, spec = SERVER_MAPS[0]
    pair = {"Y": bots.resolve("starter:example_lv2"), "K": bots.resolve("starter:example_lv1")}
    result = match.play(spec, pair, time_scale=None, record=False)["result"]
    assert result["reason"] in {"instant", "score", "occupation", "draw", "survivors"}
    assert not result.get("detail")
