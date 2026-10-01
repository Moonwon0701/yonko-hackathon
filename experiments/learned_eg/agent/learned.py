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
# 2026-10-01 ES 3차(merged337) 180세대(runs/es/20260930-194817/theta_g180.json) — 9/30 20:00 제출본 337ab49(= 2차 240세대 +
# 성혁 기능 선별 조합) 위에서 240세대 W로 시작해 성혁 기능 상수 10개까지 학습. 새 시드 570판: 대 337ab49 58.1%, 대 26fa986
# 62.5%, 대 strong_wide 76.5%(285판) — docs/benchmarks.md "학습 (진화 전략)"
W: dict[str, list[float]] = {
    "KILL_VALUE": [0.88016, -0.15206, 0.06612, 0.50414, 0.30992, 0.0271, 0.27885, 0.20976],
    "ESCORT_VALUE": [0.10211, -0.02814, 0.1573, -0.13344, 0.2934, -0.12748, -0.18355, 0.17369],
    "EVICT_WEIGHT": [-0.00495, -0.58113, -0.23278, -0.01902, 0.39916, 0.22532, 0.28745, 0.26101],
    "ECON_WEIGHT": [0.16463, 0.21054, -0.30581, 0.30854, -0.43095, -0.45173, -0.21613, -0.15697],
    "RAID_STEAL": [-0.09828, -0.38503, 0.3322, -0.34338, -0.34911, 0.17948, -0.56376, -0.11846],
    "SQUAD_WEIGHT": [0.302, 0.09742, -0.08391, -0.08395, 0.31279, -0.13202, 0.44849, 0.03877],
    "RUSH_VALUE": [0.24247, -0.22453, -0.20108, -0.01388, -0.01495, 0.05276, -0.16665, 0.30784],
    "RUSH_CAPTURE": [-0.10411, -0.03345, -0.10429, 0.35194, -0.106, -0.25124, -0.03345, 0.10243],
    "PICKET_VALUE": [-0.31509, -0.02625, 0.11192, 0.34237, 0.03039, 0.09347, -0.09119, 0.41963],
    "RETAKE_VALUE": [0.2069, -0.14457, 0.07071, -0.00978, -0.52928, 0.40952, 0.33123, -0.02584],
    "RETAKE_CAPTURE": [0.67849, 0.06915, 0.01588, 0.38417, -0.05587, -0.19233, 0.18371, 0.0313],
    "OPENING_NEUTRAL": [1.06096, -0.5131, -0.2446, 0.00497, 0.3689, 0.20704, 0.26435, -0.0027],
    "SH_COST_BASE": [0.18271, 0.53827, 0.12976, -0.06662, -0.19991, -0.08947, 0.03522, 0.0595],
    "FLAG_GUARD_WEIGHT": [0.92275, -0.18547, -0.22129, -0.24658, -0.17924, 0.16005, 0.11945, -0.04456],
    "TRADE_BOOST": [-0.0177, 0.28622, -0.40943, -0.11136, 0.12278, -0.00127, -0.33085, -0.14665],
    "FLAG_INERTIA": [0.242, -0.0831, 0.17953, 0.02258, -0.09343, 0.03961, 0.01273, -0.10047],
    "HALL_VALUE_PER_TURN": [0.75166, -0.35586, -0.2315, 0.06584, 0.11123, -0.36559, 0.35452, -0.01576],
    "FUNCTION_VALUE.ENG": [0.27399, -0.75548, 0.41558, -0.11922, -0.06715, 0.52188, -0.30873, 0.14298],
    "DEPOT_VALUE": [-0.51451, -0.02377, 0.10212, -0.2569, -0.10995, 0.19589, 0.0503, -0.05612],
    "ETA_OFFSET": [-0.70466, -0.05988, 0.09169, -0.20581, -0.07133, 0.10107, -0.55133, 0.16328],
    "MAX_FLAGS": [-0.44529, -0.10653, -0.09385, -0.39415, -0.35656, -0.09523, 0.25962, -0.15452],
    "SQUAD_SIZE": [0.06266, -0.3115, 0.50399, -0.12255, -0.10435, -0.00904, 0.09623, 0.10241],
    "RUSH_EXTRA": [-0.60667, -0.06461, 0.47538, 0.2067, -0.05329, -0.17812, 0.32879, 0.20568],
    "MIN_WARRIORS": [-0.38184, 0.44695, -0.28336, -0.09346, -0.32669, 0.12102, 0.28364, -0.66811],
    "HOSPITAL_ISOLATED": [-0.14363, -0.29568, -0.00615, -0.23845, -0.08517, -0.1689, 0.0309, 0.02665],
    "STATION_BASE": [-0.18467, 0.19768, -0.18283, -0.13371, 0.18101, -0.1295, 0.00854, -0.26363],
    "FUNCTION_VALUE.LIBRARY": [0.20297, -0.00682, -0.05635, -0.25611, -0.20512, -0.00135, -0.21154, -0.10979],
    "SH_ESCORT_T1": [0.17918, 0.02367, 0.01982, -0.07179, 0.0447, 0.01673, 0.22982, -0.14124],
    "SH_ESCORT_T2": [-0.38515, -0.22019, 0.02996, -0.24336, 0.1449, -0.34528, 0.02463, -0.16552],
    "SH_ESCORT_T3": [0.40129, 0.25945, -0.31619, -0.15829, -0.15232, 0.21646, -0.19606, 0.01002],
    "DIVERSION_VALUE": [-0.00436, -0.02097, 0.23743, -0.11306, -0.11522, -0.37111, -0.25235, 0.083],
    "DIVERSION_CAPTURE": [-0.12784, -0.01692, 0.00084, -0.24469, 0.26883, 0.0974, 0.30406, 0.07312],
    "ASSASSIN_BOOST": [0.10882, 0.17623, 0.27995, -0.13281, 0.01684, 0.37032, -0.06377, 0.0077],
    "MOBILE_WEIGHT": [0.00207, 0.124, 0.07848, 0.11002, -0.02516, 0.07748, 0.35575, 0.12175],
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
