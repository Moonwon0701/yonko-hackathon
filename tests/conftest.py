"""모든 테스트를 막 시작한 봇 상태에서 돌린다.

봇은 한 프로세스 = 한 경기라 턴을 넘는 기억(지난 소유자, 국면 Latch, 기동대 전환 기록 등)과 학습 층이 바꿔 둔 상수를
모듈 전역에 둔다. 테스트는 한 프로세스에서 여러 경기(test_official)와 여러 장면을 이어 돌리므로, 앞 테스트가 남긴 값이
뒤 테스트의 판단을 바꾼다(10/1 hunters 코드를 넣은 뒤 test_strategy 2개가 전체 실행에서만 실패). 테스트마다 import 직후
값으로 되돌린다.
"""

import copy
import types

import pytest

from agent import forecast, learned, strategy

_MODULES = (strategy, learned, forecast)


def _state(mod: types.ModuleType) -> dict:
    return {k: v for k, v in vars(mod).items()
            if not k.startswith("__") and not isinstance(v, (types.ModuleType, types.FunctionType, type))}


_FRESH = {mod: copy.deepcopy(_state(mod)) for mod in _MODULES}


@pytest.fixture(autouse=True)
def fresh_bot_state():
    for mod, saved in _FRESH.items():
        for name, value in saved.items():
            setattr(mod, name, copy.deepcopy(value))
    yield
