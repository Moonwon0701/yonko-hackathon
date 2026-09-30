"""World를 받아 다음 행동을 결정하는 에이전트 두뇌: decide(world) -> actions.

M1 — 건물 효용 점수 + 깃발병 목표 분산 (M0 기준선은 tests/lv2_port.py에 보관)
- 건물 효용 = (추정 점수 + 기능 가치) / (도착 거리 + 점령 단계 수 + ETA_OFFSET)
- 깃발병을 한 명씩, 효용이 가장 높은 (깃발병, 건물) 짝부터 배정한다. 한 건물에는 한 명만 간다.
- 점령 비용은 이번 턴 수입까지 셈해 필요한 만큼만 남기고, 나머지로 생산한다.
- 이번 턴 점령할 건물이 둘 이상이면 효용 순으로 PRIORITY를 낸다.

M2 — 위험 판단 + 전투병 과제 + 깃발 뽑기 (docs/roadmap.md)
- 위협 맵: 다음 턴 적 전투병이 각 칸에 모일 수 있는 최대 인원 (이번 턴 본진 생산분 포함)
- 전투병 과제: 적 깃발병 처치(건물 위면 깃발 뽑기·방어 가치 추가), 점령 중인 우리 깃발병 호위.
  과제마다 이기는 데 필요한 인원이 있고, 인원을 채울 수 있는 과제 중 가치/거리가 큰 것부터 배정한다.
- 깃발병은 이번 턴 우리 전투병보다 적 전투병이 더 모일 수 있는 칸에 들어가지 않는다(피하거나 대기).
- 깃발 뽑기: 적 깃발병이 있는 건물은 전투병 과제가 잡혔을 때만 깃발병 목표가 되고, 깃발병은 전투병이
  이번 턴 도착할 때까지 한 칸 앞에서 기다린다(깃발병만 들어가면 경합이라 점령이 안 된다).
- 전투병 수: 적 전투병 + 1 (최소 MIN_WARRIORS)

구조 — 행동 트리(BT). decide는 TURN_TREE를 한 번 실행한다(트리 전체: tree_text(), 조립은 파일 맨 끝,
노드 정의는 agent/bt.py). 유닛이 하는 일은 모두 과제(Task) 하나로 나타낸다: 점령(깃발병 1명)과
처치·호위·지키기(전투병 need명).
- TURN_TREE(Sequence): 상황 읽기 → PHASE_TREE → 깃발병 1차 → 전투병 → 깃발병 2차 → 우선순위
- PHASE_TREE(Selector): 처음 성립하는 국면 가지가 이번 턴 과제 목록의 구성(과제 종류와 가중치)을 정한다
- 배정·생산·이동 단계는 국면이 정한 과제 목록만 보고 움직인다(국면별 분기가 트리 밖에 없다)
- FLAG_TREE(Selector): 깃발병 한 명의 다음 칸 — 안전하게 다가가기 → 대기 → 피하기 → 그래도 다가가기
- 효용 배정기(assign_flags, assign_warriors)는 트리의 행동 잎 안에서 호출하는 부품이다.

M3 — 국면 선택 (위층). 국면 = 이번 턴 과제 목록을 만드는 방법(과제 종류 + 가중치).
- Selector: 위협 대응 → 굳히기 → 공격 → 확장. 위에서부터 처음 조건이 성립하는 국면을 고른다.
  - 위협 대응(THREAT): 적 깃발병이 GUARD_RADIUS 안에 들어온 우리 건물의 점수 합 ≥ THREAT_PRESSURE
  - 굳히기(HOLD): LATE_TURN 이후이고 추정 점수가 앞섬
  - 공격(ATTACK): 우리 전투병이 적보다 ATTACK_MARGIN 이상 많고 상대가 건물을 갖고 있음
  - 확장(EXPAND): 그 밖 (M2까지의 동작)
- 국면 유지(Latch 노드): 더 급한 국면으로는 바로 바꾸고, 덜 급한 국면으로는 지금 국면의 조건이 HOLD_TURNS턴
  연속 풀렸을 때만 내려간다(국면이 턴마다 흔들리지 않게).
- 지키기 과제: 적 깃발병이 GUARD_RADIUS 안에 있는 우리 건물에 전투병을 세운다(가치 × 국면별 배수).
- 몰아내기 과제: 적 전투병이 EVICT_RADIUS 안에 온 우리 핵심 건물(학생회관·공학관·병원)에 전투병을 세운다.
  적이 전투병을 먼저 모아 두고 깃발병을 나중에 들이는 경우를 막는다(9/28 리더보드 패배 분석).

현진 테마 브랜치(hyunjin/defense-econ) — 별동대 과제: 위험한 목표(상대 소유이거나 적 전투병이 닿는 건물)로 가는 깃발병
1명(SECOND_SQUAD_TURN부터 2명)의 다음 칸에 전투병 SQUAD_SIZE명을 먼저 보내, 가는 길에서도 깃발병과 함께 움직인다.
공학관 러시: ENG_RUSH_UNTIL턴까지 상대 캠퍼스 공학관에 전투병을 보내고 깃발병이 공학관을 먼저 노린다(흉내 봇 eng_rush의
러시 부분). 별동대가 그 공학관으로 가는 깃발병을 지킨다.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from types import SimpleNamespace

from agent.algorithms import (
    DEFAULT_ORDER,
    distance_map,
    manhattan,
    max_assignment,
    step_along,
    threat_map,
)
from agent.bt import Act, Condition, Latch, Node, Selector, Sequence
from agent.world import (
    BASE_INCOME,
    HALL_BONUS,
    TELE_MAX_UNITS,
    TOTAL_TURNS,
    UNIT_COST,
    Action,
    Building,
    Move,
    Pos,
    Priority,
    Spawn,
    Tele,
    World,
)

MIN_WARRIORS = 3  # 전투병 최소 인원 (적 전투병이 적어도 이만큼은 둔다)
SPARE_FLAGS = 1  # 목표 건물 수보다 이만큼 더 많은 깃발병까지만 만든다
MIN_FLAGS = 2  # 깃발병이 이보다 적으면 전투병보다 먼저 만든다 (목표가 있을 때만)
# 깃발병 총원 상한. 목표 건물 수만큼 깃발병을 만들면 20턴까지 깃발병에 35~75를 써서, 수입이 같은 상대보다
# 전투병이 10~15명 적었다(9/27·9/28 리더보드 리플레이 18경기). 전투병은 1:1로 상쇄되므로 이 차이가 그대로 남는다
MAX_FLAGS = 6
BEHIND_EXTRA_FLAGS = 1  # 상대가 건물을 더 가지면 깃발병 최소 인원에 더한다

# 점수를 모를 때의 기대값. 규칙: 신촌·안암 건물 1~2점, 중앙 건물 2~4점
SIDE_SCORE_GUESS = 1.5
CENTER_SCORE_GUESS = 3.0
SIDE_KINDS = {"HALL", "LIBRARY", "ENG", "HOSPITAL"}  # 역은 위치로 가린다(campus_stations)
CENTER_KINDS = {"WATCH", "DEPOT"}

# 기능 가치 (점수 단위)
HALL_VALUE_PER_TURN = 0.02  # 학생회관: 남은 턴 × 이 값 (초반일수록 크다)
DEPOT_VALUE = 2.0  # 보급소: 최초 점령 +15 자원, 팀별 건물당 1회
# 공학관: 전투병 값 3 → 2, 같은 자원으로 전투병 1.5배. 진 경기는 전투병(= 생산량) 차이로 벌어지므로
# 0.5 → 2.0으로 올렸다(main 상대 400경기 약 61% — docs/benchmarks.md)
FUNCTION_VALUE = {"LIBRARY": 0.5, "ENG": 2.0, "HOSPITAL": 0.5, "STATION": 0.3, "WATCH": 0.3}

ETA_OFFSET = 2  # 효용 분모에 더하는 값. 클수록 거리보다 건물 가치를 중시한다
KILL_VALUE = 1.0  # 적 깃발병 한 명 제거의 가치 (점수 단위)
# 요격: 이동 중인(건물 위가 아닌) 적 깃발병은 지금 칸이 아니라 앞질러 간다. 목적지 = 그 깃발병에서 가장 가까운 상대 것이
# 아닌 건물. "step" = 목적지 쪽 다음 칸, "goal" = 목적지 건물에서 기다림, "" = 끔(지금 칸). 처치 과제와 과제 없는 전투병의
# 공통 목표에 함께 쓴다. 양쪽이 동시에 움직이므로 지금 칸으로 가면 도착할 때 깃발병은 이미 한 칸 앞에 있다.
# 끔: "step"은 1672fe2 상대 54 / 50%, 흉내 봇 풀 79 → 83%, 서버 맵 main 상대 79.6 → 69.4%. "goal"은 13% (docs/benchmarks.md)
INTERCEPT = ""
# 미끼: DECOY_FROM~DECOY_UNTIL턴, 우리 깃발병이 DECOY_MIN_FLAGS명 이상이면 점령 중이 아닌 깃발병 중 적 전투병에 가장 가까운
# 1명을 미끼로 쓴다. 다음 턴 적 전투병이 닿지 못하는 칸(위협 0) 중 적 전투병에 가장 가까운 칸으로 가서, 적이 다가오면 물러나고
# 멈추면 다시 다가간다(사거리 끝에서 맴돌기). 그런 칸이 없으면 적 전투병에게서 가장 먼 이웃으로 도망친다. UNTIL 0 = 끔.
# 끔: 1672fe2 상대 1~160 / 1~60 / 20~100턴 33 / 38 / 45%, 깃발병 1명 추가해도 36 / 47%, 흉내 봇 풀 62~70% (지금 79%)
DECOY_FROM = 1
DECOY_UNTIL = 0
DECOY_MIN_FLAGS = 3
DECOY_EXTRA_FLAG = False  # 미끼 기간에 깃발병 목표 인원·총원 상한을 1명씩 늘린다(미끼로 빠지는 점령 인원을 메운다)
DANGER_DISCOUNT = 0.5  # 적 전투병이 닿는 건물은 깃발병 목표로서 가치를 이만큼 곱한다


# 국면별 과제 구성(종류·가중치)은 파일 끝 PHASE_TREE에 가지마다 적는다.
HOLD_TURNS = 3  # 덜 급한 국면으로 내려가려면 지금 국면의 조건이 이만큼 연속으로 풀려야 한다
GUARD_RADIUS = 3  # 적 깃발병이 이 거리 안에 있는 우리 건물은 위협받는 것으로 본다
THREAT_PRESSURE = 2.0  # 위협받는 우리 건물의 추정 점수 합이 이 이상이면 위협 대응
LATE_TURN = 110  # 굳히기: 이 턴 이후 추정 점수가 앞서면
ATTACK_MARGIN = 2  # 공격: 우리 전투병이 적보다 이만큼 많으면
# 몰아내기: 적 전투병이 이 거리 안에 온 우리 핵심 건물에 전투병을 세운다. 적 깃발병만 보던 지키기로는 적이 전투병을
# 먼저 건물 위·옆에 모아 두고 깃발병을 나중에 들이는 경우를 못 막았다(9/28 리더보드 패배 4경기 중 3경기)
EVICT_KINDS = {"HALL", "ENG", "HOSPITAL"}
EVICT_RADIUS = 2
EVICT_WEIGHT = 1.0
# 아래 셋은 문원 테마 브랜치(moonwon/eval-tuning, adffd5b)의 스위치를 그대로 옮긴 것. 기본값은 예전 동작과 같다.
# 경제 건물 몰아내기: 공학관·학생회관은 반경·가중치를 따로 둔다
ECON_KINDS = {"HALL", "ENG"}
ECON_EVICT_RADIUS = 2
ECON_WEIGHT = 1.0
# 이동 중 깃발병 호위: 우리 깃발병이 있는 칸마다 전투병 1명(가치 ESCORT_VALUE, 0 = 끔).
# 현진 브랜치에서 호위 + 2걸음을 함께 켬: a560165 상대 61% / 60% (시드 200~299 / 300~399), 흉내 봇 풀 평균 68.5 → 79%,
# 문원 브랜치 상대 49 → 58%, 서버 맵 main 상대 79.6%. 하나씩: 호위만 51.5%·풀 76%, 2걸음만 60.5%·풀 74% (docs/benchmarks.md)
ESCORT_VALUE = 1.0
# 경제 건물(ECON_KINDS) 지키기·몰아내기의 필요 인원 = ECON_DEFEND_REACH걸음 안의 적 전투병 + 1 (다음 턴 위협이 더 크면
# 그것 + 1). 1이면 예전과 같다. 흉내 봇 "공학관 러시"는 2칸 밖에서 다가오는 전투병 2명 + 깃발병 1명으로 우리 공학관을
# 빼앗았고, 그때 우리는 위협 0으로 보고 1명만 보냈다(문원 기록)
ECON_DEFEND_REACH = 2
# 전선: 적이 오기 전에, 점령을 끝낸 우리 건물 중 가장 노출된 곳에 전투병을 미리 세운다.
# 노출 순위 = 가장 가까운 적·중립 건물까지 거리 + FRONT_MARGIN_WEIGHT × (적 본진 거리 − 우리 본진 거리). 작을수록 전선
FRONT_COUNT = 3
FRONT_MARGIN_WEIGHT = 0.5
FRONT_NEED = 1  # 호위 없는 적 깃발병은 전투병 한 명으로 막힌다
# 우리 전투병이 적보다 이만큼 이상 많을 때만 세운다. 늘 세우면 적 깃발병을 쫓을 전투병이 모자라 예전 봇 상대로
# 떨어졌다(M4 72 → 62%, M3 96 → 87% — docs/benchmarks.md)
FRONT_SURPLUS = 10
# 급습: 상대 경제 건물(공학관 = 전투병 값 −1, 학생회관 = 수입 +2)에 전투병을 보내고 깃발병이 뒤따라 빼앗는다.
# 리더보드 상위 봇에게 진 경기는 모두 우리 공학관·학생회관을 잃고 생산력이 벌어지며 무너졌다 — 그 반대를 노린다
RAID_KINDS = {"ENG", "HALL"}
RAID_STEAL = 2.0  # 상대 경제 건물의 점령 가치에 더 곱하는 값
RAID_SURPLUS = -99  # 우리 전투병이 적 전투병 + 이 값 이상일 때만 급습한다
# 별동대(현진 테마 브랜치): 위험한 목표(상대 소유이거나 적 전투병이 닿는 건물)로 가는 깃발병에 전투병을 붙여, 가는 길의
# 다음 칸을 먼저 차지한다(호위는 점령을 시작한 뒤에만 붙는다). main 상대 시드 0~99 75%, 흉내 봇 풀 평균 55 → 62%(2개).
# 인원 1·2·3 / 가중치 3, 2개 시작 1·60·100턴도 비교했다 (docs/benchmarks.md, docs/llm-log/2026-09-2*-hyunjin-*)
SQUAD_SIZE = 5
SQUAD_WEIGHT = 1.0
SECOND_SQUAD_TURN = 30  # 이 턴부터 별동대 2개 (목표 건물이 서로 다른 깃발병 2명)
# 공학관 러시(흉내 봇 opponents/eng_rush.py의 러시 부분): ENG_RUSH_UNTIL턴까지 상대 캠퍼스 공학관에 전투병
# "위협 + ENG_RUSH_EXTRA"명(가치 ENG_RUSH_VALUE), 깃발병은 공학관 점령 가치 × ENG_RUSH_CAPTURE. 0이면 끔.
# 별동대 버전(26fae2a) 상대 시드 200~299: 20 / 40 / 60 / 80 / 100 / 160턴 → 53 / 55 / 63 / 65 / 65 / 60%, 80턴은 300~399 52%.
# 흉내 봇 풀 평균 62 → 69%, 서버 맵 main 상대 67 → 71%, main 69%·문원 49%는 그대로 (docs/benchmarks.md)
ENG_RUSH_UNTIL = 80
ENG_RUSH_EXTRA = 2
ENG_RUSH_VALUE = 6.0
ENG_RUSH_CAPTURE = 3.0
# 러시 접기: ENG_RUSH_GIVEUP턴이 지나도 상대 캠퍼스 공학관을 한 번도 가진 적이 없으면 그 경기는 러시(전투병·깃발병 가치 둘 다)를
# 그만둔다. 공학관 러시 흉내 봇에게 진 맵은 30턴에 상대 공학관을 가진 비율이 27%(이긴 맵 71%)였고, 80턴까지 러시에 묶인
# 전투병 때문에 중앙 건물(보급소·광장·역)을 내줬다. 0이면 끔.
# 끔: 30 / 40 / 50턴 → 2cdf9f1 상대 46 / 53.5 / 52%, 흉내 봇 풀 평균 79 / 81 / 80% (지금 79%, 공학관 러시 상대 56 → 64 / 68 / 64%).
# 40턴: moonwon/merge-squad 상대 48 → 57%, moonwon/unit-ops 상대 44 → 41% — 엇갈리고 모두 오차 안 (docs/benchmarks.md)
ENG_RUSH_GIVEUP = 0
# 수비대: GARRISON_UNTIL턴까지 우리 공학관·학생회관(GARRISON_KINDS) 위에 전투병 GARRISON_NEED명을 적이 오기 전에 세운다
# (가치 × GARRISON_WEIGHT). 몰아내기는 적 전투병이 온 뒤에 움직인다. 흉내 봇 풀에서 공학관을 잃는 경기가 절반쯤이었다. 0이면 끔.
# 끔: 40 / 80 / 160턴 × 1명 → 7001772 상대 55.5 / 53 / 46%, 3명 → 43.5 / 43 / 39%. 흉내 봇 풀 공학관 잃음 51%가 그대로
# (러시는 "위협 + 2"명이라 1명으로 못 막고, 3명은 적 깃발병 추격 인원을 뺏는다 — docs/benchmarks.md)
GARRISON_KINDS = {"ENG", "HALL"}
GARRISON_UNTIL = 0
GARRISON_NEED = 1
GARRISON_WEIGHT = 1.0

# ------------------------------------------------------------------ 성혁 테마: 현진 브랜치 복사본 위의 스위치 (2026-09-30)
# 전부 끄면(기본값) 현진 브랜치(7b8b67e)와 행동이 같다. 켠 조합은 docs/benchmarks.md에 100경기씩 적는다.

# 1. 별동대 인원 가변: 5명 고정 대신 "그 칸을 노리는 적 전투병 수 + 1"명을 SQUAD_MIN~SQUAD_MAX 안에서 쓴다.
#    적이 2칸 안에 없으면 최소(가볍게), 2명이면 3명(기준), 4명 이상이면 5명(최대). 턴이 아니라 상황으로 정한다.
SQUAD_FLEX = False
SQUAD_MIN = 1
SQUAD_MAX = 5
SQUAD_REACH = 2  # 별동대 칸에서 이 걸음 안의 적 전투병을 센다

# 2. 양동(V2): DIVERSION_FROM~DIVERSION_UNTIL턴, 주력이 미는 전선에서 가까워 지원할 수 있고 수비가 약한 건물 하나를 골라
#    전투병 "주변 적 + DIVERSION_EXTRA"명(2~DIVERSION_MAX)을 보내고 깃발병 점령 가치를 DIVERSION_CAPTURE배 한다. 목적은
#    건물 하나가 아니라 상대 방어 병력을 전선에서 분산시키는 것이다. 깊숙이 들어가지 않는다.
#    - 학생회관·공학관은 우선순위(DIVERSION_PRIORITY배)일 뿐, 교란하기 좋은 위치면 다른 건물도 목표가 된다.
#    - 우리 전투병이 DIVERSION_FRONT_REACH걸음 안에 DIVERSION_MIN_SUPPORT명 이상 있는 건물만 고른다(걸어서 잰 거리라
#      장애물로 막혀 돌아가야 하는 구석 건물은 저절로 빠진다).
#    - 한 목표를 DIVERSION_PATIENCE턴 안에 진전(소유자 변화)이 없으면 DIVERSION_COOLDOWN턴 접는다.
#    - 우리 전투병이 적 전투병의 DIVERSION_MIN_RATIO배에 못 미치면(밀리는 판) 하지 않는다. 0 = 끔.
DIVERSION_FROM = 0
DIVERSION_UNTIL = 120
DIVERSION_PRIORITY_KINDS = {"HALL", "ENG"}
DIVERSION_PRIORITY = 1.5
DIVERSION_ANY = True  # False면 우선순위 종류만 목표로 삼는다(V1)
DIVERSION_REACH = 2  # 목표 주변 이 걸음 안의 적 전투병 수 = 수비 병력
DIVERSION_MAX_DEF = 4  # 수비 병력이 이보다 많으면 허술하지 않다. 이미 고른 목표는 +1까지 참는다
DIVERSION_FRONT_REACH = 5
DIVERSION_MIN_SUPPORT = 4
DIVERSION_PATIENCE = 12
DIVERSION_COOLDOWN = 25
DIVERSION_MIN_RATIO = 0.8
DIVERSION_EXTRA = 1
DIVERSION_MAX = 6
DIVERSION_VALUE = 3.0
DIVERSION_CAPTURE = 1.5
DIVERSION_IN_THREAT = True  # THREAT 국면에서도 하는가 (THREAT가 대부분의 턴이라 끄면 거의 안 한다)

# 3. 전투병 과제 관성(성혁 9/29): 지난 턴에 전투병을 받은 과제는 거리를 WARRIOR_INERTIA만큼 깎아 계속 맡게 한다. 0 = 끔.
WARRIOR_INERTIA = 0

# 4. 점령 비용 반영(성혁 9/29): 가치 × COST_BASE / (COST_BASE + 실제 자원 비용). 0 = 끔.
#    광장은 PLAZA_SKIP_UNTIL턴 전에는 깃발병 목표에서 뺀다. 0 = 끔.
COST_BASE = 0.0
PLAZA_SKIP_UNTIL = 0

# 5. 점령을 마친 깃발병은 우리 건물 위에 남지 않고 요충지 1칸·나머지 2칸 비켜 대기한다(성혁 9/29).
IDLE_RETREAT = False
IDLE_KEEP = {"ENG": 1, "HALL": 1}
IDLE_KEEP_DEFAULT = 2

# 6. 건물 가치 V2(성혁 9/29): 공학관 3.0에서 5턴마다 0.2씩 25턴에 2.0, 학생회관 3.6에서 45턴에 1.8(하한), 보급소 3.5.
VALUES_V2 = False
ENG_EARLY_VALUE = 3.0
ENG_FLOOR = 2.0
HALL_EARLY_VALUE = 3.6
HALL_FLOOR = 1.8
DEPOT_VALUE_V2 = 3.5

# 7. 초반 깃발병 상한: EARLY_FLAG_TURN턴 전에는 총원을 EARLY_MAX_FLAGS명까지만(아낀 자원은 전투병으로). 0 = 끔.
EARLY_FLAG_TURN = 20
EARLY_MAX_FLAGS = 0

# 8. 역 가치 V2(성혁 9/29): 순간이동은 내 역이 2개 이상이라야 열린다. 가치는 조건에서 나온다 — ① STATION_MIN_LINK 이상 떨어진 다른
#    역이 있어야 하고(없으면 0) ② 짝을 완성하는 역이면 STATION_BASE + 가장 연계되는 역 주변 건물 가치 ③ 이미 짝이 있으면
#    STATION_EXTRA. 병원은 역 주변 가치에서 뺀다. False면 FUNCTION_VALUE의 0.3.
STATION_V2 = False
STATION_FIRST = 0.0  # 첫 역 — 아직 순간이동이 안 열린다
STATION_BASE = 2.0
STATION_EXTRA = 0.3
STATION_MIN_LINK = 4
STATION_NEIGHBOR = 3
STATION_NEIGHBOR_VALUE = {"ENG": 1.0, "DEPOT": 0.6, "HALL": 0.3}

# 9. 암살자(성혁 9/30): 경기 내내 전투병 1명을 "무방비해 보이는 적 깃발병"만 쫓는 암살자로 임명한다. 죽으면(있던 칸에 우리 전투병이
#    없으면) 이번 턴 전투병을 한 명 새로 만들어 그 자리를 잇는다. 유닛에 ID가 없어 칸으로 추적한다. 다른 과제에는 배정하지 않는다.
#    무방비 = 그 적 깃발병에서 ASSASSIN_GUARD_R걸음(맨해튼) 안에 적 전투병이 없음. 표적이 여럿이면 (건물 위면 그 건물 가치 + 1) × 인원 /
#    (1 + 거리)가 큰 것. 다음 칸은 적 전투병이 닿지 못하는 곳(위협 0)만 밟는다. 무방비 표적이 없으면 ASSASSIN_ROAM일 때 가장 가까운
#    적 깃발병 쪽으로 안전한 칸만 골라 다가간다.
ASSASSIN = False
ASSASSIN_GUARD_R = 2
ASSASSIN_ROAM = True
_assassin: dict = {"pos": None, "deaths": 0}

# 10. 조건부 양동(성혁 9/30): DIVERSION_COND면 양동을 늘 하지 않고 신호가 있을 때만 시작한다. 신호 S = (건물 가치 × 우선순위) / (1 + 수비) /
#     (2 + 가장 가까운 우리 전투병 거리) × (1 + 어그로/12). 어그로 = 목표에서 DIVERSION_AGGRO_MIN_DIST~MAX_DIST걸음 사이의 적 전투병 수
#     (건드리면 달려올 병력). 시작 조건: ① 전선이 팽팽(우리/적 전투병 비율이 TIGHT_LO~TIGHT_HI)하고 S ≥ DIVERSION_SIGNAL_TIGHT, 또는
#     ② 쉽게 뺏을 수 있고(수비 ≤ DIVERSION_EASY_DEF) 어그로가 충분하며(≥ DIVERSION_AGGRO_MIN) S ≥ DIVERSION_SIGNAL_EASY.
#     시작한 뒤에는 관성: S ≥ DIVERSION_SIGNAL_KEEP인 동안 유지한다.
DIVERSION_COND = False
DIVERSION_TIGHT_LO = 0.85
DIVERSION_TIGHT_HI = 1.2
DIVERSION_SIGNAL_TIGHT = 0.8
DIVERSION_SIGNAL_EASY = 1.0
DIVERSION_SIGNAL_KEEP = 0.5
DIVERSION_EASY_DEF = 1
DIVERSION_AGGRO_MIN = 6
DIVERSION_AGGRO_MIN_DIST = 3
DIVERSION_AGGRO_MAX_DIST = 7

# 11. 조건부 암살(성혁 9/30): ASSASSIN_COND면 지정된 병사 없이, 과제를 받은 전투병이든 누구든 가장 가까운 한 명이 "무방비한 적 깃발병"을
#     죽이러 간다. 무방비 = 그 칸에 적 전투병이 닿지 못하고(위협 0) ASSASSIN_GUARD_R걸음 안에 적 전투병이 없음. 신호 = (KILL_VALUE × n +
#     건물 가치 + ASSASSIN_EXTRA × n) / (1 + 우리 전투병까지 거리) ≥ ASSASSIN_SIGNAL이고 거리 ≤ ASSASSIN_MAX_DIST일 때만. 처치 과제 가치를
#     ASSASSIN_BOOST배로 올려 다른 과제보다 먼저 한 명을 데려가게 한다(관성보다 앞선다).
ASSASSIN_COND = False
ASSASSIN_EXTRA = 2.0
ASSASSIN_SIGNAL = 1.0
ASSASSIN_MAX_DIST = 3
ASSASSIN_BOOST = 3.0

# 12. 최소 명령 인원(성혁 9/30): MIN_ORDER_FROM턴부터 전투병 과제는 MIN_ORDER명 미만으로 받지 않는다(과제 인원을 끌어올린다).
#     양동·암살은 예외. 0 = 끔.
MIN_ORDER = 0
MIN_ORDER_FROM = 20
ORDER_EXEMPT = {"양동", "암살"}

# 13. 역 가치 V3(STATION_V2 위에): 도착지 주변(이 역 자신의 주변 포함 = 전진 거점), 순간이동으로 아끼는 걸음(연계 역까지 거리),
#     수비(이 역 근처의 우리 공학관·학생회관으로 바로 지원)를 함께 본다. STATION_V2도 켜야 한다.
STATION_V3 = False
STATION_LINK_GAIN = 0.5  # (연계 역까지 거리 − STATION_MIN_LINK)를 6으로 나눠 곱한다
STATION_DEFENSE = 0.6  # 이 역 STATION_NEIGHBOR걸음 안의 우리 공학관·학생회관 하나당

# 14. 기동대(성혁 9/30): 우리 진영 깊은 곳(상대 본진까지 걸음 ≥ MOBILE_ENEMY_DIST)의 건물을 MOBILE_WINDOW턴 안에 MOBILE_FLIPS번 이상
#     잃으면(우리 소유 → 아님) 그 건물에 전담 소규모 기동대(MOBILE_SIZE명, 가치 × MOBILE_WEIGHT)를 붙이고, 마지막으로 잃은 뒤
#     MOBILE_CALM턴 조용하면 푼다. 0 = 끔.
MOBILE = False
MOBILE_FLIPS = 3
MOBILE_WINDOW = 40
MOBILE_CALM = 25
MOBILE_SIZE = 3
MOBILE_WEIGHT = 2.0
MOBILE_ENEMY_DIST = 9
_lost: dict = {"owner": {}, "turns": {}}  # 건물 id → 지난 소유자 / 우리가 잃은 턴 목록

_diversion: dict = {"target": None, "since": 0, "owner": None, "banned": {}}  # 양동 목표 id·시작 턴·그때 소유자·접은 건물(id → 풀리는 턴)
_served: set[Pos] = set()  # 지난 턴에 전투병을 받은 과제 칸 (WARRIOR_INERTIA)

_phase = {"name": "EXPAND", "calm": 0}  # 직전 국면과, 그 국면의 조건이 연속으로 풀린 턴 수

_eng_rush = {"held": False}  # 이번 경기에서 상대 캠퍼스 공학관을 한 번이라도 가졌는가 (러시 접기)
_depots_taken: set[int] = set()  # 우리가 소유했던 보급소 id (보너스는 1회뿐). 한 프로세스 = 한 경기
_dist_cache: dict[Pos, dict[Pos, int]] = {}  # 칸 → 그 칸까지의 거리표. 맵은 경기 내내 같으므로 턴을 넘어 재사용
_tele_cache: dict[tuple[Pos, tuple[Pos, ...]], dict[Pos, int]] = {}  # (칸, 우리 역들) → 역 포함 거리표
_dist_cache_rows: list[tuple[str, ...]] = []  # 캐시를 만든 맵의 지형 (맵이 바뀌면 캐시를 비운다)


@dataclass(frozen=True)
class Task:
    """과제: `unit` 병종을 `pos`에 `need`명 이상 보내면 `value`만큼 얻는다.

    점령 과제는 깃발병 한 명이 맡고, 대상 건물과 남은 점령 단계 수(`stages`)를 함께 적는다.
    """

    kind: str  # 점령 · 처치 · 호위 · 지키기
    unit: str  # "F" | "W"
    pos: Pos
    need: int
    value: float
    building: Building | None = None
    stages: int = 0


# ------------------------------------------------------------------ 한 턴 (루트 Sequence)


class Turn:
    """한 턴의 칠판(blackboard). 트리의 각 단계가 앞 단계의 결과를 여기서 읽고, 자기 결과를 적는다."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.phase = _phase
        self.actions: list[Action] = []
        # 국면 가지가 채운다: 병종별 과제 만들기 함수, 전투병 목표 인원의 추가분
        self.makers: dict[str, list[Maker]] = {"F": [], "W": []}
        self.extra_warriors = 0
        self.diversion_ok = False  # 이번 국면이 양동을 켰는가 (점령 과제가 읽는다)
        self.diversion: Building | None = None
        self.assassin_needed = False  # 암살자가 없어 이번 턴 새로 정해야 한다
        self.assassin_move: tuple[Pos, Pos] | None = None

    def tasks(self, unit: str) -> list[Task]:
        """이번 국면이 켠 과제 만들기 함수로 `unit` 병종의 과제 목록을 만든다."""
        return [task for maker in self.makers[unit] for task in maker(self)]

    def dist_to(self, pos: Pos) -> dict[Pos, int]:
        """걸어서 `pos`까지의 거리표 (경기 내내 캐시)."""
        if pos not in _dist_cache:
            _dist_cache[pos] = distance_map([pos], self.world.map.passable)
        return _dist_cache[pos]

    def tele_to(self, pos: Pos) -> dict[Pos, int]:
        """우리 역끼리 순간이동(비용 1)을 포함한 `pos`까지의 거리표. 역이 2개 미만이면 걸어서만."""
        if not self.gates:
            return self.dist_to(pos)
        if (pos, self.gates) not in _tele_cache:
            _tele_cache[(pos, self.gates)] = distance_map([pos], self.world.map.passable, self.gates)
        return _tele_cache[(pos, self.gates)]


