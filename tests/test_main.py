"""main.py가 몰수패 조건(END 누락, 비정상 종료)을 만들지 않는지 확인한다."""

import importlib.util
import io
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fake_input import random_game

ROOT = Path(__file__).resolve().parent.parent


def load_main():
    spec = importlib.util.spec_from_file_location("bot_main", ROOT / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_game_answers_every_turn():
    text = random_game(seed=1, turns=160)
    result = subprocess.run(
        [sys.executable, "main.py"], cwd=ROOT, input=text, capture_output=True,
        text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines().count("END") == 160
    assert result.stderr == ""


def test_exception_in_decide_still_prints_end(monkeypatch, capsys):
    bot = load_main()

    def broken(world):
        raise RuntimeError("boom")

    monkeypatch.setattr(bot, "decide", broken)
    monkeypatch.setattr(sys, "stdin", io.StringIO(random_game(seed=2, turns=3)))
    bot.main()
    out, err = capsys.readouterr()
    assert out.splitlines() == ["END", "END", "END"]
    assert "boom" in err


def test_answers_turn_by_turn_like_the_server():
    """서버처럼 한 턴 보내고 응답(END)을 받은 뒤 다음 턴을 보낸다. 입력을 더 기다리며 멈추면 실패."""
    blocks = random_game(seed=3, turns=5).split("END\n")[:-1]
    proc = subprocess.Popen(
        [sys.executable, "main.py"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
    )
    pool = ThreadPoolExecutor(1)
    try:
        proc.stdin.write(blocks[0] + "END\n")  # INIT에는 응답하지 않는다
        for block in blocks[1:]:
            proc.stdin.write(block + "END\n")
            proc.stdin.flush()
            reply = pool.submit(lambda: list(iter(proc.stdout.readline, "END\n")))
            lines = reply.result(timeout=5)  # 응답이 없으면 여기서 TimeoutError
            assert all(line.split()[0] in {"SPAWN", "MOVE"} for line in lines)
        proc.stdin.close()
        assert proc.wait(timeout=5) == 0
    finally:
        proc.kill()  # 막힌 readline도 여기서 풀린다
        pool.shutdown(wait=False)
