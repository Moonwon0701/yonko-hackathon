"""The only module that knows the raw game API.

Owns every detail of the wire protocol: endpoints, authentication, request/response
shapes, JSON field names, and error handling. Translates raw API payloads into a
``world.World`` and translates the actions returned by ``strategy.decide`` back into the
format the API expects.

Boundary: contains no strategy, heuristics, or decision-making. If the game's protocol
changes, this file is the only one that should need editing.

TODO (day 1): implement against the real API once the rules are published.

원시 게임 API를 아는 유일한 모듈.

통신 프로토콜의 모든 세부사항을 담당합니다: 엔드포인트, 인증, 요청·응답 형태, JSON 필드명,
오류 처리. 원시 API 페이로드를 ``world.World``로 옮기고, ``strategy.decide``가 돌려준 행동을
다시 API가 기대하는 형식으로 번역합니다.

경계: 전략, 휴리스틱, 의사결정을 일절 포함하지 않습니다. 게임 프로토콜이 바뀌면 수정이 필요한
파일은 이 파일 하나뿐이어야 합니다.

TODO (1일차): 규칙이 공개되면 실제 API에 맞춰 구현할 것.
"""