Maker = Callable[[Turn], list[Task]]  # 과제 만들기 함수: 칠판을 읽고 과제 목록을 돌려준다


def decide(world: World) -> list[Action]:
    turn = Turn(world)
    TURN_TREE.tick(turn)
    return turn.actions


def read_situation(t: Turn) -> None:
    """상황 읽기: 적 위치·위협 맵·건물 가치·목표 후보·국면 조건."""
    world = t.world
    me, enemy = world.me, world.enemy
    remember(world)
    if world.turn <= 1:
        analyze_map(t)
    t.order = direction_order(world)
    t.key = key = normalizer(world)  # 동점일 때의 순서를 자기 본진 기준으로 맞춘다 → 양 진영이 거울처럼 움직인다
    # 역 순간이동: 우리 역이 2개 이상이면 역끼리 비용 1로 이어진 경로도 최단거리에 넣는다 (전투병 이동에만.
    # 깃발병에 쓰면 효과가 없었다 — docs/benchmarks.md)
    stations = sorted((b.pos for b in world.owned(me, "STATION")), key=key)
    t.gates = tuple(stations) if len(stations) >= 2 else ()
    t.enemy_flags = dict(sorted(world.units_of(enemy, "F"), key=lambda u: key(u[0])))
    t.flag_aim = {pos: intercept_cell(t, pos) for pos in t.enemy_flags}  # 적 깃발병 칸 → 전투병이 갈 칸
    t.enemy_warriors = world.units_of(enemy, "W")
    t.threat = threat_map(t.enemy_warriors + enemy_spawnable(world), world.map.passable)
    t.values = {b.id: building_value(world, b) for b in world.buildings.values()}
    t.eng_rush_on = eng_rush_active(t)
    t.diversion = diversion_target(t)
    t.assassin_needed = assassin_update(world)
    t.others = sorted((b for b in world.buildings.values() if b.owner != me), key=lambda b: key(b.pos))
    # 상대 깃발병이 있는 건물은 경합이라, 전투병이 뽑아 주기 전에는 깃발병 목표가 아니다
    t.free_targets = [b for b in t.others if b.pos not in t.enemy_flags]
    t.pressured = pressured_buildings(world, t.enemy_flags, t.dist_to)
    t.active = phase_conditions(world, t.pressured)


