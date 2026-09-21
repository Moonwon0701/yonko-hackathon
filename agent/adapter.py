"""The only module that knows the raw game API.

Owns every detail of the wire protocol: endpoints, authentication, request/response
shapes, JSON field names, and error handling. Translates raw API payloads into a
``world.World`` and translates the actions returned by ``strategy.decide`` back into the
format the API expects.

Boundary: contains no strategy, heuristics, or decision-making. If the game's protocol
changes, this file is the only one that should need editing.

TODO (day 1): implement against the real API once the rules are published.
"""
