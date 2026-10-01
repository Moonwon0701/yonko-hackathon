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
    "KILL_VALUE": [0.97505, -0.36714, 0.14479, 0.03421, 0.11932, 0.21943, 0.00398, -0.09722],
    "ESCORT_VALUE": [0.47616, -0.1781, 0.16384, -0.27497, 0.36965, -0.07777, -0.06865, 0.28868],
    "EVICT_WEIGHT": [-0.18887, -0.28187, -0.0763, 0.00225, 0.15148, 0.22094, 0.2088, 0.30489],
    "ECON_WEIGHT": [-0.31353, 0.10286, -0.07697, 0.05327, -0.27219, -0.16937, -0.36198, -0.10022],
    "RAID_STEAL": [-0.27423, -0.27397, -0.06342, -0.49908, 0.06956, 0.20929, -0.78198, 0.20478],
    "SQUAD_WEIGHT": [0.03289, 0.30768, 0.1726, 0.43524, -0.00216, 0.19449, 0.5672, -0.25038],
    "RUSH_VALUE": [-0.00701, -0.6435, -0.38324, 0.15615, 0.01041, -0.01926, -0.20585, 0.036],
    "RUSH_CAPTURE": [-0.09156, 0.21482, 0.12302, 0.05133, -0.31157, -0.51408, -0.28585, 0.03756],
    "PICKET_VALUE": [-0.02454, -0.29599, 0.00124, 0.07024, 0.08783, -0.27205, -0.11412, 0.21055],
    "RETAKE_VALUE": [0.17727, 0.21922, -0.14145, -0.09338, -0.58598, 0.32562, 0.05671, -0.01943],
    "RETAKE_CAPTURE": [0.9088, -0.06757, 0.19457, -0.09702, -0.10241, 0.05265, 0.09836, 0.22287],
    "OPENING_NEUTRAL": [1.04458, -0.51299, -0.12293, -0.07732, 0.2564, -0.21886, 0.40457, 0.12984],
    "SH_COST_BASE": [-0.2334, 0.5351, 0.47108, -0.27652, -0.14455, -0.2313, -0.13041, 0.12571],
    "FLAG_GUARD_WEIGHT": [0.85461, 0.06411, -0.14462, -0.15744, -0.00723, 0.30201, 0.17408, -0.11608],
    "TRADE_BOOST": [0.10226, 0.30146, -0.16901, -0.34517, 0.21365, 0.46834, 0.0219, -0.18407],
    "FLAG_INERTIA": [0.23655, -0.05971, -0.04406, 0.02588, 0.07179, 0.31382, 0.37485, -0.22211],
    "HALL_VALUE_PER_TURN": [0.93087, -0.23958, -0.36553, -0.04052, -0.05152, -0.464, 0.70584, 0.0528],
    "FUNCTION_VALUE.ENG": [0.67335, -0.97191, 0.31167, 0.19702, -0.04545, 0.24315, -0.40474, 0.15245],
    "DEPOT_VALUE": [-0.52924, 0.1711, -0.09622, -0.18319, 0.06858, 0.10888, -0.04256, 0.1228],
    "ETA_OFFSET": [-0.73128, -0.15422, 0.02319, -0.09794, -0.30638, 0.30402, -0.3921, 0.32659],
    "MAX_FLAGS": [-0.2882, -0.19128, 0.17423, -0.23829, -0.2952, 0.02862, 0.177, -0.38674],
    "SQUAD_SIZE": [-0.00356, -0.24725, 0.24149, 0.1162, -0.25851, 0.18366, -0.1082, 0.28528],
    "RUSH_EXTRA": [-0.29451, -0.13933, 0.54649, 0.19009, 0.16931, -0.4583, 0.17945, -0.08784],
    "MIN_WARRIORS": [-0.47155, 0.47026, 0.12218, -0.24856, -0.02286, -0.19225, 0.13453, -0.27579],
    "HOSPITAL_ISOLATED": [-0.37891, -0.65643, 0.21523, 0.08695, -0.09821, -0.20628, 0.02428, -0.33321],
    "STATION_BASE": [0.03489, 0.13882, -0.06537, -0.19718, 0.01562, -0.09505, 0.04221, -0.55382],
    "FUNCTION_VALUE.LIBRARY": [0.24642, -0.09808, -0.06839, -0.13987, -0.43735, 0.22556, -0.28527, -0.07984],
    "SH_ESCORT_T1": [0.29135, 0.42153, 0.00266, 0.19229, 0.02671, -0.05877, 0.23002, -0.14024],
    "SH_ESCORT_T2": [-0.3197, -0.16337, 0.12218, -0.15964, -0.0213, -0.15544, 0.05428, -0.00691],
    "SH_ESCORT_T3": [0.34876, 0.35981, 0.04174, -0.22272, -0.17704, 0.36235, -0.27659, 0.08337],
    "DIVERSION_VALUE": [0.48353, 0.04224, 0.22119, -0.30818, 0.01401, -0.29818, -0.37232, 0.25505],
    "DIVERSION_CAPTURE": [0.54613, -0.05818, -0.24042, 0.36271, -0.00874, -0.08892, 0.2743, -0.01324],
    "ASSASSIN_BOOST": [0.24336, -0.04481, 0.16005, -0.31901, 0.02803, 0.27923, -0.1541, -0.10608],
    "MOBILE_WEIGHT": [0.00357, 0.24031, 0.23642, 0.25967, 0.10425, 0.31291, 0.15797, 0.24154],
    "EARLY_GUARD_WEIGHT": [-0.00576, -0.19451, -0.2377, -0.03413, 0.03392, 0.16989, 0.14308, -0.241],
    "EARLY_GUARD": [0.27392, -0.05809, 0.03206, 0.04118, 0.18512, 0.12002, -0.08545, 0.03418],
    "EARLY_SLACK": [-0.06733, 0.20063, -0.31315, -0.02405, -0.19799, -0.02087, -0.07104, -0.08316],
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