def enter_phase(t: Turn, name: str) -> None:
    """국면 가지의 첫 행동 잎: 지금 국면을 기록한다(다음 턴 Latch가 읽는다)."""
    if t.phase["name"] != name:
        t.phase.update(name=name, calm=0)


def plan_flags(t: Turn) -> None:
    """깃발병 1차: 지금 있는 깃발병을 점령 과제에 배정해, 이번 턴 점령 단계가 진행될 건물을 정한다."""
    t.flags = sorted(t.world.units_of(t.world.me, "F"), key=lambda u: t.key(u[0]))
    t.targets, t.pulled = t.free_targets, set()
    t.f_tasks = t.tasks("F")
    t.capturing_now = capturing(assign_flags(t.flags, t.f_tasks, t.dist_to), t.dist_to)


def reserve_capture_cost(t: Turn) -> None:
    """이번 턴 점령 비용만 남기고 나머지를 생산 예산으로."""
    world, me = t.world, t.world.me
    need = sum(world.stage_cost(task.building) for task in t.capturing_now)
    income = BASE_INCOME + HALL_BONUS * len(world.owned(me, "HALL"))
    t.budget = max(0, world.gold[me] - max(0, need - income))  # 점령은 이번 턴 수입 뒤에 치른다


def plan_warrior_tasks(t: Turn) -> None:
    """전투병 과제 목록(이번 국면이 켠 종류)과, 과제가 없는 전투병의 공통 목표."""
    t.w_tasks = sorted(t.tasks("W"), key=lambda task: t.key(task.pos))
    if MIN_ORDER and t.world.turn >= MIN_ORDER_FROM:  # 소수 전투병에게는 명령을 주지 않는다
        t.w_tasks = [task if task.kind in ORDER_EXEMPT or task.need >= MIN_ORDER else replace(task, need=MIN_ORDER)
                     for task in t.w_tasks]
    # 과제가 없는 전투병은 모두 같은 목표 집합으로 가므로, 목표 쪽에서 BFS를 한 번만 한다.
    # (전투병마다 BFS를 하면 유닛 수에 비례해 느려진다 — 서버에서 186명일 때 응답 214 ms)
    t.goals = set(t.flag_aim.values()) or {b.pos for b in t.free_targets}
    t.goal_dist = distance_map(t.goals, t.world.map.passable)


