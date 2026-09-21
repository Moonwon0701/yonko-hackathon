"""The clean, engine-agnostic game state.

Defines the team's shared vocabulary for describing a game position: the board, our
units, the opponent, and anything else the agent reasons about. Plain dataclasses in our
own terms, never the API's.

Boundary: performs no I/O and knows nothing about the API's field names or transport.
Everything above this layer reads game state only through these types, so this module is
the team's contract - announce changes to existing fields before making them.

TODO (day 1): define the state types once the rules are published.
"""
