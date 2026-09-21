"""The agent's actual behavior: ``decide(world) -> actions``.

Composes the primitives from ``bt`` and the queries from ``pathfind`` into the behavior
tree that plays the game. ``decide`` is the single entry point from ``adapter`` into the
agent's brain, and its signature does not change.

Boundary: speaks only in ``world`` types and our own action vocabulary - never raw API
formats, never network calls. Must always return a legal action within the game's
per-decision time limit; a timeout is worse than a mediocre move.

TODO (day 1): implement once the rules are published.

에이전트의 실제 행동: ``decide(world) -> actions``.

``bt``의 기본 요소와 ``pathfind``의 질의를 조합해 게임을 플레이하는 행동 트리를 구성합니다.
``decide``는 ``adapter``에서 에이전트의 두뇌로 들어오는 유일한 진입점이며, 그 시그니처는 바뀌지
않습니다.

경계: 오직 ``world`` 타입과 우리 행동 어휘로만 말합니다. 원시 API 형식이나 네트워크 호출은
절대 없습니다. 게임의 판단 1회당 시간 제한 안에서 항상 합법적인 행동을 반환해야 합니다. 시간
초과는 평범한 수보다 나쁩니다.

TODO (1일차): 규칙이 공개되면 구현할 것.
"""
