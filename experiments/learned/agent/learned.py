"""학습한 상황별 가중치 층: 매 턴 상황 특징으로 strategy.py의 상수(과제 가치·생산 인원)를 바꾼다.

    상수 = 기준값 × exp(clip(Σ W[상수][i] × 특징[i], ±Z_MAX))     정수 상수는 반올림(하한 있음)

- 기준값은 strategy.py에 적힌 값(= 현진 테마 브랜치 7b8b67e). W가 비어 있으면 그 봇과 똑같이 움직인다.
- W는 진화 전략(ES, scripts/es_train.py)으로 상대 풀과의 대전 승점만 보고 찾았다. 소스 안의 상수이므로 규정상
  허용된다(docs/game-api.md 12절). 실행 중 파일을 읽지 않는다.
- 판단 구조(BT·과제·배정)는 그대로이고, 이 층은 "지금 상황에서 어느 과제를 얼마나 중시할지"만 정한다.
"""

from __future__ import annotations

import math

from agent.world import World

FEATURES = (
    "bias",       # 1
    "turn",       # 턴 / 160 × 2 − 1  (−1 ~ 1)
    "warriors",   # (우리 − 적 전투병) / (합 + 10)
    "buildings",  # (우리 − 적 건물 수) / 8
    "eng",        # (우리 − 적 공학관 수) / 2
    "hall",       # (우리 − 적 학생회관 수) / 2
    "gold",       # 우리 자원 / 40
    "invaded",    # 우리 본진 쪽에 온 적 전투병 / (적 전투병 + 5)
)

# (상수 이름, 정수인가, 정수일 때 하한). "A.B"는 dict 상수 A의 키 B
KNOBS: tuple[tuple[str, bool, int], ...] = (
    ("KILL_VALUE", False, 0),
    ("ESCORT_VALUE", False, 0),
    ("EVICT_WEIGHT", False, 0),
    ("ECON_WEIGHT", False, 0),
    ("RAID_STEAL", False, 0),
    ("SQUAD_WEIGHT", False, 0),
    ("ENG_RUSH_VALUE", False, 0),
    ("ENG_RUSH_CAPTURE", False, 0),
    ("HALL_VALUE_PER_TURN", False, 0),
    ("FUNCTION_VALUE.ENG", False, 0),
    ("DEPOT_VALUE", False, 0),
    ("ETA_OFFSET", False, 0),
    ("MAX_FLAGS", True, 1),
    ("SQUAD_SIZE", True, 1),
    ("ENG_RUSH_EXTRA", True, 0),
    ("MIN_WARRIORS", True, 0),
)
Z_MAX = 2.5  # 배수 범위 exp(±2.5) ≈ 0.08 ~ 12

# 학습한 가중치: 상수 이름 → FEATURES 순서의 가중치. 없는 상수는 기준값 그대로.
# 2026-09-30 ES 80세대(runs/es/20260930-011408/theta_g80.json) — docs/benchmarks.md "학습 (진화 전략)"
W: dict[str, list[float]] = {
    "KILL_VALUE": [0.483, 0.269, 0.225, -0.141, -0.157, -0.188, 0.151, -0.051],
    "ESCORT_VALUE": [-0.336, -0.119, -0.001, -0.183, -0.325, 0.557, -0.274, -0.387],
    "EVICT_WEIGHT": [0.142, 0.122, -0.226, 0.113, -0.263, -0.108, -0.008, -0.089],
    "ECON_WEIGHT": [-0.374, -0.441, 0.241, 0.093, 0.051, -0.021, 0.518, -0.186],
    "RAID_STEAL": [-0.288, -0.504, -0.103, -0.137, -0.263, 0.358, -0.195, 0.519],
    "SQUAD_WEIGHT": [0.156, 0.072, -0.140, -0.444, 0.090, 0.061, 0.117, 0.424],
    "ENG_RUSH_VALUE": [-0.142, 0.182, 0.555, 0.235, -0.271, -0.193, 0.233, -0.177],
    "ENG_RUSH_CAPTURE": [0.433, -0.237, 0.084, 0.138, -0.012, 0.328, 0.273, -0.176],
    "HALL_VALUE_PER_TURN": [0.733, -0.394, -0.427, -0.023, 0.338, -0.436, 0.255, 0.012],
    "FUNCTION_VALUE.ENG": [0.509, -0.484, 0.271, 0.096, -0.383, -0.263, 0.045, -0.003],
    "DEPOT_VALUE": [-0.295, 0.143, -0.106, 0.205, 0.331, -0.505, 0.004, -0.254],
    "ETA_OFFSET": [-0.505, 0.239, -0.027, 0.134, -0.124, -0.042, -0.094, 0.120],
    "MAX_FLAGS": [-0.359, -0.318, 0.244, -0.433, -0.346, 0.227, 0.195, 0.009],
    "SQUAD_SIZE": [-0.150, 0.034, -0.275, 0.057, -0.095, -0.255, 0.119, 0.023],
    "ENG_RUSH_EXTRA": [-0.365, -0.167, -0.097, 0.199, -0.320, -0.039, -0.013, 0.392],
    "MIN_WARRIORS": [0.125, -0.079, 0.037, -0.182, -0.615, 0.380, 0.268, -0.038],
}

_base: dict[str, float] = {}  # 처음 불렀을 때 strategy.py에서 읽은 기준값


def features(world: World) -> list[float]:
    me, enemy = world.me, world.enemy
    my_w = sum(n for _, n in world.units_of(me, "W"))
    en_w_units = world.units_of(enemy, "W")
    en_w = sum(n for _, n in en_w_units)
    home, away = world.map.bases[me], world.map.bases[enemy]

    def dist(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    invaded = sum(n for p, n in en_w_units if dist(p, home) < dist(p, away))
    return [
        1.0,
        world.turn / 80.0 - 1.0,
        (my_w - en_w) / (my_w + en_w + 10),
        (len(world.owned(me)) - len(world.owned(enemy))) / 8.0,
        (len(world.owned(me, "ENG")) - len(world.owned(enemy, "ENG"))) / 2.0,
        (len(world.owned(me, "HALL")) - len(world.owned(enemy, "HALL"))) / 2.0,
        world.gold[me] / 40.0,
        invaded / (en_w + 5),
    ]


def _get(g: dict, name: str):
    if "." in name:
        top, key = name.split(".")
        return g[top][key]
    return g[name]


def apply(world: World, g: dict) -> None:
    """strategy 모듈의 전역(`g` = strategy.globals())을 이번 턴 값으로 바꾼다."""
    if not _base:
        _base.update({name: float(_get(g, name)) for name, *_ in KNOBS})
    f = features(world) if W else None
    for name, is_int, low in KNOBS:
        w = W.get(name)
        z = 0.0
        if w and f is not None:
            z = max(-Z_MAX, min(Z_MAX, sum(wi * fi for wi, fi in zip(w, f))))
        value = _base[name] * math.exp(z)
        if is_int:
            value = max(low, int(round(value)))
        if "." in name:
            top, key = name.split(".")
            g[top] = {**g[top], key: value}
        else:
            g[name] = value
