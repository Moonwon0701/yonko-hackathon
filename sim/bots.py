"""봇 프로세스: 서버처럼 봇을 따로 띄우고 stdin/stdout 텍스트로 주고받는다.

봇 지정 방법 (resolve):
    .                     지금 작업 폴더의 main.py (제출본과 같은 진입점)
    path/to/dir           그 폴더의 main.py
    path/to/bot.py        그 파일
    starter:example_lv2   스타터 킷 예제 (starter/example_lv2.py)
    git:main              커밋/브랜치/태그의 main.py + agent/ 를 runs/bots/<해시>/ 에 풀어서 실행

`python -u`나 PYTHONUNBUFFERED를 쓰지 않는다. 서버와 마찬가지로 봇이 직접 flush하지 않으면 응답이
오지 않아 시간 초과가 나야 하기 때문이다.
"""

from __future__ import annotations

import io
import os
import queue
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from sim import rules

ROOT = Path(__file__).resolve().parent.parent
_EOF = object()


@dataclass(frozen=True)
class BotSpec:
    name: str
    cmd: tuple[str, ...]
    cwd: str


def resolve(spec: str, root: Path = ROOT) -> BotSpec:
    python = sys.executable
    if spec.startswith("starter:"):
        name = spec.split(":", 1)[1]
        path = root / "starter" / f"{name.removesuffix('.py')}.py"
        if not path.exists():
            raise ValueError(f"스타터 봇 없음: {path}")
        return BotSpec(spec, (python, path.name), str(path.parent))
    if spec.startswith("git:"):
        return _git_bot(spec.split(":", 1)[1], root)
    path = Path(spec)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if path.is_dir():
        path = path / "main.py"
    if not path.exists():
        raise ValueError(f"봇 파일 없음: {path}")
    return BotSpec(spec, (python, path.name), str(path.parent))


def _git_bot(ref: str, root: Path) -> BotSpec:
    def git(*args: str, binary: bool = False):
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
        if out.returncode:
            raise ValueError(f"git {' '.join(args)} 실패: {out.stderr.decode(errors='replace')}")
        return out.stdout if binary else out.stdout.decode().strip()

    sha = git("rev-parse", "--short=10", f"{ref}^{{commit}}")
    dest = root / "runs" / "bots" / sha
    if not (dest / "main.py").exists():
        paths = [p for p in ("main.py", "agent", "submission.json")
                 if git("ls-tree", "--name-only", sha, p)]
        data = git("archive", "--format=zip", sha, *paths, binary=True)
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(dest)
    return BotSpec(f"git:{ref}@{sha}", (sys.executable, "main.py"), str(dest))


@dataclass
class Reply:
    lines: list[str]
    ms: float
    error: str | None = None  # 몰수 사유
    stderr: str = ""


class BotProcess:
    """봇 하나. send()로 블록을 보내고 receive()로 END까지 읽는다."""

    def __init__(self, spec: BotSpec, time_scale: float | None = 1.0):
        self.spec = spec
        self.time_scale = time_scale  # None이면 시간 제한 없음 (디버깅용)
        env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.started = time.perf_counter()
        self.proc = subprocess.Popen(
            list(spec.cmd), cwd=spec.cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, bufsize=0,
        )
        self.turn_start = self.started
        self.first = True
        self.stdout: queue.Queue = queue.Queue()
        self.stdin: queue.Queue = queue.Queue()
        self._stderr: list[bytes] = []
        self.stderr_bytes = 0
        self._lock = threading.Lock()
        for target in (self._read_stdout, self._read_stderr, self._write_stdin):
            threading.Thread(target=target, daemon=True).start()

    # 입력이 막혀도(봇이 안 읽어도) 우리 쪽이 멈추지 않도록 쓰기·읽기는 모두 스레드에서 한다
    def _write_stdin(self) -> None:
        while (data := self.stdin.get()) is not None:
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except OSError:
                return
        try:
            self.proc.stdin.close()
        except OSError:
            pass

    def _read_stdout(self) -> None:
        for raw in self.proc.stdout:
            self.stdout.put(raw)
        self.stdout.put(_EOF)

    def _read_stderr(self) -> None:
        for raw in self.proc.stderr:
            with self._lock:
                self.stderr_bytes += len(raw)
                if sum(map(len, self._stderr)) < 64 * 1024:  # 리플레이에는 턴당 조금만 남긴다
                    self._stderr.append(raw)

    def take_stderr(self) -> str:
        with self._lock:
            data, self._stderr = b"".join(self._stderr), []
        return data.decode("utf-8", errors="replace")

    def send(self, text: str) -> None:
        if not self.first:
            self.turn_start = time.perf_counter()
        self.stdin.put(text.encode())

    def receive(self) -> Reply:
        limit = rules.FIRST_TURN_MS if self.first else rules.TURN_MS
        self.first = False
        deadline = None if self.time_scale is None else self.turn_start + limit * self.time_scale / 1000
        lines: list[str] = []
        size = 0
        while True:
            timeout = None if deadline is None else max(0.0, deadline - time.perf_counter())
            try:
                raw = self.stdout.get(timeout=timeout)
            except queue.Empty:
                return self._reply(lines, f"시간 초과 ({limit} ms)")
            if raw is _EOF:
                code = self.proc.poll()
                return self._reply(lines, f"END 전에 프로세스 종료 (종료 코드 {code})")
            size += len(raw)
            if len(raw) > rules.LINE_MAX_BYTES:
                return self._reply(lines, f"한 줄이 {rules.LINE_MAX_BYTES} B 초과")
            line = raw.decode("utf-8", errors="replace").strip()
            if line == "END":
                break
            lines.append(line)
            if size > rules.STDOUT_MAX_BYTES or len(lines) > rules.STDOUT_MAX_LINES:
                return self._reply(lines, "턴당 출력 한도 초과 (64 KiB · 4,096줄)")
        if self.stderr_bytes > rules.STDERR_MAX_BYTES:
            return self._reply(lines, "stderr 경기당 1 MiB 초과")
        return self._reply(lines, None)

    def _reply(self, lines: list[str], error: str | None) -> Reply:
        ms = (time.perf_counter() - self.turn_start) * 1000
        return Reply(lines, ms, error, self.take_stderr())

    def close(self) -> None:
        """EOF를 보내 스스로 끝나게 하고, 안 끝나면 죽인다."""
        self.stdin.put(None)
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
