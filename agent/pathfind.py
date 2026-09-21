"""Pure pathfinding functions.

Movement and reachability queries over the board - shortest paths, distances, reachable
sets - exposed as deterministic functions of their arguments.

Boundary: no I/O, no globals, no mutation of inputs, and no strategy decisions. Choosing
*where* to go belongs in ``strategy``; this module only answers *how* to get there. Must
stay cheap enough to call repeatedly inside the per-decision time budget.

TODO (day 1): implement once the map representation is known.

순수한 경로 탐색 함수.

보드 위의 이동과 도달 가능성에 관한 질의(최단 경로, 거리, 도달 가능 영역)를 인자에만 의존하는
결정적 함수로 제공합니다.

경계: I/O, 전역 변수, 입력 변형, 전략적 판단이 없습니다. *어디로* 갈지 고르는 일은
``strategy``의 몫이고, 이 모듈은 *어떻게* 갈지만 답합니다. 판단 1회당 시간 예산 안에서 반복
호출해도 될 만큼 가벼워야 합니다.

TODO (1일차): 맵 표현 방식이 정해지면 구현할 것.
"""
