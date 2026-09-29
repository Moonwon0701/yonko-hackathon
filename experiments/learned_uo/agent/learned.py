"""학습한 상황별 가중치 층: 매 턴 상황 특징으로 strategy.py의 상수(과제 가치·생산 인원)를 바꾼다.

    상수 = 기준값 × exp(clip(Σ W[상수][i] × 특징[i], ±Z_MAX))     정수 상수는 반올림(하한 있음)

- 기준값은 strategy.py에 적힌 값(= moonwon/unit-ops daa1888). W가 비어 있으면 그 봇과 똑같이 움직인다.
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

# (상수 이름, 정수인가, 정수일 때 하한). "A.B"는 dict 상수 A의 키 B. 모두 실행 중에 읽히고 기준값이 0이 아닌 것
KNOBS: tuple[tuple[str, bool, int], ...] = (
    ("KILL_VALUE", False, 0),
    ("ESCORT_VALUE", False, 0),
    ("EVICT_WEIGHT", False, 0),
    ("ECON_WEIGHT", False, 0),
    ("RAID_STEAL", False, 0),
    ("SQUAD_WEIGHT", False, 0),
    ("RUSH_VALUE", False, 0),
    ("RUSH_CAPTURE", False, 0),
    ("PICKET_VALUE", False, 0),
    ("RETAKE_VALUE", False, 0),
    ("RETAKE_CAPTURE", False, 0),
    ("OPENING_NEUTRAL", False, 0),
    ("SH_COST_BASE", False, 0),
    ("FLAG_GUARD_WEIGHT", False, 0),
    ("TRADE_BOOST", False, 0),
    ("FLAG_INERTIA", False, 0),
    ("HALL_VALUE_PER_TURN", False, 0),
    ("FUNCTION_VALUE.ENG", False, 0),
    ("DEPOT_VALUE", False, 0),
    ("ETA_OFFSET", False, 0),
    ("MAX_FLAGS", True, 1),
    ("SQUAD_SIZE", True, 1),
    ("RUSH_EXTRA", True, 0),
    ("MIN_WARRIORS", True, 0),
)
Z_MAX = 2.5  # 배수 범위 exp(±2.5) ≈ 0.08 ~ 12

# 학습한 가중치: 상수 이름 → FEATURES 순서의 가중치. 없는 상수는 기준값 그대로.
# 2026-09-30 ES 2차 250세대(runs/es/20260930-032953/theta_g250.json) — docs/benchmarks.md "학습 (진화 전략)"
W: dict[str, list[float]] = {
    "KILL_VALUE": [0.424, -0.020, -0.027, 0.306, 0.261, 0.170, 0.078, 0.325],
    "ESCORT_VALUE": [-0.257, -0.256, 0.146, -0.093, 0.060, -0.043, -0.291, 0.266],
    "EVICT_WEIGHT": [0.132, -0.489, -0.143, -0.225, 0.541, 0.190, 0.339, 0.079],
    "ECON_WEIGHT": [0.177, 0.044, -0.447, 0.292, -0.270, -0.091, 0.115, -0.236],
    "RAID_STEAL": [-0.089, -0.191, 0.324, 0.001, -0.121, 0.081, -0.653, 0.028],
    "SQUAD_WEIGHT": [0.084, -0.300, 0.078, 0.058, 0.071, -0.284, 0.442, -0.145],
    "RUSH_VALUE": [0.001, 0.079, -0.180, 0.076, 0.179, -0.072, -0.008, 0.362],
    "RUSH_CAPTURE": [-0.264, 0.068, -0.228, 0.116, 0.127, -0.333, 0.027, 0.355],
    "PICKET_VALUE": [-0.257, 0.266, 0.241, 0.144, 0.039, 0.038, -0.196, 0.060],
    "RETAKE_VALUE": [0.350, -0.026, 0.015, 0.235, -0.395, 0.353, 0.111, -0.182],
    "RETAKE_CAPTURE": [0.564, -0.279, -0.026, 0.498, 0.087, -0.156, -0.025, 0.268],
    "OPENING_NEUTRAL": [1.104, -0.711, -0.355, 0.135, 0.409, 0.409, -0.076, 0.065],
    "SH_COST_BASE": [-0.130, 0.496, 0.284, 0.071, 0.013, -0.156, 0.074, 0.407],
    "FLAG_GUARD_WEIGHT": [0.569, -0.264, -0.319, -0.245, -0.077, 0.342, 0.486, -0.002],
    "TRADE_BOOST": [-0.213, 0.313, -0.173, -0.057, 0.011, -0.098, -0.161, -0.245],
    "FLAG_INERTIA": [0.263, -0.041, -0.110, 0.089, -0.272, -0.215, 0.122, -0.284],
    "HALL_VALUE_PER_TURN": [0.593, -0.344, -0.281, -0.054, 0.235, -0.163, 0.261, 0.051],
    "FUNCTION_VALUE.ENG": [0.269, -0.520, 0.182, 0.026, 0.123, 0.274, 0.004, 0.064],
    "DEPOT_VALUE": [-0.480, 0.007, 0.072, -0.408, -0.207, 0.500, 0.176, 0.090],
    "ETA_OFFSET": [-0.665, -0.236, -0.120, -0.034, 0.104, -0.069, -0.374, -0.104],
    "MAX_FLAGS": [-0.444, -0.057, 0.103, -0.236, -0.526, -0.171, 0.314, 0.007],
    "SQUAD_SIZE": [-0.247, -0.150, 0.501, 0.027, 0.013, 0.152, -0.156, 0.072],
    "RUSH_EXTRA": [-0.865, 0.038, 0.411, 0.133, -0.390, -0.059, -0.075, 0.065],
    "MIN_WARRIORS": [-0.451, 0.443, -0.493, 0.184, -0.226, 0.032, 0.111, -0.353],
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
