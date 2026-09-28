"""우리 adapter·world·algorithms 위에 옮긴 lv2(tests/lv2_port.py)가 스타터 킷 example_lv2와
같은 입력에 같은 명령을 내는지 확인한다. 전략이 아니라 우리 입출력·경로 탐색이 스타터와 같은지 보는 테스트다.
"""

import io
import sys
from pathlib import Path

import pytest
from fake_input import random_game
from lv2_port import decide

from agent import adapter

STARTER = Path(__file__).resolve().parent.parent / "starter"
sys.path.insert(0, str(STARTER))
import campus_bot
import example_lv2


def starter_outputs(text: str) -> list[list[str]]:
    stream = io.StringIO(text)
    init = campus_bot.parse_init(campus_bot.read_block(stream))
    turns = []
    while (block := campus_bot.read_block(stream)) is not None:
        turns.append(example_lv2.decide(campus_bot.parse_turn(block, init), init))
    return turns


def our_outputs(text: str) -> list[list[str]]:
    stream = io.StringIO(text)
    game_map, me = adapter.parse_init(adapter.read_block(stream))
    turns = []
    while (block := adapter.read_block(stream)) is not None:
        world = adapter.parse_turn(block, game_map, me)
        turns.append([adapter.to_line(a) for a in decide(world)])
    return turns


@pytest.mark.parametrize("seed", range(200))
def test_same_commands_as_example_lv2(seed):
    text = random_game(seed, turns=5)
    assert our_outputs(text) == starter_outputs(text)
