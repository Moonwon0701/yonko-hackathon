"""Hand-written behavior tree primitives.

Provides the generic node vocabulary - leaves, composites such as sequence and selector,
decorators - and the tick semantics used to compose them.

Boundary: entirely game-agnostic. No game-specific conditions or actions live here; those
belong in ``strategy``. Written by hand rather than pulled from a library so its behavior
is fully under our control during the hackathon.

TODO (day 1): implement once the action model is known.

직접 작성한 행동 트리 기본 요소.

범용 노드 어휘(리프, 시퀀스·셀렉터 같은 조합 노드, 데코레이터)와 이들을 조합할 때 쓰는 틱
동작을 제공합니다.

경계: 게임에 전혀 종속되지 않습니다. 게임 고유의 조건이나 행동은 여기 두지 않고 ``strategy``에
둡니다. 해커톤 동안 동작을 완전히 통제할 수 있도록 라이브러리를 쓰지 않고 직접 작성합니다.

TODO (1일차): 행동 모델이 정해지면 구현할 것.
"""
