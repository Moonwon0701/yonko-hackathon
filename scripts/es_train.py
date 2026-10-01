"""진화 전략(ES) 학습: agent/learned.py의 상황별 가중치 W를 상대 풀 대전 승점으로 찾는다.

사용법 (저장소 최상위에서):
    python scripts/es_train.py --gens 300                    # 새로 시작 (W = 0 = 기준 봇)
    python scripts/es_train.py --gens 300 --resume runs/es/<시각>/theta.json
    python scripts/es_train.py --validate runs/es/<시각>/theta.json --maps data/server-replays   # 검증만
    python scripts/es_train.py --bot experiments/learned_uo --pool unitops --gens 300   # daa1888 기반

방법 (OpenAI-ES, Salimans et al. 2017):
- 매개변수 θ = 상수(봇 폴더 agent/learned.py의 KNOBS) × 특징 8개. θ = 0이면 기준 봇과 똑같다.
- 한 세대: 잡음 ε를 POP쌍 뽑아 θ ± σε 후보 2·POP개를 만든다(대칭 표본). 모든 후보가 **같은 경기 묶음**(이번 세대 새
  생성 맵 × 풀 상대, 맵마다 진영 하나)을 둔다 → 후보끼리 차이가 맵 운이 아니라 가중치 차이에서 나온다.
- 보상 = 승점(승 1, 무 0.5, 패 0) + MARGIN_W × 점수 차 / 총점. 후보 점수를 순위로 바꿔(가운데 0) 기울기를 어림하고
  Adam으로 θ를 옮긴다. 가중치 감쇠로 θ를 0(= 기준 봇) 쪽으로 당긴다 — 이득이 없는 변화는 남지 않는다.
- 학습 맵은 매 세대 새 시드(10만 이상), 검증은 고정 시드(90만~) 또는 서버 맵. 모든 기록은 runs/es/<시각>/.
- 진영 교대는 하지 않는다: 맵이 점대칭이고 봇이 자기 본진 기준으로 움직여, 진영만 바꾼 경기는 결과가 똑같았다(12판 확인).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim import mapgen, match  # noqa: E402
from sim.bots import BotSpec, resolve  # noqa: E402

# 학습할 봇 폴더(main.py + agent/learned.py). 작업자 프로세스도 같은 폴더를 쓰도록 환경 변수로 넘긴다
BOT_DIR = ROOT / os.environ.get("ES_BOT", "experiments/learned")
LAUNCHER = ROOT / "scripts" / "es_bot.py"
# 상대 풀: 이름 → (지정, 한 세대에 나오는 비율). 기준 봇 자신을 가장 많이 둔다(자기 대전 = 기준보다 나아졌는가)
POOLS = {
    "hyunjin": {  # experiments/learned (현진 7b8b67e 기반)
        "hyunjin": ("git:7b8b67e", 3),
        "moonwon": ("git:2b71430", 2),
        "sunghyuk": ("git:73e2691", 1),
        "eng_rush": ("opponents/eng_rush.py", 1),
        "blob": ("opponents/blob.py", 1),
        "econ_raid": ("opponents/econ_raid.py", 1),
    },
    "unitops2": {  # unitops에서 주 상대 비중을 올린 것 (목표 = daa1888을 이기기)
        "daa1888": ("git:daa1888", 6),
        "7941b88": ("git:7941b88", 2),
        "hyunjin": ("git:7b8b67e", 2),
        "sunghyuk": ("git:73e2691", 1),
        "eng_rush": ("opponents/eng_rush.py", 1),
    },
    "learned240": {  # 학습 봇(26fa986 = daa1888 + 240세대) 위에서 이어 학습. 주 상대 = 그 봇 자신, 그다음 가장 어려운 로컬
        # 상대 strong_wide(26fa986 승점률 67%, 서버 강팀 스타일). 나머지(26fa986이 82~90%로 이김)는 퇴보 방지용
        "26fa986": ("git:26fa986", 4),
        "strong_wide": ("opponents/strong_wide.py", 3),
        "daa1888": ("git:daa1888", 2),
        "7941b88": ("git:7941b88", 1),
        "hyunjin": ("git:7b8b67e", 1),
        "sunghyuk": ("git:73e2691", 1),
        "eng_rush": ("opponents/eng_rush.py", 1),
    },
    "merged337": {  # 9/30 20:00 제출본(337ab49 = 26fa986 + 성혁 기능 선별 조합, experiments/learned_sh) 위에서 이어 학습.
        # 주 상대 = 제출본 자신, 그다음 strong_wide와 한 단계 전 학습 봇. 나머지는 퇴보 방지용
        "337ab49": ("git:337ab49", 4),
        "strong_wide": ("opponents/strong_wide.py", 3),
        "26fa986": ("git:26fa986", 2),
        "daa1888": ("git:daa1888", 1),
        "7941b88": ("git:7941b88", 1),
        "hyunjin": ("git:7b8b67e", 1),
        "sunghyuk": ("git:73e2691", 1),
        "eng_rush": ("opponents/eng_rush.py", 1),
    },
    "flag_escape": {  # experiments/learned_fe(= 0a15a9e: ee4ea4b + 포위된 깃발병 FLAG_ESCAPE) 위에서 4차 180세대 W부터 이어 학습.
        # 주 상대 = 그 봇 자신, 그다음 제출본 ee4ea4b와 strong_wide. 나머지는 퇴보 방지용
        "0a15a9e": ("git:0a15a9e", 4),
        "ee4ea4b": ("git:ee4ea4b", 3),
        "strong_wide": ("opponents/strong_wide.py", 3),
        "337ab49": ("git:337ab49", 1),
        "hunters": ("git:efb71da", 1),
        "26fa986": ("git:26fa986", 1),
        "eng_rush": ("opponents/eng_rush.py", 1),
    },
    "early_guard": {  # experiments/learned_eg(= e30333c(074803e + 선제 수비) + 성혁 hunters efb71da 코드, 기동대 수정만 켬)
        # 위에서 이어 학습. 주 상대 = 제출본 e30333c, 그다음 strong_wide와 선제 수비 전 봇 074803e. 나머지는 퇴보 방지용
        "e30333c": ("git:e30333c", 4),
        "strong_wide": ("opponents/strong_wide.py", 3),
        "074803e": ("git:074803e", 2),
        "337ab49": ("git:337ab49", 1),
        "hunters": ("git:efb71da", 1),
        "26fa986": ("git:26fa986", 1),
        "daa1888": ("git:daa1888", 1),
        "eng_rush": ("opponents/eng_rush.py", 1),
    },
    "unitops": {  # experiments/learned_uo (moonwon/unit-ops daa1888 기반). 흉내 봇은 과적합이 커서 하나만
        "daa1888": ("git:daa1888", 4),
        "7941b88": ("git:7941b88", 2),
        "hyunjin": ("git:7b8b67e", 2),
        "sunghyuk": ("git:73e2691", 1),
        "eng_rush": ("opponents/eng_rush.py", 1),
    },
    "final": {  # experiments/learned_final(= main e5cbeb7: 0a15a9e + 성혁 막판 광장·공학관 급습) 위에서 이어 학습.
        # 주 상대 = 최종 후보 자신, 그다음 제출본 ee4ea4b와 strong_wide. 나머지는 퇴보 방지용
        "e5cbeb7": ("git:e5cbeb7", 4),
        "ee4ea4b": ("git:ee4ea4b", 3),
        "strong_wide": ("opponents/strong_wide.py", 3),
        "0a15a9e": ("git:0a15a9e", 1),
        "337ab49": ("git:337ab49", 1),
        "eng_rush": ("opponents/eng_rush.py", 1),
    },
}
POOL = POOLS["hyunjin"]
MARGIN_W = 0.5
FEATURES: tuple = ()
KNOBS: tuple = ()
DIM = 0


def load_layer() -> None:
    """BOT_DIR/agent/learned.py의 특징·상수 목록을 읽는다(봇마다 조절하는 상수가 다르다)."""
    global FEATURES, KNOBS, DIM
    spec = importlib.util.spec_from_file_location("es_layer", BOT_DIR / "agent" / "learned.py")
    sys.path.insert(0, str(BOT_DIR))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    FEATURES, KNOBS = mod.FEATURES, mod.KNOBS
    DIM = len(KNOBS) * len(FEATURES)


def to_w(theta: list[float]) -> dict[str, list[float]]:
    n = len(FEATURES)
    return {name: [round(x, 5) for x in theta[k * n:(k + 1) * n]] for k, (name, *_) in enumerate(KNOBS)}


def from_w(w: dict[str, list[float]]) -> list[float]:
    theta = [0.0] * DIM
    n = len(FEATURES)
    for k, (name, *_) in enumerate(KNOBS):
        for i, x in enumerate(w.get(name, [])[:n]):
            theta[k * n + i] = x
    return theta


def learned_spec(weights: Path) -> BotSpec:
    return BotSpec(f"learned:{weights.name}", (sys.executable, str(LAUNCHER), str(BOT_DIR), str(weights)), str(BOT_DIR))


def play_one(task: tuple) -> tuple:
    key, map_ref, side, weights, opp = task
    spec = mapgen.generate(map_ref) if isinstance(map_ref, int) else map_ref[1]
    other = "K" if side == "Y" else "Y"
    try:
        result = match.play(spec, {side: learned_spec(Path(weights)), other: resolve(opp)},
                            time_scale=2.0, record=False)["result"]
    except Exception as e:  # noqa: BLE001 — 한 경기 오류로 학습을 멈추지 않는다
        return key, None, f"error {e}"
    winner = result["winner"]
    outcome = 1.0 if winner == side else 0.5 if winner is None else 0.0
    total = max(1, spec.total_score)
    margin = max(-1.0, min(1.0, (result["score"][side] - result["score"][other]) / total))
    return key, outcome + MARGIN_W * margin, (outcome, result["reason"])


def centered_ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    for r, i in enumerate(order):
        ranks[i] = r / (len(xs) - 1) - 0.5
    return ranks


class Adam:
    def __init__(self, dim: int, lr: float, b1: float = 0.9, b2: float = 0.999) -> None:
        self.m, self.v, self.t = [0.0] * dim, [0.0] * dim, 0
        self.lr, self.b1, self.b2 = lr, b1, b2

    def step(self, g: list[float]) -> list[float]:
        self.t += 1
        out = []
        for i, gi in enumerate(g):
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * gi
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * gi * gi
            mh = self.m[i] / (1 - self.b1 ** self.t)
            vh = self.v[i] / (1 - self.b2 ** self.t)
            out.append(self.lr * mh / (math.sqrt(vh) + 1e-8))
        return out


def write_w(path: Path, theta: list[float]) -> Path:
    path.write_text(json.dumps(to_w(theta)))
    return path


def validate(ex, out: Path, theta: list[float], maps: list, tag: str, weighted: bool = False) -> dict:
    """θ를 풀 상대 모두와 둔다(맵마다 진영 하나). 상대별 승점률. `weighted`면 상대마다 맵 수를 풀 비중에 맞춘다
    (비중이 가장 큰 상대 = 맵 전부) — 주 상대와의 차이를 가릴 판 수를 확보한다."""
    wpath = write_w(out / f"val_{tag}.json", theta)
    top = max(w for _, w in POOL.values())
    tasks = [((name, m_i), maps[m_i], "YK"[m_i % 2], str(wpath), spec)
             for name, (spec, w) in POOL.items() for m_i in range(len(maps) * w // top if weighted else len(maps))]
    per: dict[str, list[float]] = {}
    for (name, *_), _, info in ex.map(play_one, tasks, chunksize=2):
        if info and not isinstance(info, str):
            per.setdefault(name, []).append(info[0])
    rates = {name: sum(v) / len(v) for name, v in per.items()}
    rates["mean"] = sum(rates.values()) / len(rates)
    return rates


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gens", type=int, default=100)
    ap.add_argument("--pop", type=int, default=12, help="잡음 쌍 수 (후보 = 2배)")
    ap.add_argument("--maps-per-gen", type=int, default=8, help="세대마다 새 맵 수 (= 후보당 경기)")
    ap.add_argument("--sigma", type=float, default=0.25)
    ap.add_argument("--lr", type=float, default=0.03)
    ap.add_argument("--decay", type=float, default=0.002, help="θ를 0 쪽으로 당기는 비율(세대당)")
    ap.add_argument("--jobs", type=int, default=22)
    ap.add_argument("--val-every", type=int, default=10)
    ap.add_argument("--val-seeds", type=int, default=20)
    ap.add_argument("--val-weighted", action="store_true", help="검증 판 수를 상대마다 풀 비중에 맞춤")
    ap.add_argument("--resume", help="θ 파일(learned.W 형식 JSON)")
    ap.add_argument("--validate", help="학습 없이 이 θ만 검증")
    ap.add_argument("--maps", help="검증에 쓸 서버 리플레이 폴더 (없으면 생성 시드 900000~)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--bot", default="experiments/learned", help="학습할 봇 폴더")
    ap.add_argument("--cfg", default="", help='학습할 봇의 strategy 상수 덮어쓰기 "이름=값 ..." (스위치 켜기, es_bot.py ES_CFG)')
    ap.add_argument("--pool", default="hyunjin", choices=sorted(POOLS), help="상대 풀")
    ap.add_argument("--normal-priority", action="store_true", help="우선순위를 낮추지 않는다")
    args = ap.parse_args()
    global BOT_DIR, POOL
    os.environ["ES_BOT"] = args.bot
    os.environ["ES_CFG"] = args.cfg  # 작업자 프로세스 → es_bot.py가 읽는다
    BOT_DIR = ROOT / args.bot
    POOL = POOLS[args.pool]
    load_layer()
    if sys.platform == "win32" and not args.normal_priority:
        # 우선순위 "낮음"(BELOW_NORMAL). 자식 프로세스(작업자·봇)도 물려받아, 같은 컴퓨터의 다른 작업이 먼저 CPU를 쓴다
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p  # 핸들은 64비트. 기본(int)으로 넘기면 설정이 조용히 실패한다
        k32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000)

    for spec, _ in POOL.values():  # git 봇은 한 번만 풀어 둔다(병렬 작업끼리 경합하지 않게)
        resolve(spec)
    out = ROOT / "runs" / "es" / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / "cand").mkdir()
    log = (out / "log.jsonl").open("a", encoding="utf-8")
    val_maps = mapgen.load_server_maps(args.maps) if args.maps else list(range(900000, 900000 + args.val_seeds))

    theta = from_w(json.loads(Path(args.resume or args.validate).read_text())) if (args.resume or args.validate) else [0.0] * DIM
    with ProcessPoolExecutor(args.jobs) as ex:
        if args.validate:
            base = validate(ex, out, [0.0] * DIM, val_maps, "base", args.val_weighted)
            rates = validate(ex, out, theta, val_maps, "theta", args.val_weighted)
            print("기준  ", json.dumps({k: round(v, 3) for k, v in base.items()}, ensure_ascii=False))
            print("학습  ", json.dumps({k: round(v, 3) for k, v in rates.items()}, ensure_ascii=False))
            return

        rng = random.Random(args.seed)
        adam = Adam(DIM, args.lr)
        opp_cycle = [spec for spec, weight in POOL.values() for _ in range(weight)]
        print(f"차원 {DIM}, 후보 {2 * args.pop}, 후보당 {args.maps_per_gen}경기, 기록 {out}", flush=True)
        base = validate(ex, out, theta, val_maps, "base", args.val_weighted)  # 출발점(이어서 할 때는 불러온 θ)의 검증값
        print("출발점 검증", json.dumps({k: round(v, 3) for k, v in base.items()}), flush=True)
        log.write(json.dumps({"gen": 0, "val": base}) + "\n")
        for gen in range(1, args.gens + 1):
            started = time.perf_counter()
            eps = [[rng.gauss(0, 1) for _ in range(DIM)] for _ in range(args.pop)]
            cands = []
            for j, e in enumerate(eps):
                for sign in (1, -1):
                    c = [t + sign * args.sigma * x for t, x in zip(theta, e)]
                    cands.append(write_w(out / "cand" / f"{2 * j + (sign < 0)}.json", c))
            seeds = [rng.randrange(100000, 10**9) for _ in range(args.maps_per_gen)]
            opps = [opp_cycle[rng.randrange(len(opp_cycle))] for _ in seeds]
            sides = [rng.choice("YK") for _ in seeds]
            tasks = [((ci, si), s, sides[si], str(cands[ci]), opps[si])
                     for ci in range(len(cands)) for si, s in enumerate(seeds)]
            rewards: list[list[float]] = [[] for _ in cands]
            outcomes: list[list[float]] = [[] for _ in cands]
            errors = 0
            for (ci, *_), r, info in ex.map(play_one, tasks, chunksize=2):
                if r is None:
                    errors += 1
                    continue
                rewards[ci].append(r)
                outcomes[ci].append(info[0])
            fit = [sum(r) / len(r) if r else 0.0 for r in rewards]
            ranks = centered_ranks(fit)
            grad = [0.0] * DIM
            for j, e in enumerate(eps):
                d = ranks[2 * j] - ranks[2 * j + 1]
                for i in range(DIM):
                    grad[i] += d * e[i]
            grad = [g / (args.pop * args.sigma) for g in grad]
            step = adam.step(grad)
            theta = [(t + s) * (1 - args.decay) for t, s in zip(theta, step)]
            write_w(out / "theta.json", theta)
            win = sum(sum(o) for o in outcomes) / max(1, sum(len(o) for o in outcomes))
            norm = math.sqrt(sum(t * t for t in theta))
            row = {"gen": gen, "fit_mean": sum(fit) / len(fit), "fit_max": max(fit), "win": win,
                   "norm": norm, "errors": errors, "sec": round(time.perf_counter() - started, 1)}
            if gen % args.val_every == 0:
                row["val"] = validate(ex, out, theta, val_maps, f"g{gen}", args.val_weighted)
                write_w(out / f"theta_g{gen}.json", theta)
            log.write(json.dumps(row) + "\n")
            log.flush()
            val = f" 검증 {row['val']['mean']:.3f} " + json.dumps({k: round(v, 2) for k, v in row["val"].items()}) if "val" in row else ""
            print(f"g{gen} 승점 {win:.3f} 적합도 {row['fit_mean']:.3f}/{row['fit_max']:.3f} |θ| {norm:.2f} "
                  f"오류 {errors} {row['sec']}초{val}", flush=True)


if __name__ == "__main__":
    main()
