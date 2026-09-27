"""규칙 수치. docs/rules-original.md 부록과 starter/_generated.py의 BALANCE에서 옮겼다.

tests/test_sim_rules.py가 이 값들이 공식 BALANCE와 같은지 확인한다. 우리 봇(agent/)의 상수는
일부러 가져다 쓰지 않는다 — 봇과 엔진이 같은 실수를 공유하면 테스트가 잡지 못한다.
"""

SIZE = 15
CENTER = (7, 7)
TOTAL_TURNS = 160

FIRST_TURN_MS = 3000
TURN_MS = 300

TEAMS = ("Y", "K")
OTHER = {"Y": "K", "K": "Y"}
KINDS = ("F", "W", "S")
DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}

UNIT_COST = {"F": 5, "W": 3, "S": 2}
UNIT_VALUE = {"F": 5, "W": 3, "S": 2}  # 160턴 판정 ③ 생존 병력 환산

START_RESOURCE = 10
BASE_INCOME = 10
HALL_BONUS = 2
RESOURCE_CAP = 40

CAPTURE_COST = 2
PLAZA_MULTIPLIER = 2
MIN_CAPTURE_COST = 1
LIBRARY_DISCOUNT = 1
ENG_DISCOUNT = 1
ENG_COST_FLOOR = 2
DEPOT_BONUS = 15
WATCH_RANGE = 3
SCOUT_RANGE = 2
PLAZA_SCORE = 3

TELE_MAX_UNITS = 5
TELE_MIN_STATIONS = 2

# 맵 생성 (BALANCE["mapgen"], BALANCE["regions"])
OBSTACLE_PAIRS = 10
MIN_BASE_DISTANCE = 12
MAX_PLACE_ATTEMPTS = 4000
SIDE_SCORE = (1, 2)  # 신촌·안암 건물
CENTER_SCORE = (2, 4)  # 중앙 건물
CENTRAL_Y_MARGIN = 2  # 중앙 건물은 y 2~12
REGIONS = {"sinchon": (0, 4), "center": (5, 9), "anam": (10, 14)}
SIDE_KINDS = ("HALL", "LIBRARY", "ENG", "HOSPITAL", "STATION")
CENTER_KINDS = ("STATION", "WATCH", "DEPOT")  # 각 2개(점대칭 짝)

# 출력 한도 (대회 서버 안내 페이지)
STDOUT_MAX_BYTES = 64 * 1024
STDOUT_MAX_LINES = 4096
LINE_MAX_BYTES = 1024
STDERR_MAX_BYTES = 1024 * 1024
