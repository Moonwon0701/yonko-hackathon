"""제출 진입 파일. 서버가 이 파일을 실행하고 stdin/stdout으로 한 경기를 진행한다.

규칙: 매 턴 END를 반드시 출력하고 flush한다. 입력이 끝날(EOF) 때까지 종료하지 않는다.
어떤 예외가 나도 그 턴은 END만이라도 출력한다 — 프로세스가 죽으면 즉시 몰수패다.
"""

import sys
import traceback

from agent import adapter
from agent.strategy import decide

MAX_ERROR_LOGS = 30  # stderr는 경기당 1 MiB 한도


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

    while (block := adapter.read_block(sys.stdin)) is not None:
        lines: list[str] = []
        try:
            world = adapter.parse_turn(block, game_map, me)
            for action in decide(world):
                try:
                    lines.append(adapter.to_line(action))
                except ValueError:
                    log_error("to_line")
        except Exception:  # noqa: BLE001 — 어떤 예외든 END는 나가야 한다(몰수패 방지)
            log_error("turn")
        adapter.write_turn(sys.stdout, lines)


if __name__ == "__main__":
    main()
