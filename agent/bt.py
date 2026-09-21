"""Hand-written behavior tree primitives.

Provides the generic node vocabulary - leaves, composites such as sequence and selector,
decorators - and the tick semantics used to compose them.

Boundary: entirely game-agnostic. No game-specific conditions or actions live here; those
belong in ``strategy``. Written by hand rather than pulled from a library so its behavior
is fully under our control during the hackathon.

TODO (day 1): implement once the action model is known.
"""
