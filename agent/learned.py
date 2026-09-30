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
    # 성혁 기능(strategy.py "성혁 테마 브랜치 기능", 스위치를 켰을 때만 쓰인다). 학생회관·공학관 감쇠 값은 위
    # HALL_VALUE_PER_TURN · FUNCTION_VALUE.ENG 배수를 따른다
    ("HOSPITAL_ISOLATED", False, 0),
    ("STATION_BASE", False, 0),
    ("FUNCTION_VALUE.LIBRARY", False, 0),
    ("SH_ESCORT_T1", True, 0),
    ("SH_ESCORT_T2", True, 0),
    ("SH_ESCORT_T3", True, 0),
    # 성혁 decoy-flex 기능 (양동·암살·기동대, 스위치를 켰을 때만 쓰인다)
    ("DIVERSION_VALUE", False, 0),
    ("DIVERSION_CAPTURE", False, 0),
    ("ASSASSIN_BOOST", False, 0),
    ("MOBILE_WEIGHT", False, 0),
)
Z_MAX = 2.5  # 배수 범위 exp(±2.5) ≈ 0.08 ~ 12

# 학습한 가중치: 상수 이름 → FEATURES 순서의 가중치. 없는 상수는 기준값 그대로.
# 2026-09-30 ES 2차 240세대(runs/es/20260930-032953/theta_g240.json) — docs/benchmarks.md "학습 (진화 전략)".
# 250세대에서 바꿈: 서버 맵 85개 × 상대 25개에서 강한 상대·대 daa1888 모두 가장 고르고, 250세대가 약한 맵이 없다
W: dict[str, list[float]] = {
    "KILL_VALUE": [0.42455, -0.03432, -0.01533, 0.24788, 0.26375, 0.13231, 0.10532, 0.30905],
    "ESCORT_VALUE": [-0.27687, -0.24518, 0.17388, -0.09252, 0.04673, -0.02556, -0.29185, 0.23342],
    "EVICT_WEIGHT": [0.14564, -0.56915, -0.14477, -0.22051, 0.52821, 0.22367, 0.29976, 0.07904],
    "ECON_WEIGHT": [0.17134, 0.02926, -0.45157, 0.29497, -0.29362, -0.14246, 0.07467, -0.233],
    "RAID_STEAL": [-0.08597, -0.25579, 0.30853, -0.00039, -0.12478, 0.08953, -0.66961, 0.05097],
    "SQUAD_WEIGHT": [0.10312, -0.28716, 0.10492, 0.01348, 0.0889, -0.27744, 0.4533, -0.19405],
    "RUSH_VALUE": [0.00287, 0.12723, -0.20374, 0.06584, 0.12606, -0.08165, -0.05362, 0.38238],
    "RUSH_CAPTURE": [-0.22034, 0.00234, -0.20624, 0.15466, 0.17462, -0.33043, 0.02555, 0.33416],
    "PICKET_VALUE": [-0.27572, 0.25835, 0.23046, 0.21215, 0.04602, 0.10095, -0.20686, 0.0571],
    "RETAKE_VALUE": [0.29196, -0.05543, 0.06026, 0.23477, -0.38453, 0.35969, 0.11961, -0.18705],
    "RETAKE_CAPTURE": [0.60021, -0.26542, -0.03583, 0.53491, 0.07694, -0.19673, -0.05755, 0.24468],
    "OPENING_NEUTRAL": [1.10827, -0.70976, -0.36358, 0.15063, 0.36644, 0.39819, -0.02728, 0.08278],
    "SH_COST_BASE": [-0.11603, 0.46453, 0.27365, 0.03581, 0.04685, -0.17086, 0.04822, 0.39623],
    "FLAG_GUARD_WEIGHT": [0.5662, -0.28577, -0.34778, -0.252, -0.0801, 0.31129, 0.4876, 0.03749],
    "TRADE_BOOST": [-0.18822, 0.36311, -0.1778, -0.02837, 0.03, -0.11202, -0.09395, -0.24062],
    "FLAG_INERTIA": [0.28647, -0.05265, -0.08694, 0.10897, -0.31454, -0.15882, 0.09004, -0.27118],
    "HALL_VALUE_PER_TURN": [0.58614, -0.35029, -0.2836, -0.03102, 0.24994, -0.15184, 0.2541, 0.06781],
    "FUNCTION_VALUE.ENG": [0.25706, -0.51276, 0.21038, 0.01392, 0.09004, 0.27213, 0.02413, 0.05566],
    "DEPOT_VALUE": [-0.4749, 0.00286, 0.07427, -0.39371, -0.14741, 0.46412, 0.16542, 0.09247],
    "ETA_OFFSET": [-0.63618, -0.30009, -0.0729, -0.06166, 0.09889, -0.05808, -0.39458, -0.05347],
    "MAX_FLAGS": [-0.4119, -0.11714, 0.11507, -0.27159, -0.50012, -0.1712, 0.32799, 0.00224],
    "SQUAD_SIZE": [-0.26732, -0.11757, 0.48021, -0.00629, 0.01396, 0.09619, -0.184, 0.09318],
    "RUSH_EXTRA": [-0.81017, 0.05034, 0.4105, 0.09637, -0.35387, -0.04907, -0.07702, 0.05754],
    "MIN_WARRIORS": [-0.45949, 0.43464, -0.43995, 0.15325, -0.27062, 0.05219, 0.13342, -0.30375],
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
