## What changed

<!-- One or two sentences. Which layer does this touch, and why? -->

## How tested

<!-- Commands you ran and what they showed. Every new behavior needs a scenario test
     (CLAUDE.md > Rules). -->

- [ ] `ruff format .` and `ruff check .` clean
- [ ] `pytest` passes
- [ ] New/updated scenario test covering this behavior — or N/A because:

## Arena result vs main

<!-- Win rate of this branch against main, and over how many games. -->

| | |
|---|---|
| Games played | |
| Win rate vs `main` | |
| Verdict | keep / revert / needs more games |

- [ ] Logged in `experiments.md`
- [ ] Not applicable (no behavior change — docs/tooling/refactor only), because:

## Checklist

- [ ] Stays inside my layer's boundary (CLAUDE.md > Architecture)
- [ ] No files owned by a teammate touched without coordinating
- [ ] `main` stays submittable if this merges
