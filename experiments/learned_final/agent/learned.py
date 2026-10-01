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
    # 선제 수비 (10/1, EARLY_GUARD > 0일 때 쓰인다). EARLY_GUARD가 GUARD_RADIUS(3) 이하로 내려가면 사실상 꺼진다
    ("EARLY_GUARD_WEIGHT", False, 0),
    ("EARLY_GUARD", True, 0),
    ("EARLY_SLACK", True, 0),
)
Z_MAX = 2.5  # 배수 범위 exp(±2.5) ≈ 0.08 ~ 12

# 학습한 가중치: 상수 이름 → FEATURES 순서의 가중치. 없는 상수는 기준값 그대로.
# 2026-10-01 ES 4차(early_guard) 180세대(runs/es/20261001-034749/theta_g180.json) — e30333c(3차 180세대 + 선제 수비)에
# 성혁 hunters(efb71da)의 기동대 수정을 켠 봇 위에서 3차 180세대 W로 시작해 선제 수비 상수 3개까지 학습. 새 시드 44000~44599
# 600판씩: 대 e30333c 53.2%, 대 074803e 57.3%(e30333c 53.7), 대 strong_wide 80.3%(78.2) — docs/benchmarks.md "학습 (진화 전략)"
W: dict[str, list[float]] = {
    "KILL_VALUE": [0.97776, -0.45631, 0.10599, 0.05666, 0.13457, 0.22763, 0.02618, 0.01233],
    "ESCORT_VALUE": [0.41093, -0.19349, 0.10533, -0.21905, 0.46881, -0.15708, -0.02328, 0.35294],
    "EVICT_WEIGHT": [-0.07712, -0.35203, -0.20235, 0.04237, 0.16011, 0.11799, 0.26598, 0.30857],
    "ECON_WEIGHT": [-0.2263, 0.19298, -0.17377, 0.07695, -0.30964, -0.11465, -0.43512, -0.07404],
    "RAID_STEAL": [-0.33642, -0.33085, -0.07726, -0.483, 0.03881, 0.22342, -0.69509, 0.14684],
    "SQUAD_WEIGHT": [-0.00889, 0.23708, 0.15316, 0.32873, 0.05548, 0.24437, 0.5726, -0.36414],
    "RUSH_VALUE": [-0.01451, -0.61216, -0.2616, 0.14876, 0.05075, 0.10452, -0.28587, 0.12495],
    "RUSH_CAPTURE": [-0.17396, 0.25119, 0.02156, 0.08176, -0.3125, -0.42647, -0.30172, 0.02971],
    "PICKET_VALUE": [-0.12447, -0.27407, -0.07006, 0.13866, 0.1618, -0.24513, -0.09739, 0.25432],
    "RETAKE_VALUE": [0.21334, 0.15283, -0.08987, 0.01176, -0.6097, 0.29062, 0.07027, -0.0216],
    "RETAKE_CAPTURE": [0.8649, -0.0399, 0.08698, -0.02209, -0.02937, -0.008, 0.17916, 0.31046],
    "OPENING_NEUTRAL": [0.97981, -0.60204, -0.15652, -0.02557, 0.32425, -0.10896, 0.34404, 0.14796],
    "SH_COST_BASE": [-0.21513, 0.61837, 0.46975, -0.2241, -0.08042, -0.21691, -0.15969, 0.07587],
    "FLAG_GUARD_WEIGHT": [0.8567, 0.0168, -0.03244, -0.24879, -0.01338, 0.39774, 0.12148, -0.05561],
    "TRADE_BOOST": [0.11773, 0.25208, -0.17338, -0.32975, 0.24295, 0.45584, 0.01633, -0.25908],
    "FLAG_INERTIA": [0.2313, -0.02907, -0.02592, -0.10121, -0.00499, 0.24366, 0.34224, -0.18408],
    "HALL_VALUE_PER_TURN": [0.85905, -0.27676, -0.39968, -0.13586, -0.13361, -0.43549, 0.70673, 0.10193],
    "FUNCTION_VALUE.ENG": [0.65552, -1.00483, 0.29473, 0.14339, -0.0238, 0.27094, -0.42976, 0.05849],
    "DEPOT_VALUE": [-0.50296, 0.13519, -0.10351, -0.19471, 0.14464, 0.05015, -0.05825, 0.06714],
    "ETA_OFFSET": [-0.7068, -0.08288, 0.04994, -0.09934, -0.32737, 0.20676, -0.3665, 0.34],
    "MAX_FLAGS": [-0.34706, -0.08478, 0.0569, -0.23299, -0.3254, -0.02683, 0.11122, -0.37275],
    "SQUAD_SIZE": [-0.11191, -0.33416, 0.26734, -0.00096, -0.20431, 0.13441, -0.09, 0.29231],
    "RUSH_EXTRA": [-0.44791, -0.23104, 0.41576, 0.17624, 0.05278, -0.44216, 0.17271, -0.14671],
    "MIN_WARRIORS": [-0.4906, 0.4737, 0.18932, -0.22921, -0.08465, -0.22325, 0.19255, -0.27705],
    "HOSPITAL_ISOLATED": [-0.32022, -0.62491, 0.21208, -0.00834, 0.01016, -0.21851, -0.02137, -0.36134],
    "STATION_BASE": [0.04131, 0.17935, -0.0438, -0.11014, 0.02979, -0.09259, 0.00491, -0.50137],
    "FUNCTION_VALUE.LIBRARY": [0.21969, -0.12119, -0.08764, -0.23537, -0.46589, 0.30284, -0.17301, -0.11468],
    "SH_ESCORT_T1": [0.19313, 0.37393, 0.02833, 0.1209, -0.04127, -0.10648, 0.27214, -0.22232],
    "SH_ESCORT_T2": [-0.35683, -0.13961, 0.12247, -0.18636, -0.06256, -0.15793, 0.02527, -0.0921],
    "SH_ESCORT_T3": [0.36949, 0.34828, 0.02873, -0.24993, -0.16053, 0.37805, -0.32355, 0.04555],
    "DIVERSION_VALUE": [0.3759, -0.04988, 0.20542, -0.35218, -0.05194, -0.36473, -0.33435, 0.23225],
    "DIVERSION_CAPTURE": [0.56211, -0.06191, -0.34514, 0.22888, -0.08546, -0.14436, 0.15061, -0.10355],
    "ASSASSIN_BOOST": [0.25407, -0.07781, 0.13313, -0.23692, -0.08986, 0.3629, -0.05905, -0.06706],
    "MOBILE_WEIGHT": [0.00135, 0.29749, 0.3032, 0.12561, 0.04829, 0.40974, 0.1389, 0.24047],
    "EARLY_GUARD_WEIGHT": [-0.01037, -0.25813, -0.18846, -0.00361, 0.06354, 0.11118, 0.10251, -0.24997],
    "EARLY_GUARD": [0.35183, -0.06937, 0.03246, 0.00358, 0.23983, 0.08832, -0.13447, 0.00232],
    "EARLY_SLACK": [-0.05386, 0.18101, -0.4297, -0.10846, -0.09125, -0.04324, -0.15989, -0.07782],
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
