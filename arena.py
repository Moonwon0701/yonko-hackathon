"""Version-vs-version evaluation harness.

Runs repeated matches between two versions of the agent and reports the win rate, so that
"is this change actually better?" is answered by evidence rather than intuition. Results
belong in ``experiments.md``.

Boundary: contains no agent logic - it only sets up matches, collects outcomes, and
reports.

TODO (day 1): implement once the game can be run locally or against the API.
"""
