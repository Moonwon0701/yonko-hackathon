"""제출 진입 파일. 서버가 이 파일을 실행하고 stdin/stdout으로 한 경기를 진행한다.

규칙: 매 턴 END를 반드시 출력하고 flush한다. 입력이 끝날(EOF) 때까지 종료하지 않는다.
어떤 예외가 나도 그 턴은 END만이라도 출력한다 — 프로세스가 죽으면 즉시 몰수패다.
"""

import sys
import time
import traceback
from collections import Counter

from agent import adapter
from agent.strategy import decide

MAX_ERROR_LOGS = 30  # stderr는 경기당 1 MiB 한도


def log_init(init: list[str]) -> None:
    """INIT 블록 원문. 서버 맵을 `python -m sim match --map-file`로 재현할 때 그대로 복사해 쓴다."""
    print("\n".join([*init, "END"]), file=sys.stderr)


def log_turn(turn: int, ms: float, lines: list[str]) -> None:
    """턴당 한 줄(약 30 B): `#t 12 3.1ms SPAWN1 MOVE4`. 160턴이어도 5 KB 정도다."""
    kinds = Counter(line.split(maxsplit=1)[0] for line in lines)
    counts = " ".join(f"{k}{n}" for k, n in sorted(kinds.items()))
    print(f"#t {turn} {ms:.1f}ms {counts}".rstrip(), file=sys.stderr)


def main() -> None:
    errors = 0

    def log_error(where: str) -> None:
        nonlocal errors
        errors += 1
        if errors <= MAX_ERROR_LOGS:
            print(f"[{where}] {traceback.format_exc(limit=5)}", file=sys.stderr)

    init = adapter.read_block(sys.stdin)
    if init is None:
        return
    game_map, me = adapter.parse_init(init)
    log_init(init)

    turn = 0
    while (block := adapter.read_block(sys.stdin)) is not None:
        start = time.perf_counter()
        turn += 1
        lines: list[str] = []
        try:
            world = adapter.parse_turn(block, game_map, me)
            turn = world.turn
            for action in decide(world):
                try:
                    lines.append(adapter.to_line(action))
                except ValueError:
                    log_error("to_line")
        except Exception:  # noqa: BLE001 — 어떤 예외든 END는 나가야 한다(몰수패 방지)
            log_error("turn")
        adapter.write_turn(sys.stdout, lines)
        try:
            log_turn(turn, (time.perf_counter() - start) * 1000, lines)
        except Exception:  # noqa: BLE001 — 로그 실패로 경기를 망치지 않는다
            pass


if __name__ == "__main__":
    main()
