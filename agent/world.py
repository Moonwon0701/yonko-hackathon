"""The clean, engine-agnostic game state.

Defines the team's shared vocabulary for describing a game position: the board, our
units, the opponent, and anything else the agent reasons about. Plain dataclasses in our
own terms, never the API's.

Boundary: performs no I/O and knows nothing about the API's field names or transport.
Everything above this layer reads game state only through these types, so this module is
the team's contract - announce changes to existing fields before making them.

TODO (day 1): define the state types once the rules are published.

엔진에 종속되지 않는 깔끔한 게임 상태.

게임의 한 국면을 설명하기 위한 팀 공용 용어를 정의합니다: 보드, 우리 유닛, 상대, 그 밖에
에이전트가 판단에 쓰는 모든 것. API의 용어가 아니라 우리 용어로 된 평범한 dataclass입니다.

경계: I/O를 전혀 하지 않으며 API의 필드명이나 통신 방식을 알지 못합니다. 이 계층 위의 모든
코드는 오직 이 타입들을 통해서만 게임 상태를 읽으므로, 이 모듈은 팀의 계약입니다. 기존 필드를
바꿀 때는 미리 공지하세요.

TODO (1일차): 규칙이 공개되면 상태 타입을 정의할 것.
"""