def produce(t: Turn) -> None:
    """생산: 깃발병(MIN_FLAGS까지) → 전투병(적 + 추가 인원까지) → 깃발병(점령 과제 수만큼, 총원 MAX_FLAGS까지)
    → 남으면 전투병.
    위치는 M4 병원 생산."""
    world, me, key = t.world, t.world.me, t.key
    budget = t.budget
    wc = world.warrior_cost(me)
    fc = UNIT_COST["F"]
    nf = sum(n for _, n in t.flags)
    nw = sum(n for _, n in world.units_of(me, "W"))
    want_w = max(MIN_WARRIORS, sum(n for _, n in t.enemy_warriors) + t.extra_warriors)
    extra_f = 1 if DECOY_EXTRA_FLAG and DECOY_FROM <= world.turn <= DECOY_UNTIL else 0  # 미끼로 빠질 1명을 메운다
    cap = MAX_FLAGS + extra_f
    if EARLY_MAX_FLAGS and world.turn < EARLY_FLAG_TURN:
        cap = min(cap, EARLY_MAX_FLAGS)  # 초반에는 깃발병을 줄이고 그만큼 전투병으로
    want_f = max(0, min(len(t.f_tasks) + SPARE_FLAGS + extra_f, cap) - nf)
    # 깃발병 최소 인원은 전투병보다 먼저 채운다. 전투병을 "적 + 추가 인원"까지 먼저 채우면, 상대가 전투병을
    # 더 뽑는 경기에서는 자원이 전부 전투병으로 가서 깃발병을 다시 만들지 못했다(9/27 리더보드 패배 경기:
    # 깃발병 0명인 22턴 중 21턴을 전투병만 생산, 건물 6 → 15개를 내줌)
    # 건물이 밀리면 최소 인원을 늘린다: 적 전투병이 훨씬 많으면 전투병 목표를 끝내 못 채워, 깃발병이 최소 인원에
    # 묶인 채 건물을 되찾지 못했다(9/28 리더보드 패배 28·29: 20턴 이후 깃발병 2명 이하 81·75턴)
    behind = len(world.owned(world.enemy)) > len(world.owned(me))
    min_f = MIN_FLAGS + (BEHIND_EXTRA_FLAGS if behind else 0)
    make_f = min(want_f, max(0, min_f - nf), budget // fc)
    budget -= make_f * fc
    make_w = min(max(0, want_w - nw), budget // wc)
    budget -= make_w * wc
    if ASSASSIN and t.assassin_needed and make_w == 0 and budget >= wc:  # 암살자를 새로 만든다
        make_w, budget = 1, budget - wc
    more_f = min(budget // fc, want_f - make_f)
    make_f += more_f
    budget -= more_f * fc
    if make_f == want_f:  # 깃발병이 충분하면 남는 자원은 쌓아 두지 않고 전투병으로
        make_w += budget // wc
    t.make_w, t.make_f = make_w, make_f
    # M4: 생산 위치 — 본진 또는 우리 병원 중 목표에 가장 가까운 안전한 곳 (동점이면 본진)
    passable = world.map.passable
    sites = [world.map.bases[me]] + sorted((b.pos for b in world.owned(me, "HOSPITAL")), key=key)
    # 전투병은 위협받는 병원에서도 만든다: 전투병끼리는 1:1로 상쇄되어 손해가 없고, 그 자리에서 병원을 지킨다.
    # (위협받는 병원을 빼던 때는 적이 다가오는 턴마다 먼 본진에서 생산했다 — 9/28 리더보드 패배 3경기에서 22~27턴)
    t.w_site = spawn_site(sites, distance_map(t.goals | {task.pos for task in t.w_tasks}, passable), {})
    t.f_site = spawn_site(sites, distance_map({task.pos for task in t.f_tasks}, passable), t.threat)
    if make_w:
        t.actions.append(Spawn("W", make_w, None if t.w_site == sites[0] else t.w_site))
    if make_f:
        t.actions.append(Spawn("F", make_f, None if t.f_site == sites[0] else t.f_site))


def plan_warriors(t: Turn) -> None:
    """전투병 배정: 과제마다 가장 가까운 전투병을 붙인다(이번 턴 새로 만든 전투병 포함)."""
    warriors = with_spawned(t.world.units_of(t.world.me, "W"), t.w_site, t.make_w, t.key)
    t.assassin_move = None
    if ASSASSIN:
        warriors = assassin_plan(t, warriors)
    t.w_plan, t.w_idle, t.arrival = assign_warriors(
        warriors, t.w_tasks, t.dist_to, frozenset(_served) if WARRIOR_INERTIA else frozenset())
    _served.clear()
    _served.update(dst for _, dst in t.w_plan)


def move_warriors(t: Turn) -> None:
    """전투병 이동(역 순간이동 포함). 이동 뒤 칸별 인원(w_after)은 깃발병 안전 판단에 쓴다."""
    world, key, order, gates = t.world, t.key, t.order, t.gates
    moving: Counter[tuple[Pos, Pos | None]] = Counter()  # (출발 칸, 목표 칸 또는 None=공통 목표) → 인원
    moving.update(t.w_plan)
    moving.update((pos, None) for pos in t.w_idle)
    goal_tele = distance_map(t.goals, world.map.passable, gates) if gates else t.goal_dist
    w_after: Counter[Pos] = Counter()
    w_steps: Counter[tuple[Pos, Pos]] = Counter()
    w_jumps: Counter[tuple[Pos, Pos]] = Counter()  # 순간이동을 원하는 (출발 역, 도착 역) → 인원
    groups = []
    for i, ((pos, goal), n) in enumerate(moving.items()):
        walk = t.goal_dist if goal is None else t.dist_to(goal)
        tele = goal_tele if goal is None else t.tele_to(goal)
        groups.append((pos not in gates, tele.get(pos, 0), key(pos), i, pos, n, walk, tele))
    queued = 0  # 이번 턴 순간이동 경로에 태운 인원 = 대기열. 역에 이미 선 인원부터 센다
    for *_, pos, n, walk, tele in sorted(groups):
        # 순간이동은 턴당 TELE_MAX_UNITS명뿐이다. 대기열에서 기다릴 턴까지 더해도 걷기보다 빠른 인원만
        # 역으로 보낸다. (전원을 역으로 보내면 못 탄 인원이 걸어서 물러났다가 다음 턴 돌아오기를 반복했다 —
        # 9/27 리더보드 리플레이에서 역 옆 두 칸을 오간 전투병 최대 66명)
        via = 0
        if gates and pos in tele:
            gain = walk.get(pos, 10**6) - tele[pos]
            via = min(n, max(0, TELE_MAX_UNITS * gain - queued))
        queued += via
        step = step_along(pos, tele, order, gates) if via else None
        if step and manhattan(pos, step) > 1:
            w_jumps[(pos, step)] += via  # 도착 인원(w_after)은 순간이동 한 쌍을 고른 뒤에 센다
        else:
            if step:
                w_steps[(pos, step)] += via
            w_after[step or pos] += via
        step = step_along(pos, walk, order)
        if step and n - via:
            w_steps[(pos, step)] += n - via
        w_after[step or pos] += n - via
    jump = pick_jump(w_jumps, key)
    for (src, dst), n in w_jumps.items():
        sent = min(n, TELE_MAX_UNITS) if (src, dst) == jump else 0
        if sent:
            t.actions.append(Tele(src, "W", sent, dst))
            w_after[dst] += sent
        w_after[src] += n - sent  # 못 탄 인원은 역에서 다음 차례를 기다린다
    t.actions += [Move(src, "W", n, dst) for (src, dst), n in w_steps.items()]
    if t.assassin_move:
        src, dst = t.assassin_move
        if dst != src:
            t.actions.append(Move(src, "W", 1, dst))
        w_after[dst] += 1
    t.w_after = w_after


def replan_flags(t: Turn) -> None:
    """깃발병 2차: 전투병이 깃발을 뽑아 줄 건물을 점령 과제에 넣고, 새로 만든 깃발병까지 다시 배정한다."""
    t.pulled = {b.id for b in t.others if b.pos in t.enemy_flags and b.pos in t.arrival}
    t.targets = t.free_targets + [b for b in t.others if b.id in t.pulled]
    flags = with_spawned(t.flags, t.f_site, t.make_f, t.key)
    t.plan = assign_flags(flags, t.tasks("F"), t.dist_to)


def move_flags(t: Turn) -> None:
    """깃발병 이동: 한 명씩 FLAG_TREE로 다음 칸을 정한다."""
    threat, w_after = t.threat, t.w_after

    def safe(pos: Pos) -> bool:
        # 전투병 수가 같으면 서로 상쇄되고 남은 전투병이 없어 깃발병은 살아남는다
        return threat.get(pos, 0) <= w_after[pos]

    f_steps: Counter[tuple[Pos, Pos]] = Counter()
    plan = list(t.plan)
    decoy = pick_decoy(t, plan)
    if decoy is not None:
        pos = plan.pop(decoy)[0]
        step = decoy_step(t, pos)
        if step != pos:
            f_steps[(pos, step)] += 1
    for pos, task in plan:
        # 전투병이 이번 턴에 못 오면 한 칸 앞에서 대기
        hold = task.building.id in t.pulled and t.arrival[task.pos] > 1
        step = flag_step(pos, task.pos, t.dist_to(task.pos), t.order, safe, hold)
        if step:
            f_steps[(pos, step)] += 1
    if IDLE_RETREAT:  # 과제를 못 받은 깃발병이 우리 건물 위·근처에 있으면 비켜 대기한다
        planned = {pos for pos, _ in t.plan}
        for pos, _ in t.flags:
            if pos not in planned:
                step = idle_step(t, pos, safe)
                if step:
                    f_steps[(pos, step)] += 1
    t.actions += [Move(src, "F", n, dst) for (src, dst), n in f_steps.items()]


def idle_step(t: Turn, pos: Pos, safe: Callable[[Pos], bool]) -> Pos | None:
    """과제 없는 깃발병의 다음 칸. 우리 건물에서 IDLE_KEEP(요충지 1, 나머지 2)칸까지 물러난다. 중립·상대 건물 위에서는
    움직이지 않는다 — 거기 있는 깃발병은 경합을 만들어 상대 점령을 막는다."""
    near = [b for b in t.world.owned(t.world.me) if manhattan(b.pos, pos) <= IDLE_KEEP_DEFAULT]
    want = [b for b in near if manhattan(b.pos, pos) < IDLE_KEEP.get(b.kind, IDLE_KEEP_DEFAULT)]
    if not want:
        return None
    x, y = pos
    best = None
    for dx, dy in t.order:
        nxt = (x + dx, y + dy)
        if not t.world.map.passable(nxt) or not safe(nxt):
            continue
        gain = min(manhattan(b.pos, nxt) - manhattan(b.pos, pos) for b in want)
        if gain > 0 and (best is None or nxt < best):
            best = nxt
    return best


def pick_decoy(t: Turn, plan: list[tuple[Pos, Task]]) -> int | None:
    """미끼로 쓸 깃발병의 `plan` 번호. 조건(DECOY_*)이 안 맞으면 None. 점령 중(목표까지 1걸음 이내)인 깃발병은 빼고,
    적 전투병에 가장 가까운 한 명(동점이면 정규화 좌표 순). 적 전투병까지 거리표는 t.enemy_w_dist에 남긴다."""
    world = t.world
    if not (DECOY_FROM <= world.turn <= DECOY_UNTIL) or not t.enemy_warriors or len(plan) < DECOY_MIN_FLAGS:
        return None
    t.enemy_w_dist = distance_map({p for p, _ in t.enemy_warriors}, world.map.passable)
    cands = [(t.enemy_w_dist.get(pos, 10**6), t.key(pos), i) for i, (pos, task) in enumerate(plan)
             if t.dist_to(task.pos).get(pos, 99) > 1]
    return min(cands)[2] if cands else None


def decoy_step(t: Turn, pos: Pos) -> Pos:
    """미끼 깃발병의 다음 칸(제자리 포함). 위협 0인 칸 중 적 전투병에 가장 가까운 칸, 없으면 가장 먼 칸."""
    passable, dist = t.world.map.passable, t.enemy_w_dist
    cells = [pos] + [(pos[0] + dx, pos[1] + dy) for dx, dy in t.order if passable((pos[0] + dx, pos[1] + dy))]
    safe = [c for c in cells if not t.threat.get(c, 0)]
    if safe:
        return min(safe, key=lambda c: (dist.get(c, 10**6), t.key(c)))
    return max(cells, key=lambda c: (dist.get(c, -1), [-v for v in t.key(c)]))


def set_priority(t: Turn) -> None:
    """이번 턴 점령할 건물이 둘 이상이면 가치 순으로 PRIORITY."""
    now = sorted(capturing(t.plan, t.dist_to), key=lambda task: -t.values[task.building.id])
    if len(now) >= 2:
        t.actions.append(Priority(tuple(task.pos for task in now)))


def analyze_map(t: Turn) -> None:
    """첫 턴 맵 분석(제한 3초, 이후 턴 300 ms). 지형·건물 배치는 경기 내내 같으므로 모든 건물과 양 본진까지의 걸음
    거리표를 미리 만들어 캐시에 넣는다. 판단은 바뀌지 않고, 처음 가는 건물이 생기는 턴의 계산만 앞당긴다."""
    world = t.world
    for pos in sorted({b.pos for b in world.buildings.values()} | set(world.map.bases.values())):
        t.dist_to(pos)


def remember(world: World) -> None:
    """턴을 넘어 기억해야 하는 것: 보급소 보너스를 이미 받았는지, 직전 국면, 거리표 캐시."""
    if world.turn <= 1:
        _depots_taken.clear()
        _phase.update(name="EXPAND", calm=0)
        _eng_rush["held"] = False
        _diversion.update(target=None, since=0, owner=None, banned={})
        _assassin.update(pos=None, deaths=0)
        _lost.update(owner={}, turns={})
        _served.clear()
    _depots_taken.update(b.id for b in world.owned(world.me, "DEPOT"))
    for b in world.buildings.values():  # 우리가 잃은 건물 (기동대)
        before = _lost["owner"].get(b.id)
        if before == world.me and b.owner != world.me:
            _lost["turns"].setdefault(b.id, []).append(world.turn)
        _lost["owner"][b.id] = b.owner
    if _dist_cache_rows != [world.map.rows]:
        _dist_cache.clear()
        _tele_cache.clear()
        _dist_cache_rows[:] = [world.map.rows]


def note() -> str:
    """턴 로그에 남길 한 단어: 이번 턴 국면."""
    return _phase["name"]


# ------------------------------------------------------------------ 국면 (BT 위층)


def pressured_buildings(
    world: World, enemy_flags: dict[Pos, int], dist_to: Callable[[Pos], dict[Pos, int]],
) -> list[tuple[Building, int]]:
    """적 깃발병이 GUARD_RADIUS 안에 들어온 우리 건물과, 가장 가까운 적 깃발병까지의 거리."""
    found = []
    for b in world.owned(world.me):
        dist = dist_to(b.pos)
        near = min((dist[p] for p in enemy_flags if p in dist), default=None)
        if near is not None and near <= GUARD_RADIUS:
            found.append((b, near))
    return found


def phase_conditions(world: World, pressured: list[tuple[Building, int]]) -> dict[str, bool]:
    """국면마다 조건이 성립하는가. 확장은 늘 성립한다(기본 국면)."""
    me, enemy = world.me, world.enemy
    pressure = sum(estimated_score(world, b) for b, _ in pressured)
    mine = sum(estimated_score(world, b) for b in world.owned(me))
    theirs = sum(estimated_score(world, b) for b in world.owned(enemy))
    my_w = sum(n for _, n in world.units_of(me, "W"))
    enemy_w = sum(n for _, n in world.units_of(enemy, "W"))
    return {
        "THREAT": pressure >= THREAT_PRESSURE,
        "HOLD": world.turn >= LATE_TURN and mine > theirs,
        "ATTACK": my_w >= enemy_w + ATTACK_MARGIN and bool(world.owned(enemy)),
        "EXPAND": True,
    }


def select_phase(active: dict[str, bool], current: str, calm: int) -> tuple[str, int]:
    """PHASE_TREE만 따로 실행한다(테스트용). 돌려주는 값: (이번 턴 국면, 갱신된 calm).

    조건이 성립하는 국면 중 우선순위가 가장 높은 것을 고른다. 그것이 지금 국면보다 급하거나 같으면
    바로 따르고, 덜 급하면 지금 국면의 조건이 HOLD_TURNS턴 연속 풀렸을 때만 내려간다(Latch).
    """
    ctx = SimpleNamespace(active=active, phase={"name": current, "calm": calm}, makers={"F": [], "W": []})
    PHASE_TREE.tick(ctx)
    return ctx.phase["name"], ctx.phase["calm"]


# ------------------------------------------------------------------ 과제 만들기 (국면 가지가 켠다)


def capture_tasks(t: Turn, steal: float, danger: float) -> list[Task]:
    """점령: 목표 건물마다 깃발병 한 명. 상대 소유 건물은 가치 × steal(빼앗으면 상대 점수도 준다), 적 전투병이
    닿는 건물은 × danger(작을수록 조심한다. 전투병이 깃발을 뽑아 줄 건물은 빼고).
    남은 점령 단계: 뽑아 줄 건물·중립은 1, 상대 건물은 중립화 → 점령 2 (목표에 우리 건물은 없다).
    """
    tasks = []
    arrival = getattr(t, "arrival", {})  # 전투병이 가는 칸 (깃발병 2차에서만 있다)
    for b in t.targets:
        if PLAZA_SKIP_UNTIL and b.kind == "PLAZA" and t.world.turn < PLAZA_SKIP_UNTIL:
            continue  # 기능이 없는데 단계 비용만 2배다. 초반 자원은 전투병으로 돌린다
        pulled = b.id in t.pulled
        covered = pulled or b.pos in arrival
        stages = 1 if pulled or b.owner is None else 2
        cost_factor = COST_BASE / (COST_BASE + t.world.stage_cost(b) * stages) if COST_BASE else 1.0
        value = (t.values[b.id] * cost_factor
                 * (DIVERSION_CAPTURE if t.diversion_ok and t.diversion is b else 1.0)
                 * (danger if t.threat.get(b.pos, 0) and not covered else 1.0)
                 * (steal if b.owner is not None else 1.0)
                 * (RAID_STEAL if b.owner == t.world.enemy and b.kind in RAID_KINDS else 1.0)
                 * (ENG_RUSH_CAPTURE if b.kind == "ENG" and t.eng_rush_on else 1.0))
        tasks.append(Task("점령", "F", b.pos, 1, value, b, stages))
    return tasks


def kill_tasks(t: Turn) -> list[Task]:
    """처치: 적 깃발병. 이기려면 그 칸에 모일 수 있는 적 전투병보다 한 명 많아야 한다.
    건물 위면 그 건물 가치를 더한다: 우리 건물이면 방어, 중립이면 점령 저지, 상대 건물이면 깃발 뽑기.
    이동 중인 깃발병은 요격 칸(t.flag_aim, INTERCEPT)으로 간다."""
    tasks = []
    for pos, n in t.enemy_flags.items():
        b = t.world.building_at(pos)
        bonus = t.values[b.id] if b else 0.0
        cell = t.flag_aim[pos]
        need = t.threat.get(cell, 0) + 1
        value = KILL_VALUE * n + bonus
        if ASSASSIN_COND and need == 1 and assassin_signal(t, cell, n, bonus):
            tasks.append(Task("암살", "W", cell, 1, value * ASSASSIN_BOOST))
            continue
        tasks.append(Task("처치", "W", cell, need, value))
    return tasks


def assassin_signal(t: Turn, cell: Pos, n: int, bonus: float) -> bool:
    """무방비한 적 깃발병(`cell`)을 우리 전투병 한 명이 혼자 죽일 만한가 (ASSASSIN_COND 설명)."""
    if any(manhattan(cell, p) <= ASSASSIN_GUARD_R for p, _ in t.enemy_warriors):
        return False
    dist = t.dist_to(cell)
    near = min((dist.get(p, 99) for p, _ in t.world.units_of(t.world.me, "W")), default=99)
    if near > ASSASSIN_MAX_DIST:
        return False
    return (KILL_VALUE * n + bonus + ASSASSIN_EXTRA * n) / (1 + near) >= ASSASSIN_SIGNAL


def intercept_cell(t: Turn, pos: Pos) -> Pos:
    """적 깃발병(`pos`)을 잡으러 갈 칸. 건물 위(점령 중)이거나 INTERCEPT가 꺼져 있으면 지금 칸. 아니면 가장 가까운 상대
    것이 아닌 건물(동점이면 정규화 좌표 순)을 목적지로 보고, "goal"이면 그 건물, "step"이면 그쪽 다음 칸."""
    world = t.world
    if not INTERCEPT or world.building_at(pos):
        return pos
    aims = [(t.dist_to(b.pos).get(pos), t.key(b.pos), b.pos) for b in world.buildings.values() if b.owner != world.enemy]
    aims = [a for a in aims if a[0] is not None]
    if not aims:
        return pos
    _, _, goal = min(aims)
    if INTERCEPT == "goal":
        return goal
    return step_along(pos, t.dist_to(goal), t.order) or pos

def escort_tasks(t: Turn) -> list[Task]:
    """호위: 이번 턴 점령 중인 우리 깃발병. 같은 수만 있어도 상쇄되어 깃발병이 산다.
    ESCORT_VALUE > 0이면 나머지 우리 깃발병(이동 중·대기 중)에도 전투병 1명씩."""
    tasks = []
    for c in t.capturing_now:
        b = c.building
        if t.threat.get(b.pos, 0) and b.pos not in t.enemy_flags:
            tasks.append(Task("호위", "W", b.pos, t.threat[b.pos], t.values[b.id]))
    if ESCORT_VALUE > 0:  # 이동 중 깃발병: 위 호위 과제가 없는 칸마다 전투병 1명
        covered = {task.pos for task in tasks}
        tasks += [Task("호위", "W", pos, 1, ESCORT_VALUE) for pos, _ in t.flags if pos not in covered]
    return tasks


def guard_tasks(t: Turn, weight: float) -> list[Task]:
    """지키기: 적 깃발병이 다가오는 우리 건물 위에 전투병을 세운다(가치 × weight). 올라오는 적 깃발병을
    그 칸에서 잡는다."""
    return [Task("지키기", "W", b.pos, defend_need(t, b), t.values[b.id] * weight) for b, _ in t.pressured]


def defend_need(t: Turn, b: Building) -> int:
    """우리 건물 `b`를 지키는 데 필요한 전투병: 다음 턴 위협 + 1. 경제 건물은 ECON_DEFEND_REACH걸음 안의 적 전투병이
    더 많으면 그것 + 1."""
    near = 0
    if b.kind in ECON_KINDS and ECON_DEFEND_REACH > 1:
        dist = t.dist_to(b.pos)
        near = sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= ECON_DEFEND_REACH)
    return max(t.threat.get(b.pos, 0), near) + 1


def evict_tasks(t: Turn) -> list[Task]:
    """몰아내기: 적 전투병이 EVICT_RADIUS 안에 온 우리 핵심 건물(EVICT_KINDS) 위에 전투병을 세운다. 건물 위의 적
    전투병은 이겨서 몰아내고, 옆의 적은 올라오지 못하게 한다. 지키기 과제가 이미 있는 건물은 뺀다."""
    guarded = {b.id for b, _ in t.pressured}
    tasks = []
    for b in t.world.owned(t.world.me):
        if b.kind not in EVICT_KINDS or b.id in guarded:
            continue
        econ = b.kind in ECON_KINDS
        radius = ECON_EVICT_RADIUS if econ else EVICT_RADIUS
        weight = EVICT_WEIGHT * (ECON_WEIGHT if econ else 1.0)
        dist = t.dist_to(b.pos)
        if any(dist.get(p, 99) <= radius for p, _ in t.enemy_warriors):
            tasks.append(Task("몰아내기", "W", b.pos, defend_need(t, b), t.values[b.id] * weight))
    return tasks


def frontline_tasks(t: Turn, weight: float) -> list[Task]:
    """전선: 우리 전투병이 적보다 FRONT_SURPLUS명 이상 많으면, 점령을 끝낸 우리 건물 중 노출 순위(front_rank)가
    앞선 FRONT_COUNT곳에 전투병 FRONT_NEED명을 미리 세운다(가치 × weight). 적 깃발병이 다가온 뒤 움직이는 지키기와
    달리 상대의 움직임을 기다리지 않는다. 지키기 과제가 있는 건물과 적 전투병이 EVICT_RADIUS 안에 온 건물은 뺀다
    (한 명으로는 못 지킨다 — 지키기·몰아내기·처치가 맡는다)."""
    world = t.world
    if sum(n for _, n in world.units_of(world.me, "W")) < sum(n for _, n in t.enemy_warriors) + FRONT_SURPLUS:
        return []
    guarded = {b.id for b, _ in t.pressured}
    ranked = []
    for b in world.owned(world.me):
        if b.id in guarded:
            continue
        dist = t.dist_to(b.pos)
        if any(dist.get(p, 99) <= EVICT_RADIUS for p, _ in t.enemy_warriors):
            continue
        ranked.append((front_rank(world, b, dist, t.others), t.key(b.pos), b))
    ranked.sort(key=lambda r: r[:2])
    return [Task("전선", "W", b.pos, FRONT_NEED, t.values[b.id] * weight) for *_, b in ranked[:FRONT_COUNT]]


def front_rank(world: World, b: Building, dist: dict[Pos, int], others: list[Building]) -> float:
    """우리 건물 `b`의 노출 순위(작을수록 전선). `dist`는 `b`에서 각 칸까지의 거리, `others`는 우리 것이 아닌 건물.
    = 가장 가까운 적·중립 건물까지 거리 + FRONT_MARGIN_WEIGHT × (적 본진 거리 − 우리 본진 거리).
    앞 항은 지금 맞닿은 경계, 뒤 항은 진영(상대 쪽으로 나가 있을수록 작다)."""
    far = world.map.width + world.map.height
    front = min((dist[o.pos] for o in others if o.pos in dist), default=far)
    bases = world.map.bases
    margin = dist.get(bases[world.enemy], far) - dist.get(bases[world.me], far)
    return front + FRONT_MARGIN_WEIGHT * margin


def raid_tasks(t: Turn, weight: float) -> list[Task]:
    """급습: 상대 공학관·학생회관(RAID_KINDS) 위에 전투병을 "그 칸 위협 + 1"명 보낸다(가치 × weight). 전투병이 서면
    깃발병이 위험 할인 없이 뒤따라 중립화 → 점령한다. 우리 전투병이 적 + RAID_SURPLUS보다 적으면 하지 않는다."""
    world = t.world
    if sum(n for _, n in world.units_of(world.me, "W")) < sum(n for _, n in t.enemy_warriors) + RAID_SURPLUS:
        return []
    return [Task("급습", "W", b.pos, t.threat.get(b.pos, 0) + 1, t.values[b.id] * weight)
            for b in sorted(world.owned(world.enemy), key=lambda b: t.key(b.pos)) if b.kind in RAID_KINDS]


def squad_tasks(t: Turn) -> list[Task]:
    """별동대: 위험한 목표(상대 소유이거나 적 전투병이 닿는 건물)로 가는 깃발병을 과제 가치 순(동점이면 정규화 좌표 순)으로,
    목표 건물이 겹치지 않게 1명(SECOND_SQUAD_TURN부터 2명) 골라, 그 깃발병이 이번 턴 들어갈 칸(목표 쪽 한 칸, 목표 위면
    목표)에 전투병 SQUAD_SIZE명을 보낸다(점령 과제 가치 × SQUAD_WEIGHT). 전투병이 그 칸을 먼저 차지하므로 깃발병의 안전
    판단(적 위협 ≤ 우리 전투병)이 통과되어 가는 길에서도 함께 움직인다. 깃발병 배정은 깃발병 1차와 같은 입력으로 다시 구한다."""
    world = t.world
    count = 2 if world.turn >= SECOND_SQUAD_TURN else 1
    cands = []
    for pos, task in assign_flags(t.flags, t.f_tasks, t.dist_to):
        b = task.building
        if b.owner == world.enemy or t.threat.get(b.pos, 0):
            cands.append((-task.value, t.key(pos), pos, task))
    cands.sort(key=lambda c: c[:2])
    tasks, taken = [], set()
    for *_, pos, task in cands:
        if len(tasks) == count:
            break
        if task.building.id in taken:
            continue
        taken.add(task.building.id)
        cell = step_along(pos, t.dist_to(task.pos), t.order) or pos
        tasks.append(Task("별동대", "W", cell, squad_size(t, cell), task.value * SQUAD_WEIGHT))
    return tasks


def assassin_update(world: World) -> bool:
    """암살자가 살아 있는지 본다(기억한 칸에 우리 전투병이 있는가). 없으면 죽은 것으로 치고 새로 정해야 한다(True)."""
    if not ASSASSIN:
        return False
    pos = _assassin["pos"]
    if pos is not None and not any(p == pos and n > 0 for p, n in world.units_of(world.me, "W")):
        _assassin.update(pos=None, deaths=_assassin["deaths"] + 1)
    return _assassin["pos"] is None


def assassin_plan(t: Turn, warriors: list[tuple[Pos, int]]) -> list[tuple[Pos, int]]:
    """암살자 1명을 전투병 풀에서 빼고 이번 턴 움직임(t.assassin_move)을 정한다. 새로 정해야 하면 이번 턴 만든 전투병 중 한 명."""
    cells = Counter(dict(warriors))
    if _assassin["pos"] is None and t.assassin_needed and t.make_w and cells.get(t.w_site, 0) > 0:
        _assassin["pos"] = t.w_site
    pos = _assassin["pos"]
    if pos is None or cells.get(pos, 0) < 1:
        return warriors
    cells[pos] -= 1
    dst = assassin_step(t, pos)
    _assassin["pos"] = dst
    t.assassin_move = (pos, dst)
    return sorted(((p, n) for p, n in cells.items() if n > 0), key=lambda item: t.key(item[0]))


def assassin_step(t: Turn, pos: Pos) -> Pos:
    """암살자의 다음 칸(제자리 포함). 표적: 무방비한 적 깃발병 → 없으면(ASSASSIN_ROAM) 가장 가까운 적 깃발병. 안전한 칸(적 전투병이
    다음 턴 닿지 못하는 곳, 위협 0)만 밟고, 그중 표적에 가장 가까운 칸으로 간다."""
    world = t.world
    free, near = [], []
    for fp, n in t.enemy_flags.items():
        d = t.dist_to(fp).get(pos)
        if d is None:
            continue
        b = world.building_at(fp)
        gain = ((t.values[b.id] if b else 0.0) + 1.0) * n / (1 + d)
        near.append((d, t.key(fp), fp))
        if not any(manhattan(fp, p) <= ASSASSIN_GUARD_R for p, _ in t.enemy_warriors):
            free.append((-gain, t.key(fp), fp))
    if free:
        goal = min(free)[2]
    elif ASSASSIN_ROAM and near:
        goal = min(near)[2]
    else:
        return pos
    dist = t.dist_to(goal)
    x, y = pos
    cells = [pos] + [(x + dx, y + dy) for dx, dy in t.order if world.map.passable((x + dx, y + dy))]
    safe = [c for c in cells if c in dist and not t.threat.get(c, 0)]
    if not safe:
        return pos
    return min(safe, key=lambda c: (dist[c], c != pos, t.key(c)))


def squad_size(t: Turn, cell: Pos) -> int:
    """별동대 인원. SQUAD_FLEX면 그 칸을 노리는 적(다음 턴 위협, SQUAD_REACH걸음 안의 적 전투병 중 큰 쪽) + 1을
    SQUAD_MIN~SQUAD_MAX로 자른다. 아니면 SQUAD_SIZE 고정."""
    if not SQUAD_FLEX:
        return SQUAD_SIZE
    reach = t.dist_to(cell)
    near = sum(n for p, n in t.enemy_warriors if reach.get(p, 99) <= SQUAD_REACH)
    return max(SQUAD_MIN, min(SQUAD_MAX, max(t.threat.get(cell, 0), near) + 1))


def enemy_defenders(t: Turn, b: Building) -> int:
    """건물 `b` 주변 DIVERSION_REACH걸음 안의 적 전투병 수."""
    dist = t.dist_to(b.pos)
    return sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= DIVERSION_REACH)


def diversion_signal(t: Turn, b: Building, defenders: int, nearest: int) -> float:
    """양동 신호 S (DIVERSION_COND 설명). 가치가 크고 수비가 약하고 가까울수록, 건드리면 달려올 적이 많을수록 크다."""
    dist = t.dist_to(b.pos)
    aggro = sum(n for p, n in t.enemy_warriors if DIVERSION_AGGRO_MIN_DIST <= dist.get(p, 99) <= DIVERSION_AGGRO_MAX_DIST)
    prio = DIVERSION_PRIORITY if b.kind in DIVERSION_PRIORITY_KINDS else 1.0
    return t.values[b.id] * prio / (1 + defenders) / (2 + nearest) * (1 + min(aggro, 12) / 12)


def diversion_start(t: Turn, b: Building, defenders: int, nearest: int, ratio: float) -> bool:
    """이 건물로 양동을 새로 시작해도 되는가. DIVERSION_COND가 꺼져 있으면 늘 True(V2)."""
    if not DIVERSION_COND:
        return True
    signal = diversion_signal(t, b, defenders, nearest)
    dist = t.dist_to(b.pos)
    aggro = sum(n for p, n in t.enemy_warriors if DIVERSION_AGGRO_MIN_DIST <= dist.get(p, 99) <= DIVERSION_AGGRO_MAX_DIST)
    tight = DIVERSION_TIGHT_LO <= ratio <= DIVERSION_TIGHT_HI
    easy = defenders <= DIVERSION_EASY_DEF and aggro >= DIVERSION_AGGRO_MIN
    return (tight and signal >= DIVERSION_SIGNAL_TIGHT) or (easy and signal >= DIVERSION_SIGNAL_EASY)


def diversion_target(t: Turn) -> Building | None:
    """양동 목표. 후보 = 우리 것이 아닌 건물(DIVERSION_ANY, 아니면 우선순위 종류만). 조건: 수비(주변 적 전투병)가 DIVERSION_MAX_DEF
    이하, 우리 전투병이 걸어서 DIVERSION_FRONT_REACH걸음 안에 DIVERSION_MIN_SUPPORT명 이상. 그중 (가치 × 우선순위) / (1 + 수비) /
    (2 + 가장 가까운 우리 전투병까지 거리)가 큰 곳. 이미 고른 목표는 조건이 유지되는 동안 잡고, DIVERSION_PATIENCE턴 동안 소유자가
    안 바뀌면 DIVERSION_COOLDOWN턴 접는다. 러시가 이미 노리는 공학관은 뺀다. 우리가 밀리면(전투병 비율) 하지 않는다."""
    world = t.world
    st = _diversion
    if not DIVERSION_FROM or not DIVERSION_FROM <= world.turn <= DIVERSION_UNTIL:
        return None
    mine = world.units_of(world.me, "W")
    if sum(n for _, n in mine) < DIVERSION_MIN_RATIO * sum(n for _, n in t.enemy_warriors):
        st["target"] = None
        return None
    cands = []
    for b in sorted(world.buildings.values(), key=lambda b: t.key(b.pos)):
        if b.owner == world.me or (b.kind == "ENG" and t.eng_rush_on) or st["banned"].get(b.id, 0) > world.turn:
            continue
        if not DIVERSION_ANY and b.kind not in DIVERSION_PRIORITY_KINDS:
            continue
        dist = t.dist_to(b.pos)
        support = sum(n for p, n in mine if dist.get(p, 99) <= DIVERSION_FRONT_REACH)
        if support < DIVERSION_MIN_SUPPORT:
            continue
        nearest = min((dist.get(p, 99) for p, _ in mine), default=99)
        cands.append((enemy_defenders(t, b), nearest, b))
    keep = st["target"]
    ratio = sum(n for _, n in mine) / max(1, sum(n for _, n in t.enemy_warriors))
    if keep is not None:
        for d, near, b in cands:
            if b.id == keep and d <= DIVERSION_MAX_DEF + 1 and (
                    not DIVERSION_COND or diversion_signal(t, b, d, near) >= DIVERSION_SIGNAL_KEEP):
                if b.owner != st["owner"]:
                    st.update(since=world.turn, owner=b.owner)  # 소유자가 바뀌었다 = 진전
                elif world.turn - st["since"] >= DIVERSION_PATIENCE:
                    st["banned"][b.id] = world.turn + DIVERSION_COOLDOWN
                    st["target"] = None
                    break
                return b
        else:
            st["target"] = None
    open_ = [(-diversion_signal(t, b, d, near), t.key(b.pos), b) for d, near, b in cands
             if d <= DIVERSION_MAX_DEF and b.id != st["target"] and diversion_start(t, b, d, near, ratio)]
    if not open_:
        return None
    target = min(open_, key=lambda c: c[:2])[2]
    st.update(target=target.id, since=world.turn, owner=target.owner)
    return target


def diversion_tasks(t: Turn) -> list[Task]:
    """양동 과제: 목표 건물에 전투병 (주변 적 + DIVERSION_EXTRA)명(2~DIVERSION_MAX). 깃발병은 점령 가치 배율로 따라온다."""
    b = t.diversion
    if b is None:
        return []
    need = max(2, min(DIVERSION_MAX, max(t.threat.get(b.pos, 0), enemy_defenders(t, b)) + DIVERSION_EXTRA))
    return [Task("양동", "W", b.pos, need, DIVERSION_VALUE)]


def mobile_tasks(t: Turn) -> list[Task]:
    """기동대: 상대 본진에서 깊숙한(걸음 ≥ MOBILE_ENEMY_DIST) 우리 건물을 MOBILE_WINDOW턴 안에 MOBILE_FLIPS번 이상 잃었고 마지막으로
    잃은 지 MOBILE_CALM턴이 안 됐으면, 그 건물에 전담 전투병 MOBILE_SIZE명."""
    if not MOBILE:
        return []
    world = t.world
    away = world.map.bases[world.enemy]
    tasks = []
    for b in sorted(world.buildings.values(), key=lambda b: t.key(b.pos)):
        turns = _lost["turns"].get(b.id)
        if not turns or t.dist_to(b.pos).get(away, 0) < MOBILE_ENEMY_DIST:
            continue
        recent = [x for x in turns if world.turn - x <= MOBILE_WINDOW]
        if len(recent) >= MOBILE_FLIPS and world.turn - turns[-1] <= MOBILE_CALM:
            tasks.append(Task("기동대", "W", b.pos, MOBILE_SIZE, t.values[b.id] * MOBILE_WEIGHT))
    return tasks


def eng_rush_tasks(t: Turn) -> list[Task]:
    """공학관 러시: ENG_RUSH_UNTIL턴까지 상대 캠퍼스 공학관(상대 본진이 더 가까운 공학관 중 우리 것이 아닌 것)에 전투병
    "위협 + ENG_RUSH_EXTRA"명. 상대 공학관을 빼앗으면 우리 전투병 값 3 → 2, 상대는 2 → 3이 된다."""
    if not t.eng_rush_on:
        return []
    return [Task("공학관 러시", "W", b.pos, t.threat.get(b.pos, 0) + ENG_RUSH_EXTRA, ENG_RUSH_VALUE)
            for b in enemy_campus_eng(t) if b.owner != t.world.me]


def enemy_campus_eng(t: Turn) -> list[Building]:
    """상대 캠퍼스 공학관: 우리 본진보다 상대 본진까지 걸음이 짧은 공학관 (정규화 좌표 순)."""
    world = t.world
    home, away = world.map.bases[world.me], world.map.bases[world.enemy]
    found = []
    for b in sorted(world.buildings.values(), key=lambda b: t.key(b.pos)):
        dist = t.dist_to(b.pos)
        if b.kind == "ENG" and dist.get(away, 99) < dist.get(home, 99):
            found.append(b)
    return found


def eng_rush_active(t: Turn) -> bool:
    """이번 턴 공학관 러시를 하는가: ENG_RUSH_UNTIL턴까지. 단 ENG_RUSH_GIVEUP턴이 지나도 상대 캠퍼스 공학관을 한 번도 가진
    적이 없으면 그만둔다(_eng_rush["held"]에 경기 중 한 번이라도 가졌는지 기억)."""
    world = t.world
    if any(b.owner == world.me for b in enemy_campus_eng(t)):
        _eng_rush["held"] = True
    if world.turn > ENG_RUSH_UNTIL:
        return False
    return not (ENG_RUSH_GIVEUP and world.turn > ENG_RUSH_GIVEUP and not _eng_rush["held"])


def garrison_tasks(t: Turn) -> list[Task]:
    """수비대: GARRISON_UNTIL턴까지 우리 공학관·학생회관 위에 전투병 GARRISON_NEED명. 지키기(적 깃발병 접근)나
    몰아내기(적 전투병 EVICT_RADIUS 안) 과제가 걸린 건물은 그쪽이 더 많은 인원으로 맡으므로 뺀다."""
    world = t.world
    if world.turn > GARRISON_UNTIL:
        return []
    guarded = {b.id for b, _ in t.pressured}
    tasks = []
    for b in sorted(world.owned(world.me), key=lambda b: t.key(b.pos)):
        if b.kind not in GARRISON_KINDS or b.id in guarded:
            continue
        dist = t.dist_to(b.pos)
        if any(dist.get(p, 99) <= EVICT_RADIUS for p, _ in t.enemy_warriors):
            continue
        tasks.append(Task("수비대", "W", b.pos, GARRISON_NEED, t.values[b.id] * GARRISON_WEIGHT))
    return tasks


# ------------------------------------------------------------------ 깃발병


def assign_flags(
    flags: list[tuple[Pos, int]], tasks: list[Task], dist_to: Callable[[Pos], dict[Pos, int]],
) -> list[tuple[Pos, Task]]:
    """깃발병 한 명씩 (칸, 점령 과제) 짝. 효용 = 가치 / (거리 + 남은 점령 단계 + ETA_OFFSET).
    한 과제엔 한 명씩, 효용 합이 가장 큰 짝을 한꺼번에 고른다(헝가리안, algorithms.max_assignment).
    과제가 다 차서 남는 인원은 각자 효용이 가장 높은 과제로 겹쳐 보낸다. 닿을 수 없으면 제자리.

    (예전에는 효용이 가장 큰 짝부터 하나씩 확정하는 탐욕 배정이었다. 서버 리플레이 매 턴 상태에서 선택지가 있는
    배정의 약 30%가 최적과 달랐다 — docs/benchmarks.md)
    """
    dists = {task.pos: dist_to(task.pos) for task in tasks}
    pool = [pos for pos, n in flags for _ in range(n)]

    def utility(pos: Pos, task: Task) -> float | None:
        d = dists[task.pos].get(pos)
        return None if d is None else task.value / (d + task.stages + ETA_OFFSET)

    pairs = max_assignment([[utility(pos, task) for task in tasks] for pos in pool]) if tasks else []
    plan = [(pool[i], tasks[j]) for i, j in pairs]
    matched = {i for i, _ in pairs}
    for i, pos in enumerate(pool):
        if i in matched:
            continue
        reachable = [task for task in tasks if utility(pos, task) is not None]
        if reachable:  # 효용이 같으면 앞의 과제
            plan.append((pos, max(reachable, key=lambda task: utility(pos, task))))
    return plan


class FlagMove:
    """깃발병 한 명의 칠판. FLAG_TREE가 `step`(다음 칸, None = 제자리)을 정한다."""

    def __init__(
        self, pos: Pos, goal: Pos, dist: dict[Pos, int], order: tuple[Pos, ...],
        safe: Callable[[Pos], bool], hold: bool,
    ) -> None:
        self.pos, self.goal, self.dist, self.safe, self.hold = pos, goal, dist, safe, hold
        self.here = dist.get(pos)
        neighbors = [(pos[0] + dx, pos[1] + dy) for dx, dy in order]
        self.neighbors = [n for n in neighbors if n in dist]
        # 목표 쪽으로 한 칸 줄이는 칸. 이미 목표 위(거리 0)면 없다
        self.closer = [n for n in self.neighbors if self.here and dist[n] == self.here - 1]
        self.step: Pos | None = None

    def enterable(self, n: Pos) -> bool:
        """`hold`(전투병이 아직 못 옴)면 목표 칸에는 들어가지 않고 한 칸 앞에서 기다린다."""
        return not (self.hold and n == self.goal)

    def go(self, n: Pos | None) -> bool:
        if n is None:
            return False
        self.step = n
        return True


def flag_step(
    pos: Pos,
    goal: Pos,
    dist: dict[Pos, int],
    order: tuple[Pos, ...],
    safe: Callable[[Pos], bool],
    hold: bool,
) -> Pos | None:
    """깃발병 한 명의 다음 칸 (None = 제자리). 판단은 FLAG_TREE:

    목표 쪽으로 한 칸 줄이는 칸 중 안전한 곳 → 없으면 지금 칸이 안전할 때 대기 → 아니면 안전한 이웃으로
    피한다 → 그것도 없으면 그냥 목표 쪽으로 간다. `hold`면 목표 칸에 들어가지 않고 앞에서 기다린다.
    """
    m = FlagMove(pos, goal, dist, order, safe, hold)
    FLAG_TREE.tick(m)
    return m.step


def capturing(plan: list[tuple[Pos, Task]], dist_to: Callable[[Pos], dict[Pos, int]]) -> list[Task]:
    """이번 턴 이동 뒤 깃발병이 올라가 있을 점령 과제 (= 이번 턴 점령 단계가 진행될 건물)."""
    found: dict[Pos, Task] = {}
    for pos, task in plan:
        if dist_to(task.pos).get(pos, 99) <= 1:
            found[task.pos] = task
    return list(found.values())


# ------------------------------------------------------------------ 전투병


def assign_warriors(
    warriors: list[tuple[Pos, int]],
    tasks: list[Task],
    dist_to: Callable[[Pos], dict[Pos, int]],
    sticky: frozenset[Pos] = frozenset(),
) -> tuple[list[tuple[Pos, Pos]], list[Pos], dict[Pos, int]]:
    """과제마다 가장 가까운 전투병 `need`명을 붙인다. 가치 / (1 + 가장 먼 전투병의 거리)가 큰 과제부터.

    `sticky`(지난 턴에 전투병을 받은 과제 칸)는 거리를 WARRIOR_INERTIA만큼 깎아 계속 맡게 한다. 과제 단위 관성이다.

    돌려주는 값: (전투병 칸, 목표 칸) 목록, 과제를 못 받은 전투병 칸 목록, 과제 칸 → 전원 도착까지 턴 수.

    전투병은 칸 단위 [칸, 인원]으로 다룬다. 한 명씩 펼쳐 정렬하면 전투병 수에 비례해 느려져, 9/28 22:00
    리더보드에서 전투병 540명일 때 서버 응답이 274 ms(제한 300 ms)까지 갔다. 같은 칸은 거리가 같으므로
    칸 순서로 동점을 가르면 한 명씩 고르던 때와 같은 전투병을 같은 순서로 고른다.
    """
    cells = [[pos, n] for pos, n in warriors if n > 0]
    plan: list[tuple[Pos, Pos]] = []
    arrival: dict[Pos, int] = {}
    remaining = list(tasks)
    while remaining and cells:
        best: tuple[float, Task, list[tuple[int, int, int]]] | None = None
        for task in remaining:
            dist = dist_to(task.pos)
            chosen: list[tuple[int, int, int]] = []  # (거리, 칸 순서, 데려갈 인원)
            got = 0
            for d, i in sorted((dist[c[0]], i) for i, c in enumerate(cells) if c[0] in dist):
                take = min(cells[i][1], task.need - got)
                chosen.append((d, i, take))
                got += take
                if got == task.need:
                    break
            if got < task.need:
                continue
            far = chosen[-1][0]
            if task.pos in sticky:  # 지난 턴에 맡던 과제는 WARRIOR_INERTIA걸음 더 가깝다고 친다
                far = max(0, far - WARRIOR_INERTIA)
            score = task.value / (1 + far)
            if best is None or score > best[0]:
                best = (score, task, chosen)
        if best is None:
            break
        _, task, chosen = best
        for _, i, take in sorted(chosen, key=lambda c: -c[1]):
            plan += [(cells[i][0], task.pos)] * take
            cells[i][1] -= take
        cells = [c for c in cells if c[1] > 0]
        arrival[task.pos] = chosen[-1][0]
        remaining.remove(task)
    return plan, [pos for pos, n in cells for _ in range(n)], arrival


def pick_jump(jumps: Counter[tuple[Pos, Pos]], key: Callable[[Pos], Pos]) -> tuple[Pos, Pos] | None:
    """순간이동은 턴당 1회: 인원이 가장 많은 (출발 역, 도착 역) 하나. 동점이면 정규화 좌표 순."""
    if not jumps:
        return None
    return min(jumps, key=lambda pair: (-min(jumps[pair], TELE_MAX_UNITS), key(pair[0]), key(pair[1])))


def spawn_site(sites: list[Pos], goal_dist: dict[Pos, int], threat: dict[Pos, int]) -> Pos:
    """생산할 칸. `sites[0]`은 본진, 나머지는 우리 병원. `threat`에서 적 전투병이 닿는 병원은 빼고(새 깃발병이 바로
    잡힌다. 전투병은 빈 위협 맵을 넘겨 빼지 않는다), 목표까지 가장 가까운 곳. 거리가 같으면 앞의 것(본진)."""
    usable = [s for i, s in enumerate(sites) if i == 0 or not threat.get(s, 0)]
    return min(usable, key=lambda s: goal_dist.get(s, 10**6))


def enemy_spawnable(world: World) -> list[tuple[Pos, int]]:
    """상대가 이번 턴 본진에서 새로 만들 수 있는 전투병 (생산한 유닛은 같은 턴에 바로 움직인다)."""
    enemy = world.enemy
    n = world.gold[enemy] // world.warrior_cost(enemy)
    return [(world.map.bases[enemy], n)] if n else []


def with_spawned(
    units: list[tuple[Pos, int]], base: Pos, count: int, key: Callable[[Pos], Pos],
) -> list[tuple[Pos, int]]:
    """이번 턴 본진에서 새로 만든 유닛을 더한 목록 (정규화 좌표 순서)."""
    merged = Counter(dict(units))
    if count:
        merged[base] += count
    return sorted(merged.items(), key=lambda item: key(item[0]))


# ------------------------------------------------------------------ 건물 가치·비용


def estimated_score(world: World, b: Building) -> float:
    """아는 점수, 모르면 기대값 (진영 건물 SIDE_SCORE_GUESS, 중앙 건물 CENTER_SCORE_GUESS)."""
    score = world.known_score(b)
    if score is None:
        return CENTER_SCORE_GUESS if is_center(world, b) else SIDE_SCORE_GUESS
    return score


def building_value(world: World, b: Building) -> float:
    """건물 하나의 가치(점수 단위) = 추정 점수 + 기능 가치."""
    score = estimated_score(world, b)
    if VALUES_V2 and b.kind == "HALL":
        bonus = max(HALL_FLOOR, HALL_EARLY_VALUE - 0.2 * (world.turn // 5))
    elif VALUES_V2 and b.kind == "ENG":
        bonus = max(ENG_FLOOR, ENG_EARLY_VALUE - 0.2 * (world.turn // 5))
    elif b.kind == "HALL":
        bonus = HALL_VALUE_PER_TURN * max(0, TOTAL_TURNS - world.turn)
    elif b.kind == "DEPOT":
        bonus = 0.0 if b.id in _depots_taken else (DEPOT_VALUE_V2 if VALUES_V2 else DEPOT_VALUE)
    elif STATION_V2 and b.kind == "STATION":
        bonus = station_value(world, b)
    else:
        bonus = FUNCTION_VALUE.get(b.kind, 0.0)
    return score + bonus


def station_value(world: World, b: Building) -> float:
    """역의 기능 가치(STATION_V2). 내 역이 몇 번째인지로 갈린다: 붙어 있는 역끼리는 순간이동이 값어치가 없어 0, 짝을 완성하는
    역은 STATION_BASE + 가장 연계되는 역(먼 역 중 주변 건물 가치가 가장 큰 것) 주변 가치, 세 번째부터 STATION_EXTRA."""
    others = [x for x in world.buildings.values() if x.kind == "STATION" and x.id != b.id]
    linked = [x for x in others if manhattan(b.pos, x.pos) >= STATION_MIN_LINK]
    if not linked:
        return 0.0
    mine = [x for x in linked if x.owner == world.me]
    if not mine:
        return STATION_FIRST
    if STATION_V3:
        dest = max([station_neighbors(world, b)] + [station_neighbors(world, x) for x in linked])  # 전진 거점 = 이 역 자신의 주변 포함
        span = max(manhattan(b.pos, x.pos) for x in linked)
        saved = STATION_LINK_GAIN * max(0, min(6, span - STATION_MIN_LINK)) / 6
        guard = STATION_DEFENSE * sum(1 for o in world.buildings.values()
                                      if o.owner == world.me and o.kind in ("ENG", "HALL") and manhattan(o.pos, b.pos) <= STATION_NEIGHBOR)
        return (STATION_EXTRA if len(mine) > 1 else STATION_BASE + dest) + saved + guard
    if len(mine) > 1:
        return STATION_EXTRA
    return STATION_BASE + max(station_neighbors(world, x) for x in linked)


def station_neighbors(world: World, s: Building) -> float:
    """역 `s` 주변 STATION_NEIGHBOR 안의 건물 가치 합 (병원 제외)."""
    return sum(STATION_NEIGHBOR_VALUE.get(o.kind, 0.0) for o in world.buildings.values()
               if o.id != s.id and manhattan(o.pos, s.pos) <= STATION_NEIGHBOR)


def is_center(world: World, b: Building) -> bool:
    """중앙 건물(서울역·방송국·보급소)인가. 역은 각 본진에서 가장 가까운 역이 캠퍼스 역이다."""
    if b.kind in CENTER_KINDS:
        return True
    if b.kind != "STATION":
        return b.kind not in SIDE_KINDS
    return b.id not in campus_stations(world)


def campus_stations(world: World) -> set[int]:
    """각 본진 쪽으로 가장 치우친 역 = 캠퍼스 역 (신촌역·안암역). 나머지 둘은 중앙의 서울역.

    "본진에서 가장 가까운 역"은 중앙 서울역이 더 가까운 맵이 있어 틀린다. 동점은 맵 중심에서 먼 역,
    그다음 본진 기준 정규화 좌표로 가른다(id로 가르면 두 진영의 판단이 대칭이 아니게 된다).
    """
    stations = [b for b in world.buildings.values() if b.kind == "STATION"]
    bases = list(world.map.bases.values())
    center = (world.map.width // 2, world.map.height // 2)
    campus = set()
    for home, away in (bases, bases[::-1]):
        flip = home > world.map.mirror(home)
        if stations:
            campus.add(min(stations, key=lambda s: (
                manhattan(s.pos, home) - manhattan(s.pos, away),
                -manhattan(s.pos, center),
                world.map.mirror(s.pos) if flip else s.pos,
            )).id)
    return campus


def normalizer(world: World) -> Callable[[Pos], Pos]:
    """정렬 키: 자기 본진 기준으로 정규화한 (y, x). 본진이 오른쪽 절반이면 180° 뒤집는다."""
    w, h = world.map.width, world.map.height
    if world.map.bases[world.me][0] * 2 > w - 1:
        return lambda p: (h - 1 - p[1], w - 1 - p[0])
    return lambda p: (p[1], p[0])


def direction_order(world: World) -> tuple[Pos, ...]:
    """거리가 같을 때의 방향 우선순위. 본진이 오른쪽 절반이면 뒤집어 자기 본진 기준으로 맞춘다."""
    base_x = world.map.bases[world.me][0]
    if base_x * 2 > world.map.width - 1:
        return tuple((-dx, -dy) for dx, dy in DEFAULT_ORDER)
    return DEFAULT_ORDER


# ------------------------------------------------------------------ 트리 조립
#
# 트리 전체를 글로 보려면 tree_text(). 노드 이름이 곧 보고서의 판단 조건 설명이다.


def phase_branch(name: str, condition: str | None, *recipe: Node) -> Node:
    """국면 가지: [조건(국면 유지 포함)] → [국면 기록] → [이번 턴 과제 구성]. 조건이 없으면 늘 성립(기본 국면)."""
    record = Act(f"국면 = {name}", lambda ctx: enter_phase(ctx, name))
    if condition is None:
        return Sequence(name, record, *recipe)
    test = Condition(condition, lambda ctx: ctx.active[name])
    return Sequence(name, Latch(name, test, HOLD_TURNS), record, *recipe)


def enable(name: str, unit: str, maker: Maker) -> Node:
    """과제 구성 잎: 이번 턴 `unit` 병종의 과제 목록에 `maker`가 만드는 과제를 넣는다."""
    return Act(name, lambda t: t.makers[unit].append(maker))


def capture(steal: float, danger: float) -> Node:
    return enable(f"점령 과제 (상대 건물 가치 ×{steal:g}, 적 전투병이 닿는 건물 ×{danger:g})",
                  "F", lambda t: capture_tasks(t, steal, danger))


def kill() -> Node:
    return enable("처치 과제: 적 깃발병 (건물 위면 방어·저지·깃발 뽑기)", "W", kill_tasks)


def escort() -> Node:
    return enable("호위 과제: 점령 중인 우리 깃발병", "W", escort_tasks)


def guard(weight: float) -> Node:
    return enable(f"지키기 과제: 적 깃발병이 {GUARD_RADIUS}칸 안에 온 우리 건물 (가치 ×{weight:g})",
                  "W", lambda t: guard_tasks(t, weight))


def evict() -> Node:
    return enable(f"몰아내기 과제: 적 전투병이 {EVICT_RADIUS}칸 안에 온 우리 핵심 건물 ({'·'.join(sorted(EVICT_KINDS))})",
                  "W", evict_tasks)


def frontline(weight: float) -> Node:
    return enable(f"전선 과제: 우리 전투병 ≥ 적 전투병 + {FRONT_SURPLUS}이면 노출 순위가 앞선 우리 건물 {FRONT_COUNT}곳에 "
                  f"전투병 {FRONT_NEED}명 (가치 ×{weight:g})",
                  "W", lambda t: frontline_tasks(t, weight))


def raid(weight: float) -> Node:
    return enable(f"급습 과제: 상대 {'·'.join(sorted(RAID_KINDS))}에 전투병 (가치 ×{weight:g})",
                  "W", lambda t: raid_tasks(t, weight))


def squad() -> Node:
    return enable(f"별동대 과제: 위험한 목표로 가는 깃발병 1명({SECOND_SQUAD_TURN}턴부터 2명)의 다음 칸에 전투병 {SQUAD_SIZE}명",
                  "W", squad_tasks)


def eng_rush() -> Node:
    return enable(f"공학관 러시: {ENG_RUSH_UNTIL}턴까지 상대 캠퍼스 공학관에 전투병 위협 + {ENG_RUSH_EXTRA}명, "
                  f"깃발병은 공학관 가치 ×{ENG_RUSH_CAPTURE:g}", "W", eng_rush_tasks)


def diversion(in_threat: bool = True) -> Node:
    def turn_on(t: Turn) -> None:
        if in_threat or DIVERSION_IN_THREAT:
            t.diversion_ok = True
            t.makers["W"].append(diversion_tasks)
    return Act(f"양동: {DIVERSION_FROM}~{DIVERSION_UNTIL}턴 상대 캠퍼스 수비가 가장 약한 학생회관·공학관에 전투병", turn_on)


def mobile() -> Node:
    return enable(f"기동대: 깊은 곳 건물을 {MOBILE_FLIPS}번 이상 잃으면 전담 전투병 {MOBILE_SIZE}명", "W", mobile_tasks)


def garrison() -> Node:
    return enable(f"수비대: {GARRISON_UNTIL}턴까지 우리 {'·'.join(sorted(GARRISON_KINDS))} 위에 전투병 {GARRISON_NEED}명 "
                  "(지키기·몰아내기가 걸린 건물 제외)", "W", garrison_tasks)


def warriors(extra: int) -> Node:
    return Act(f"전투병 목표 인원 = 적 전투병 + {extra}", lambda t: setattr(t, "extra_warriors", extra))


PHASE_TREE = Selector(
    "국면 선택 → 이번 턴 과제 구성 (위에서부터 처음 성립하는 가지)",
    phase_branch(
        "THREAT", f"적 깃발병이 {GUARD_RADIUS}칸 안에 온 우리 건물의 추정 점수 합 ≥ {THREAT_PRESSURE:g}",
        capture(steal=1.0, danger=0.5), kill(), escort(), guard(2.0), evict(), frontline(1.0), raid(1.0), squad(), eng_rush(), garrison(), diversion(False), mobile(), warriors(2),
    ),
    phase_branch(
        "HOLD", f"{LATE_TURN}턴 이후이고 추정 점수가 앞섬",
        capture(steal=1.0, danger=0.3), kill(), escort(), guard(1.5), evict(), frontline(1.5), raid(1.0), squad(), eng_rush(), garrison(), diversion(), mobile(), warriors(2),
    ),
    phase_branch(
        "ATTACK", f"우리 전투병 ≥ 적 전투병 + {ATTACK_MARGIN}이고 상대가 건물을 가짐",
        capture(steal=1.5, danger=0.5), kill(), escort(), guard(0.5), evict(), frontline(0.5), raid(2.0), squad(), eng_rush(), garrison(), diversion(), mobile(), warriors(1),
    ),
    phase_branch(
        "EXPAND", None,
        capture(steal=1.0, danger=DANGER_DISCOUNT), kill(), escort(), guard(1.0), evict(), frontline(1.0), raid(1.0), squad(), eng_rush(), garrison(), diversion(), mobile(), warriors(1),
    ),
)

TURN_TREE = Sequence(
    "한 턴",
    Act("상황 읽기 (위협 맵·건물 가치·국면 조건)", read_situation),
    PHASE_TREE,
    Sequence(
        "깃발병 1차: 이번 턴 점령할 건물",
        Act("지금 있는 깃발병을 점령 과제에 배정", plan_flags),
        Act("점령 비용 예약", reserve_capture_cost),
    ),
    Act("전투병 과제 목록", plan_warrior_tasks),
    Act(f"생산 (깃발병 최소 인원 → 전투병 목표 인원 → 점령 과제 수만큼 깃발병(총원 {MAX_FLAGS}명까지) → 남으면 전투병, "
        "병원 위치 — 적 전투병이 닿는 병원은 깃발병만 피함)", produce),
    Sequence(
        "전투병",
        Act("과제 배정 (새로 만든 전투병 포함)", plan_warriors),
        Act("이동 (역 순간이동)", move_warriors),
    ),
    Sequence(
        "깃발병 2차",
        Act("전투병이 깃발을 뽑아 줄 건물을 점령 과제에 넣고 재배정", replan_flags),
        Act("한 명씩 깃발병 트리", move_flags),
    ),
    Act("동시 점령 우선순위", set_priority),
)

FLAG_TREE = Selector(
    "깃발병 한 칸",
    Sequence("목표에 닿을 수 없음", Condition("목표까지 경로 없음", lambda m: m.here is None), Act("제자리", lambda m: None)),
    Act("목표 쪽 안전한 칸으로", lambda m: m.go(next(
        (n for n in m.closer if m.safe(n) and m.enterable(n)), None))),
    Sequence("대기", Condition("지금 칸이 안전", lambda m: m.safe(m.pos)), Act("제자리", lambda m: None)),
    Act("가장 목표에 가까운 안전한 이웃으로 피하기", lambda m: m.go(min(
        (n for n in m.neighbors if m.safe(n)), key=lambda n: m.dist[n], default=None))),
    Act("위험해도 목표 쪽으로", lambda m: m.go(
        m.closer[0] if m.closer and m.enterable(m.closer[0]) else None)),
    Act("제자리", lambda m: None),
)


def tree_text() -> str:
    """판단 트리 전체를 글로 (보고서·문서용): python -c "from agent.strategy import tree_text; print(tree_text())" """
    return "\n".join(TURN_TREE.lines() + [""] + FLAG_TREE.lines())
