"""The hackathon game agent.

Layers, in dependency order (each may import from the ones before it, never after):
``adapter`` -> ``world`` -> ``pathfind`` / ``bt`` + ``strategy``.
See CLAUDE.md for the boundary each module must respect.

해커톤 게임 에이전트.

의존성 순서대로의 계층(각 모듈은 앞의 것만 import할 수 있고 뒤의 것은 안 됨):
``adapter`` -> ``world`` -> ``pathfind`` / ``bt`` + ``strategy``.
각 모듈이 지켜야 할 경계는 CLAUDE.md를 참고하세요.
"""
