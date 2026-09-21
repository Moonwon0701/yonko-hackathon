"""Pure pathfinding functions.

Movement and reachability queries over the board - shortest paths, distances, reachable
sets - exposed as deterministic functions of their arguments.

Boundary: no I/O, no globals, no mutation of inputs, and no strategy decisions. Choosing
*where* to go belongs in ``strategy``; this module only answers *how* to get there. Must
stay cheap enough to call repeatedly inside the per-decision time budget.

TODO (day 1): implement once the map representation is known.
"""
