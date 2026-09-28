"""운영진 공식 개발도구(devtool/)를 불러오는 유일한 창구.

devtool/은 운영진이 2026-09-27에 배포한 dev_tool.zip을 그대로 푼 것이다(고치지 않는다, CLAUDE.md).
공식 코드는 `engine`, `mapgen` 같은 최상위 패키지 이름을 쓰므로, sys.path에 devtool/을 넣는 일을
여기서만 한다. sim의 다른 모듈은 이 파일의 함수만 쓴다.

- 맵: 공식 mapgen으로 만든다. 서버 모의 전투 맵은 공개 시드 0~9와 지형·점수가 똑같았다(9/27 확인).
  리더보드·최종 평가는 매 경기 랜덤 시드 맵이다.
- 엔진: sim/engine.py가 공식 engine과 매 턴 같은 상태를 내는지 tests/test_official.py가 비교한다.
  sim은 뷰어용 명령 처리 결과(무시·일부 처리 사유)가 필요해 우리 엔진으로 경기를 돌린다.
"""

from __future__ import annotations

import importlib.util
import sys
from functools import cache
from pathlib import Path

DEVTOOL = Path(__file__).resolve().parent.parent / "devtool"

if str(DEVTOOL) not in sys.path:
    sys.path.insert(0, str(DEVTOOL))

from engine import pipeline  # devtool/engine
from engine.config import load_config
from mapgen import generator  # devtool/mapgen


@cache
def config() -> dict:
    """공식 config/balance.json."""
    return load_config()


@cache
def protocol():
    """devtool/runner/protocol.py (명령 파싱·입력 블록 직렬화).

    `import runner.protocol`은 runner/__init__.py를 거쳐 봇 프로세스 코드와 스타터 파서까지
    불러오므로, 이 파일 하나만 경로로 읽는다.
    """
    spec = importlib.util.spec_from_file_location(
        "official_protocol", DEVTOOL / "runner" / "protocol.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate(seed: int):
    """공식 mapgen.generate. 돌려주는 값은 공식 GameMap."""
    return generator.generate(seed, config())


def new_state(seed: int):
    """그 시드 맵의 공식 초기 GameState."""
    return generator.to_state(generate(seed))


def run_turn(state, lines_y: list[str], lines_k: list[str]):
    """공식 엔진으로 한 턴. 명령 줄은 공식 파서로 읽는다. 돌려주는 값: (새 상태, 결과 또는 None)."""
    parse = protocol().parse_commands
    return pipeline.run_turn(state, parse(lines_y), parse(lines_k))
