"""경기 한 판: 엔진 + 봇 프로세스 둘. 서버처럼 INIT → (TURN → 응답)×최대 160 → EOF."""

from __future__ import annotations

from sim import rules
from sim.bots import BotProcess, BotSpec
from sim.engine import ASSUMPTIONS, Game
from sim.mapgen import MapSpec

STDERR_PER_TURN = 2000  # 리플레이에 남길 턴당 stderr 글자 수


def play(spec: MapSpec, bots: dict[str, BotSpec], *, time_scale: float | None = 1.0,
         record: bool = True) -> dict:
    """경기를 끝까지 진행하고 결과(와 리플레이)를 dict로 돌려준다."""
    game = Game(spec)
    procs = {t: BotProcess(bots[t], time_scale) for t in rules.TEAMS}
    frames = [game.snapshot()]
    turns: list[dict] = []
    timing = {t: [] for t in rules.TEAMS}
    try:
        for t in rules.TEAMS:
            procs[t].send(game.init_text(t))
        while not game.over:
            texts = {t: game.turn_text(t) for t in rules.TEAMS}
            if record:
                frames[-1]["input"] = texts  # 이 상태에서 각 봇이 받는 입력 원문 (팀 시점 보기용)
            for t in rules.TEAMS:
                procs[t].send(texts[t])
            replies = {t: procs[t].receive() for t in rules.TEAMS}
            for t in rules.TEAMS:
                timing[t].append(round(replies[t].ms, 2))
            errors = {t: r.error for t, r in replies.items() if r.error}
            if errors:
                game.forfeit(errors)
                if record:
                    turns.append({"turn": game.turn + 1, "commands": {}, "events": [],
                                  "stderr": _stderr(replies), "forfeit": errors})
                break
            log = game.step({t: replies[t].lines for t in rules.TEAMS})
            if record:
                entry = log.to_json()
                entry["stderr"] = _stderr(replies)
                entry["ms"] = {t: round(replies[t].ms, 1) for t in rules.TEAMS}
                turns.append(entry)
                frames.append(game.snapshot())
    finally:
        for p in procs.values():
            p.close()

    ignored = {t: 0 for t in rules.TEAMS}
    for entry in turns:
        for t, cmds in entry["commands"].items():
            ignored[t] += sum(c["status"] == "ignored" for c in cmds)
    result = dict(game.result)
    result["bots"] = {t: bots[t].name for t in rules.TEAMS}
    result["seed"] = spec.seed
    result["max_ms"] = {t: max(timing[t][1:] or [0.0]) for t in rules.TEAMS}
    result["first_ms"] = {t: timing[t][0] if timing[t] else 0.0 for t in rules.TEAMS}
    result["ignored_commands"] = ignored if record else None
    if not record:
        return {"result": result}
    return {
        "version": 1,
        "result": result,
        "map": {
            "seed": spec.seed,
            "rows": list(spec.rows),
            "bases": spec.bases,
            "buildings": [{"id": b.id, "x": b.pos[0], "y": b.pos[1], "kind": b.kind,
                           "score": b.score} for b in spec.buildings],
            "total_score": spec.total_score,
        },
        "init": {t: game.init_text(t) for t in rules.TEAMS},
        "frames": frames,
        "turns": turns,
        "assumptions": ASSUMPTIONS,
    }


def _stderr(replies) -> dict[str, str]:
    out = {}
    for t, r in replies.items():
        if r.stderr:
            text = r.stderr
            out[t] = text if len(text) <= STDERR_PER_TURN else text[:STDERR_PER_TURN] + "\n…(생략)"
    return out
