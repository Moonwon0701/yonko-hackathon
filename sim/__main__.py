"""로컬 시뮬레이터 명령줄. 저장소 최상위에서 실행한다.

    python -m sim match . starter:example_lv2 --seed 3 --open
    python -m sim arena . git:main --seeds 50
    python -m sim map --seed 3

봇 지정 방법은 sim/bots.py 맨 위, 자세한 사용법은 docs/simulator.md.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import webbrowser
from pathlib import Path

from sim import arena, bots, mapgen, match, viewer

RUNS = Path("runs")


def _time_scale(args) -> float | None:
    return None if args.no_timeout else args.time_scale


def _load_map(args) -> mapgen.MapSpec:
    if args.map_file and args.map_file.endswith(".json"):
        return mapgen.from_server_replay(args.map_file, seed=args.seed)
    if args.map_file:
        return mapgen.from_init(Path(args.map_file).read_text(encoding="utf-8"), seed=args.seed)
    return mapgen.generate(args.seed)


def cmd_match(args) -> None:
    spec = _load_map(args)
    pair = {"Y": bots.resolve(args.y), "K": bots.resolve(args.k)}
    start = time.perf_counter()
    replay = match.play(spec, pair, time_scale=_time_scale(args))
    if args.view != "all":
        replay["view"] = args.view
    res = replay["result"]
    stamp = time.strftime("%m%d-%H%M%S")
    out = Path(args.out) if args.out else RUNS / f"match-{stamp}-seed{args.seed}.html"
    viewer.write_html(replay, out)
    winner = f"{res['winner']} 승" if res["winner"] else "무승부"
    print(f"Y {pair['Y'].name}  vs  K {pair['K'].name}  (시드 {args.seed})")
    print(f"결과: {winner}, {res['reason']}, {res['turn']}턴")
    print(f"점령 점수 Y {res['score']['Y']} : K {res['score']['K']}   "
          f"누적 점령-턴 Y {res['occupation']['Y']} : K {res['occupation']['K']}")
    print(f"무시된 명령 Y {res['ignored_commands']['Y']} · K {res['ignored_commands']['K']}   "
          f"최대 응답 Y {res['max_ms']['Y']:.0f} ms · K {res['max_ms']['K']:.0f} ms")
    if res.get("detail"):
        print(f"몰수 사유: {res['detail']}")
    print(f"리플레이: {out}  ({time.perf_counter() - start:.1f}s)")
    if args.open:
        webbrowser.open(out.resolve().as_uri())


def cmd_arena(args) -> None:
    a, b = bots.resolve(args.a), bots.resolve(args.b)
    if args.maps:
        seeds = mapgen.load_server_maps(args.maps, seed=args.seed)  # (이름, 맵) 목록
    else:
        seeds = list(range(args.seed, args.seed + args.seeds))
    out = Path(args.out) if args.out else RUNS / f"arena-{time.strftime('%m%d-%H%M%S')}"
    start = time.perf_counter()

    def progress(done, total):
        print(f"\r{done}/{total} 경기", end="", file=sys.stderr, flush=True)

    rows = arena.run(a, b, seeds, jobs=args.jobs, time_scale=_time_scale(args),
                     save_dir=out, save_mode=args.save, progress=progress)
    print(file=sys.stderr)
    summary = arena.summarize(rows, a.name, b.name)
    print(summary)
    (out / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    saved = sum("replay" in r for r in rows)
    print(f"결과 폴더: {out}  (리플레이 {saved}개, {time.perf_counter() - start:.1f}s)")


def cmd_map(args) -> None:
    spec = _load_map(args)
    print("\n".join(spec.rows))
    print(f"본진 Y {spec.bases['Y']} · K {spec.bases['K']} · 맵 총점 {spec.total_score}")
    for b in spec.buildings:
        print(f"  #{b.id:2d} {b.kind:8s} {b.pos}  {b.score}점")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m sim", description="깃발 대항전 로컬 시뮬레이터")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--seed", type=int, default=0, help="맵 시드 (arena는 시작 시드)")
        sp.add_argument("--map-file", help="서버 맵: INIT 블록 텍스트 또는 대회 페이지 리플레이(.json)")
        sp.add_argument("--time-scale", type=float, default=1.0,
                        help="시간 제한 배율 (기본 1.0 = 3초/300ms)")
        sp.add_argument("--no-timeout", action="store_true", help="시간 제한 끄기 (디버깅용)")
        sp.add_argument("--out", help="출력 경로")

    m = sub.add_parser("match", help="한 판 두고 리플레이 HTML 만들기")
    m.add_argument("y", help="Y(연세) 봇")
    m.add_argument("k", help="K(고려) 봇")
    m.add_argument("--open", action="store_true", help="끝나면 브라우저로 열기")
    m.add_argument("--view", choices=("all", "Y", "K"), default="all",
                   help="리플레이를 열 때 기본 시점: all(관전자) 또는 그 팀이 아는 정보만")
    common(m)
    m.set_defaults(func=cmd_match)

    a = sub.add_parser("arena", help="여러 맵에서 진영을 바꿔 가며 대전")
    a.add_argument("a", help="평가할 봇 (A)")
    a.add_argument("b", help="상대 봇 (B)")
    a.add_argument("--seeds", type=int, default=20, help="맵 개수 (경기 수는 2배)")
    a.add_argument("--maps", help="서버 리플레이 폴더: 시드 맵 대신 그 안의 서버 맵(같은 지형은 하나로)으로 대전")
    a.add_argument("--jobs", type=int, default=arena.default_jobs(), help="동시 경기 수")
    a.add_argument("--save", choices=("none", "losses", "all"), default="losses",
                   help="리플레이 저장: A가 이기지 못한 경기만(기본)/전부/안 함")
    common(a)
    a.set_defaults(func=cmd_arena)

    mp = sub.add_parser("map", help="맵 출력")
    common(mp)
    mp.set_defaults(func=cmd_map)

    # Windows에서 출력이 파이프(Git Bash, VS Code, Claude Code의 ! 명령)로 가면 Python은 cp949로 써서
    # 한글이 깨진다. 콘솔 창은 인코딩과 상관없이 유니코드로 찍히므로 UTF-8로 통일한다.
    # PYTHONIOENCODING을 직접 정했으면 그것을 따른다.
    utf8 = "PYTHONIOENCODING" not in os.environ
    for stream in (sys.stdout, sys.stderr):
        if utf8:
            stream.reconfigure(encoding="utf-8", errors="replace")
        else:
            stream.reconfigure(errors="replace")
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
