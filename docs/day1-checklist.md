# Day 1 checklist

The order matters. The goal of day 1 is not a clever agent - it is a **submittable** one,
plus a shared understanding of the rules and a way to measure changes.

## 1. Read the rules together

- [ ] All three of us read the published rules and API docs end to end.
- [ ] Talk through anything ambiguous *before* writing code. Disagreements about the rules
      are much cheaper now than after three sessions have built on them.
- [ ] Note the hard constraints explicitly: **per-decision time limit**, action legality,
      submission format, and the penalty for a timeout or an invalid action.

## 2. Fill in `## Game Rules` in `CLAUDE.md`

- [ ] Write the rules into the `## Game Rules` section of `CLAUDE.md`, using the checklist
      already in that section.
- [ ] **Merge this first, before any other work.** It is the one file every Claude Code
      session reads, so all three sessions must be working from the same filled-in copy.
- [ ] Everyone pulls and re-reads `CLAUDE.md` after it lands.

## 3. Implement the adapter

- [ ] IO implements `agent/adapter.py` against the real API: connect, authenticate, fetch
      state, send an action.
- [ ] Define `agent/world.py` alongside it - our own vocabulary, no API field names.
      Announce the shape to the team; it is the contract everything else builds on.
- [ ] Prove a full round trip: raw payload -> `World` -> action -> accepted by the API.

## 4. Get a minimal submittable agent onto `main`

- [ ] `decide(world)` returns *some* legal action - random or trivially greedy is fine.
- [ ] Play one complete game without crashing, without an invalid action, and inside the
      time limit.
- [ ] Merge it. From this point on we always have something to submit, and every later
      change is an improvement on a known-working baseline rather than a gamble.

## 5. Stand up the arena

- [ ] IO implements `arena.py`: run N matches between two versions, report win rate.
- [ ] Record the baseline agent's result as the first row of `experiments.md`.
- [ ] From here, no strategy change merges on vibes - it merges on an arena result.

## 6. Split the work by ownership

- [ ] Fill the real GitHub handles into `.github/CODEOWNERS`.
- [ ] Work in parallel along the ownership lines:
      - **IO** - adapter, world, arena, CI
      - **ALGO** - pathfinding
      - **STRATEGY** - behavior tree and the agent's behavior
- [ ] One feature per branch, PR into `main`, CI green before merge.
- [ ] Agree on a re-sync point (e.g. end of day) to review what landed and pick the next
      targets together.
