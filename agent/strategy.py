"""The agent's actual behavior: ``decide(world) -> actions``.

Composes the primitives from ``bt`` and the queries from ``pathfind`` into the behavior
tree that plays the game. ``decide`` is the single entry point from ``adapter`` into the
agent's brain, and its signature does not change.

Boundary: speaks only in ``world`` types and our own action vocabulary - never raw API
formats, never network calls. Must always return a legal action within the game's
per-decision time limit; a timeout is worse than a mediocre move.

TODO (day 1): implement once the rules are published.
"""
