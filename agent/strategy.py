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
- 별동대 과제(현진 테마 브랜치에서 옮김): 위험한 목표(상대 소유이거나 적 전투병이 닿는 건물)로 가는 깃발병 1명
  (SECOND_SQUAD_TURN부터 2명)의 다음 칸에 전투병 SQUAD_SIZE명을 먼저 보내, 가는 길에서도 깃발병과 함께 움직인다.

학습한 상황별 가중치 층(agent/learned.py): decide 첫 줄에서 이 파일의 상수 34개(과제 가치·생산 인원·성혁 기능 값)를 매 턴
"기준값 × exp(W · 상황 특징 8개)"로 바꾼다. 아래 상수들은 그 기준값이다(= moonwon/unit-ops daa1888). W는 진화 전략으로
찾았다(docs/benchmarks.md "학습 (진화 전략)"). learned.W를 비우면 daa1888과 똑같이 움직인다.
"""

from __future__ import annotations

import time
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
from agent import learned
from agent.forecast import after_moves
from agent.bt import Act, Condition, Latch, Node, Selector, Sequence
from agent.world import (
    BASE_INCOME,
    ENG_COST_FLOOR,
    HALL_BONUS,
    RESOURCE_CAP,
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
DEPOT_VALUE = 3.5  # 보급소: 최초 점령 +15 자원, 팀별 건물당 1회
# 공학관: 전투병 값 3 → 2, 같은 자원으로 전투병 1.5배. 진 경기는 전투병(= 생산량) 차이로 벌어지므로
# 0.5 → 2.0으로 올렸다(main 상대 400경기 약 61% — docs/benchmarks.md)
FUNCTION_VALUE = {"LIBRARY": 1.0, "ENG": 2.0, "HOSPITAL": 0.5, "STATION": 0.3, "WATCH": 0.3}

ETA_OFFSET = 2  # 효용 분모에 더하는 값. 클수록 거리보다 건물 가치를 중시한다
KILL_VALUE = 1.0  # 적 깃발병 한 명 제거의 가치 (점수 단위)
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
# 경제 건물 몰아내기: 공학관·학생회관은 반경·가중치를 따로 둔다. 흉내 봇 "공학관 러시"(opponents/eng_rush.py) 상대로
# main이 공학관을 절반쯤 잃는다 (docs/benchmarks.md "상대 풀"). 기본값은 다른 핵심 건물과 같다(= 예전 동작)
ECON_KINDS = {"HALL", "ENG"}
ECON_EVICT_RADIUS = 2
ECON_WEIGHT = 1.0
# 이동 중 깃발병 호위: 우리 깃발병이 있는 칸마다 전투병 1명(가치 ESCORT_VALUE, 0 = 끔). 리더보드에서 우리 깃발병 옆에
# 전투병이 붙는 비율이 상대보다 낮고 깃발병이 강팀보다 2배 넘게 죽었다(이슈 #50). 파라미터 탐색(scripts/tune.py)에서
# 0 / 0.5 / 1 / 2 중 1.0: 새 시드 50개 상대 풀 48.0 → 57.2%, 서버 맵 49개 main 상대 55.1% (docs/benchmarks.md)
ESCORT_VALUE = 1.0
# 경제 건물(ECON_KINDS) 지키기·몰아내기의 필요 인원 = ECON_DEFEND_REACH걸음 안의 적 전투병 + 1 (다음 턴 위협이 더 크면
# 그것 + 1). 1이면 예전과 같다(다음 턴 그 칸에 올 수 있는 적만 셈). 흉내 봇 "공학관 러시"는 2칸 밖에서 다가오는 전투병
# 2명 + 깃발병 1명으로 우리 공학관을 빼앗았고, 그때 우리는 위협 0으로 보고 1명만 보냈다(seed 3009 31~34턴).
# 모든 건물에 넓게 세면 크게 나빠졌다(2·3·4걸음: 상대 풀 56.5 → 46.5 / 30.0 / 17.5%). 경제 건물만 2걸음: 새 시드 50개 상대
# 풀 56.4 → 62.6%, 서버 맵 49개 main 상대 59.2%. 호위만 켠 버전과 직접 대결은 새 시드 56.0%, 서버 맵 45.9%로 엇갈림
ECON_DEFEND_REACH = 2
# 같은 경기에서 우리 공학관 4칸 안 전투병 10~14명이 상대 건물 급습 길에 공학관을 지나쳤지만, 그때 급습을 멈추거나 지나가는
# 병력을 세우는 것은 모두 나빴다(docs/benchmarks.md "파라미터 탐색")
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
# 공학관 러시: RUSH_UNTIL턴까지 상대 캠퍼스 쪽 공학관(상대 본진이 더 가까운 것)에 전투병을 "위협 + RUSH_EXTRA"명 보내고,
# 공학관 점령 가치를 RUSH_CAPTURE배로 올린다(0턴 = 끔). 흉내 봇 opponents/eng_rush.py(서버 참새튀김기·페이커가 14·19턴에
# 우리 공학관을 빼앗은 방식)가 리그 1~2위였다(docs/benchmarks.md "리그"). 파라미터 탐색에서 0 / 20 / 40 / 60턴 중 60(초소와
# 함께): 새 시드 50개 상대 풀 60.4 → 67.6%, 리그 1위(생성 맵 63.3%, 서버 맵 66.3%)
RUSH_UNTIL = 60
RUSH_EXTRA = 2
RUSH_VALUE = 6.0
RUSH_CAPTURE = 3.0
# 수비 먼저 러시: 우리 공학관 RUSH_SAFE_REACH걸음 안의 적 전투병이 같은 범위 우리 전투병 + RUSH_SAFE_MARGIN보다 많으면 그
# 턴은 러시 과제를 내지 않는다(0 = 끔). 9/29 10:00 리더보드 치명ㄷ전은 러시가 상대 공학관에 7~9명을 보내는 동안 우리 공학관
# 2칸 안이 5:11 → 3:18이 되어 공학관을 맞바꾸고 둘 다 잃었다. 80턴까지 상대 공학관만 빼앗은 서버 경기는 19승 1패
RUSH_SAFE_REACH = 0
RUSH_SAFE_MARGIN = 0
# 초소: 상대 건물마다 전투병 1명(가치 PICKET_VALUE, 0 = 끔). 흉내 봇들이 서버 강팀처럼 전투병을 넓게·앞으로 깔 때 쓴 것.
# 0 / 0.5 / 1 중 1.0 (러시만 켜면 검증 60.0 → 60.5%, 초소까지 켜면 63.0%)
PICKET_VALUE = 1.0
# 별동대(hyunjin/defense-econ 1672fe2에서 옮김): 위험한 목표(상대 소유이거나 적 전투병이 닿는 건물)로 가는 깃발병에
# 전투병을 붙여, 가는 길의 다음 칸을 먼저 차지한다(호위는 점령을 시작한 뒤에만 붙는다). 현진 브랜치 상대로 진 경기는 30~60턴에
# 공학관·보급소를 잃어 전투병 생산이 벌어졌고, 현진 봇에서 별동대만 빼면 문원 봇 승률이 28 → 62%가 됐다. 문원 봇에 붙이면
# 현진 봇 상대 28 → 62%(시드 0~49) · 40 → 54%(200~249), 흉내 봇 풀 평균 68 → 79% (docs/benchmarks.md)
SQUAD_SIZE = 5
SQUAD_WEIGHT = 1.0
SECOND_SQUAD_TURN = 30  # 이 턴부터 별동대 2개 (목표 건물이 서로 다른 깃발병 2명)
# ---- 유닛 운용 실험 스위치 (moonwon/unit-ops, 모두 기본 끔 = 예전 동작) ----
# 서버 리플레이 48판 10~80턴 전투 6155건을 우리 명령으로 복원하면, 전투의 36%에 우리가 전투병 1명으로 들어가 승 8%였다
# (6명 이상은 71%). 상대가 이미 있던 칸에 들어간 전투는 55%를 졌고(2.6 : 7.5), 그 절반은 직전 턴 2칸 안에 우리 전투병이 더
# 있었다. 전투병은 1:1로 상쇄되므로 모아서 얻는 것은 그 칸(깃발병·건물)이다.
# 모아서 들어가기: 1 = 적 전투병이 선 과제 칸 바로 앞에서, 그 과제의 가장 먼 전투병이 한 걸음 거리가 될 때까지 기다린다.
# 2 = 1 + 가는 길에 적 전투병이 지금 선 칸이면, 이번 턴 그 칸에 들어갈 우리 인원이 적보다 많을 때만 들어간다.
STAGE = 0
# 모으는 거리: 1 = 예전(적 바로 옆 칸). 9/29 흉내 봇 풀에서 STAGE 1·2가 76.6 → 40.3·39.4%로 무너졌고, 같은 맵 대결에서
# 제자리에 선 전투병이 44~52 → 54~64%로 늘며 건물을 잃었다(적 옆 칸에서 기다리는 동안 상대가 먼저 움직임). 2 = 적 전투병이 한
# 걸음에 닿지 않는 거리에서 모았다가 함께 들어간다
STAGE_GAP = 1
# 요격: 적 깃발병을 뒤쫓지 않고 그 깃발병이 갈 건물(가장 가까운 우리·중립 건물, INTERCEPT_RADIUS걸음 안)에 먼저 간다.
# INTERCEPT_IDLE = 과제 없는 전투병의 공통 목표를 적 깃발병 칸 대신 그 건물로. INTERCEPT_VALUE > 0 = 그 건물이 우리 것이면
# "요격" 과제(그 칸 위협 + 1명, 가치 = 건물 가치 × INTERCEPT_VALUE)를 더한다.
INTERCEPT_IDLE = 0
INTERCEPT_VALUE = 0.0
INTERCEPT_RADIUS = 6
# 요격 인원에 깃발병 곁 적 전투병(호위)도 센다: max(그 칸 위협, 호위) + 1 (0 = 예전처럼 그 칸 위협 + 1)
# 10/1 재시험(074803e 위, 새 시드 40000번대 300판, 대 074803e / 337ab49(기준 58.0) / strong_wide(기준 74.0)): 요격 1.0 43.7 / 50.3 /
# 75.3%, + 호위 셈 37.0 / 47.7 / 76.7%, 공통 목표 요격 44.7 / 49.3 / 71.7%, FORECAST_KILL 43.0 / 53.0 / 76.0%. 뒤쫓기를 줄이면 적 깃발병
# 처치가 줄어 더 손해다 — 리플레이의 뒤쫓기 문제는 선제 수비(EARLY_GUARD)로 먼저 건물에 서는 쪽이 통했다. 모두 끈 채 남김
INTERCEPT_ESCORT = 0
# 비용 교환: 우리 전투병 값이 상대보다 싸면 공격 과제(TRADE_KINDS) 가치 × TRADE_BOOST, 비싸면 ÷ TRADE_BOOST (1 = 끔).
# 교환은 1:1이지만 값이 2 대 3이면 같은 자원으로 1.5배를 만든다
TRADE_BOOST = 1.0
TRADE_KINDS = {"처치", "급습", "러시", "초소", "별동대"}
# 1명짜리 과제의 인원: 초소(상대 건물마다)·이동 중 호위. 전선은 FRONT_NEED
PICKET_NEED = 1
ESCORT_NEED = 1
# ---- 공학관 되찾기 스위치 (moonwon/unit-ops. 탈환은 켬, 열세 국면은 끔) ----
# 리더보드 48판: 21~80턴에 우리만 공학관이 없던(전투병 값 3 : 2) 턴이 상대보다 많았던 경기는 진 15판 중 8판, 이긴 33판 중 0판.
# 공학관을 잃은 뒤 되찾은 경기는 거의 없었다(9/29 신촌도 우리땅 35~40턴 잠깐).
# 탈환: 최근 RETAKE_MEMORY턴 안에 우리 것이었던 공학관이 지금 우리 것이 아니면(중립화된 턴 = 상대가 점령하기 전 한 턴 포함)
# 그 칸에 전투병 "위협 + RETAKE_EXTRA"명(가치 RETAKE_VALUE), 그 건물의 깃발병 점령 가치 × RETAKE_CAPTURE. 0 = 끔.
# 무작위 맵 1000개(맵마다 1경기): 현진 봇 상대 44.8 → 51.0%(같은 맵 패→승 140 · 승→패 78), 끈 봇과 직접 56.9%,
# 공학관 강습 흉내 봇 상대 75.1 → 76.8%. 풀 100경기에서는 현진 상대 56 → 52%로 반대로 보였다 (docs/benchmarks.md)
RETAKE_VALUE = 8.0
RETAKE_EXTRA = 1
RETAKE_MEMORY = 20
RETAKE_CAPTURE = 2.0
# 탈환 대상 종류 (10/1 오후). 진 경기는 중앙(광장·방송국·보급소·서울역)을 내줘서 졌는데 탈환은 공학관만 본다. 중앙을 넣으면 잃은 중앙
# 건물에도 전투병이 되돌아간다. 기본 = 공학관만(예전 동작)
RETAKE_KINDS = {"ENG"}
# 공학관 열세 국면: 우리 전투병 값 > 상대 값이면 ENG_DEFICIT 가지. 전투병은 1:1 상쇄라 이때 흩어진 교전은 1.5배 손해이므로
# 초소·전선·급습(학생회관)·러시를 빼고, 우리 것이 아닌 공학관 전부에 전투병 "위협 + DEFICIT_EXTRA"명(가치 DEFICIT_VALUE),
# 공학관 점령 가치 × DEFICIT_CAPTURE. 공학관 할인은 중복되지 않으므로(최소 2) 어느 쪽 공학관이든 하나면 된다.
ENG_DEFICIT = 0
# 공학관 조기 경보: ENG_WATCH_UNTIL턴까지 우리 공학관 ENG_WATCH_REACH걸음 안에 적 전투병이 오면 몰아내기 과제를 내고, 그 범위의
# 적 전투병 + 1명을 세운다(0 = 끔). 리더보드에서 공학관을 잃은 강습(신촌도 우리땅·치명ㄷ·페이커)은 15~18턴에 3걸음 앞에서
# 모았다가 한꺼번에 들어왔는데, 몰아내기는 ECON_EVICT_RADIUS(2)걸음 안에 와야 켜져 모이는 동안 반응하지 않았다.
# 무작위 맵 1000개 × 2묶음에서 3 / 4 / 5걸음 중 5: 탈환만 켠 봇(fdb0112)과 직접 53.4·53.6%(862승 721패), 현진 봇 상대
# +3.8·+1.0%p. 강습 흉내 봇 상대는 76.8 → 75.9%로 그대로 — 강습을 막는 것이 아니라 초반 공학관 수비가 두꺼워진 효과
ENG_WATCH_REACH = 5
ENG_WATCH_UNTIL = 30
# 국면 전환 실험. 현진 봇 상대 300경기에서 31턴 뒤 97~100%의 턴이 위협 대응(THREAT)이라 다른 국면이 거의 돌지 않았다.
# 열세: 적 전투병이 우리보다 BEHIND_MARGIN명 이상 많으면 러시·초소·급습·전선을 끄고 지키는 국면(0 = 끔). 진 경기는 21~110턴의
# 37%가 전투병 10명 넘게 뒤진 턴이었다. 굳히기 먼저: HOLD 조건(LATE_TURN 뒤 추정 점수 앞섬)이면 위협 대응보다 굳히기(0 = 끔).
# 110턴에 앞선 141판 중 26판을 역전당했다
BEHIND_MARGIN = 0
HOLD_FIRST = 0
# 막판: 마지막 ENDGAME_TURNS턴은 160턴 순간의 점수만 본다(0 = 끔). 현진 봇 상대 300경기에서 한 턴 점수차 변화가 끝까지 평균
# 1.3이었고, 150턴에 앞섰다 진 경기 17 · 뒤졌다 이긴 경기 16(140턴 27 · 14) — 봇이 경기 끝을 모른다.
# 깃발병은 160턴 전에 끝낼 수 있는 짝만(상대 건물은 중립화 한 단계만 세어 점수 × 2). 나머지는 위협 대응 가지와 같고,
# FINAL_GUARD_WEIGHT > 0이면 남은 턴 안에 적 깃발병이 닿는 우리 건물 지키기(가치 = 점수 × 이 값)를 더한다.
# 처음 판(러시·초소·급습·전선·탈환·지키기를 끄고 막판 수비 2.0)은 현진 상대 54.8 → 8턴 52.9 / 12턴 52.5 / 20턴 50.1% —
# 전투병이 우리 건물 전체로 흩어져 155턴 건물 8.5:8.0 → 8.0:8.4
ENDGAME_TURNS = 0
FINAL_GUARD_WEIGHT = 0.0
# 역전: COMEBACK_TURN턴 뒤 추정 점수가 뒤지면 위협 대응보다 먼저 — 상대 건물 가치 × 2, 위험 건물 × 0.8, 급습 × 2 (0 = 끔)
COMEBACK_TURN = 0
# 초반: OPENING_TURNS턴까지 중립 건물 점령 가치 × OPENING_NEUTRAL (0 = 끔). 30턴 건물 수가 앞선 경기 승 67%, 뒤진 경기 42%.
# 무작위 맵 1000개 두 묶음에서 현진 봇 상대 54.8 → 58.7%, 53.8 → 58.5%, 탈환·조기 경보 봇(2a844fe)과 직접 55.9%.
# ×2는 57.3%, 위험 감수 0.8을 더해도 58.6%로 같음
OPENING_TURNS = 30
OPENING_NEUTRAL = 1.5
# 위협 대응 가지의 가중치 (31턴 뒤 턴의 97~100%가 이 가지라 사실상 봇 전체의 가중치)
THREAT_GUARD = 2.0
THREAT_EXTRA = 2
THREAT_DANGER = 0.5
# 성혁 브랜치(sunghyuk/attack-expand)에서 옮긴 스위치 (0 = 끔).
# 관성(73e2691): 지난 턴에 전투병을 받은 과제 칸은 거리를 SH_INERTIA만큼 깎아 계속 맡게 한다
SH_INERTIA = 0
# 점령 비용(b1f0f69): 점령 가치 × SH_COST_BASE / (SH_COST_BASE + 남은 단계의 자원 비용), 광장은 SH_PLAZA_SKIP턴 전 목표에서 뺀다.
# 무작위 맵 1000개 두 묶음에서 현진 봇 상대 58.5 → 64.7%(짝 비교 240 · 178, p = 0.003), 58.7 → 66.1%, 627cfbe와 직접 54.6%.
# 관성(SH_INERTIA = 1)은 58.5 → 60.5%(p = 0.35), 둘 다 켜면 64.6%로 점령 비용만과 같음
SH_COST_BASE = 8.0
SH_PLAZA_SKIP = 40
_served: set[Pos] = set()  # 지난 턴에 전투병을 받은 과제 칸 (관성)
DEFICIT_VALUE = 6.0
DEFICIT_EXTRA = 2
DEFICIT_CAPTURE = 3.0
# ---- 9/29 22:00 리더보드 분석 스위치 (moonwon/unit-ops, 모두 기본 끔 = 예전 동작) ----
# 그 회차에 우리 학생회관·공학관을 잃은 56번 중 30번은 적 전투병 없이 깃발병 혼자 들어왔다(점령한 우리 깃발병이 떠나면 전투병이
# 없고, 지키기는 적 깃발병이 GUARD_RADIUS 안에 와야 켜져 4~8걸음 밖 전투병이 1~2턴 늦음). 23번은 상쇄 패배였다(적이 옆 칸에
# 쌓다가 동수가 되는 턴에 들어옴, 우리는 "위협 + 1"을 계산했지만 증원이 2걸음 밖이라 한 턴 늦음).
# 경제 건물 상주: 우리 학생회관·공학관마다 전투병 ECON_GARRISON명(가치 GARRISON_VALUE, 0 = 끔)
ECON_GARRISON = 0
GARRISON_VALUE = 3.0
# 경제 건물 조기 경보: 적 깃발병이 이 걸음 안에 오면 우리 학생회관·공학관을 위협받는 건물로 본다(0 = GUARD_RADIUS 그대로)
ECON_GUARD_RADIUS = 0
# 경제 건물 지키기·몰아내기 필요 인원에 더하는 여유 (0 = 끔)
DEFEND_MARGIN = 0
# 깃발병 쫓기 제한: 적 깃발병 처치 과제를 그 깃발병이 우리 전투병 KILL_REACH걸음 안에 있을 때만 낸다(우리 건물 위 깃발병은
# 늘 낸다, 0 = 끔). 진 경기 20~80턴 우리 전투병의 32%가 건물에서 떨어진 우리 진영 칸에서 평균 8.4걸음 떨어진 목표로 가는
# 중이었고(이긴 경기 21%, 5.2걸음), 그 목표 중 가장 많은 것이 처치(22%)
KILL_REACH = 0
# 동수 공격: 급습·러시 과제의 필요 인원을, 우리 깃발병이 ATTACK_TIE걸음 안에 있으면 "위협 + 1~2"에서 "위협"으로 줄인다(0 = 끔).
# 서버 상대는 우리 건물 위 인원과 같은 수로 들어와 상쇄시킨 뒤 깃발병으로 중립화했다(상쇄 패배 23번)
ATTACK_TIE = 0
# 병력 덩어리로 쓰기. 진 경기 20~80턴 우리 전투병의 32%가 먼 목표로 이동 중이었고, 한 턴 전투병 과제 칸이 16~20개로 쪼개져
# 10~50턴 전투 뒤 상대만 남은 비율이 46~75%였다.
# 과제 수 제한: 한 턴에 채우는 전투병 과제를 TASK_LIMIT개까지만 열고, 남는 전투병은 적 깃발병을 쫓는 대신 고른 과제 중
# 가장 가까운 곳에 합류한다(0 = 끔). 깃발병을 돕는 과제(FLAG_SUPPORT)는 세지도 막지도 않는다 — 처음 판(모든 과제를 셈)은
# 호위·별동대가 잘려 깃발병이 움직이지 못해 제출본과 직접 0%였다
TASK_LIMIT = 0
FLAG_SUPPORT = {"호위", "별동대"}
TASK_MERGE = 1  # 1 = 남는 전투병을 고른 과제에 합류, 0 = 예전처럼 공통 목표(적 깃발병·점령할 건물)로
# 깃발병 관성: 지난 턴 이 칸 깃발병이 맡은 목표와의 짝은 효용 × FLAG_INERTIA (1 = 끔). 9/29 22:00 리플레이를 재현하면 깃발병
# 이동의 11%(판당 약 48번)가 다음 턴 되돌아왔고, 그중 41%(판당 17번)는 매 턴 새로 푸는 헝가리안 배정에서 깃발병끼리 목표를
# 맞바꾼 것이었다(나머지는 같은 목표에서 위협 때문에 물러남)
FLAG_INERTIA = 1.0
_flag_goal: dict[Pos, set[Pos]] = {}  # 지난 턴 이동 뒤 칸 → 그 칸 깃발병들의 목표 칸
# 깃발병 사망. 9/29 22:00 12판 120턴까지 85명(판당 7명)을 재현하면 64명은 이미 포위되어(지금 칸도 이웃도 위험) "위험해도 목표
# 쪽으로" 가지에서, 10명은 위험한 칸에 머물다, 11명은 안전하다고 본 칸에서 죽었다(적 병원 생산 8 · 적 역 순간이동 3).
# 두 걸음 앞 보기: 목표 쪽으로 나아갈 칸은 두 걸음 안 적 전투병 ≤ 그 칸과 이웃의 우리 전투병일 때만 (0 = 끔)
FLAG_LOOKAHEAD = 0
# 적 병원 생산: 위협 맵에 상대 병원에서 이번 턴 만들 수 있는 전투병을 더한다 (0 = 끔, 본진만)
HOSPITAL_THREAT = 0
# 공학관 타이밍 생산: 우리에게 공학관이 없고 곧 얻으면(eng_coming) 전투병 생산을 미뤄 값 2로 산다(0 = 끔, 1 = 이번 턴 끝, 2 = 다음
# 턴 끝까지). 리더보드 60판에서 공학관을 얻기 1~2턴 전에 값 3으로 산 전투병에 판당 약 30자원(20턴까지 16)을 썼다 — 값 2였다면
# 판당 전투병 +5명(1:1 상쇄라 끝까지 남는다). 자원 상한(RESOURCE_CAP)을 넘길 만큼은 이번 턴에 쓴다.
# 제출본(7941b88)과 직접: 1 = 새 맵 58.8 · 66.0%(시드 8000·9000번대 각 400경기), 서버 맵 61.5%. 2 = 72.8 · 65.0%, 서버 맵
# 64.8%, 흉내 봇 풀 76.6 → 80.6%. 2는 현진(7b8b67e) 74.0 / 73.8%, 0f689cd 73.5 / 72.1%(제출본은 69.0 / 68.5, 69.5 / 71.2).
# 3(3턴 앞까지)은 2와 직접 새 맵 53.0 · 58.0%(8000·9000번대), 서버 맵 55.7%, 풀 80.0 → 81.2%, 제출본 70.8%, 현진 77.0%
ENG_BANK = 3
# 같은 계열(건물을 얻는 순간을 기다려 생산). 병원 타이밍: 이번 턴 끝에 병원을 얻고 그 병원이 전투병 목표까지 지금 생산 칸보다
# HOSP_BANK걸음 이상 가까우면 한 턴 미뤄 병원에서 만든다(0 = 끔). 위협 시 적립 안 함: 우리 경제 건물 BANK_SAFE걸음 안 적
# 전투병이 우리보다 많으면 적립하지 않는다(0 = 끔)
HOSP_BANK = 0
BANK_SAFE = 0
# 수비 깃발(flag_guard_tasks): 적 깃발병이 FLAG_GUARD걸음 안에 온 우리 경제 건물 위에 우리 깃발병을 세운다(0 = 끔). 경합 규칙으로
# 적 깃발병 혼자 빼앗기(9/29 22:00 빈 건물 30번)와 동수 상쇄 뒤 중립화(상쇄 패배 23번)를 막는다. 가치 = 건물 가치 × 이 배수.
# 반경을 넓히면 깃발병이 점령을 못 하고 묶인다(4걸음: 20경기 30%). 규칙상 내 건물 위 내 깃발병이 전투로 죽으면 그 건물은 즉시
# 중립이 되고 상대 깃발병이 같은 턴에 점령할 수 있어, 적이 +1을 만들면 오히려 약점이 된다.
# ENG_BANK = 3 봇(17847af)과 직접(새 맵 8000·9000번대 / 서버 맵): 반경 1 54.8% / 54.9, 반경 2 65.5 · 57.8 / 62.3, **반경 2 × 0.5
# 65.2 · 68.2 / 63.9**(풀 80 → 88.1 · 81.6%), 반경 3 × 0.5 62.0 / 62.3. 반경 2 × 0.5는 제출본(7941b88) 71.2 / 70.5%, 현진 78.5 / 82.0%
FLAG_GUARD = 2
FLAG_GUARD_WEIGHT = 0.5
# 수비 깃발 대상 확대 (10/1 리플레이 분석): 경제 건물 말고도 추정 점수가 FLAG_GUARD_SCORE 이상인 우리 건물에 수비 깃발을 세운다
# (0 = 끔). 9/30 20:00 탈락도 락이다전에서 4점 역을 9번 잃었다 — 깃발병이 역과 옆 칸을 오가며 비울 때마다 적이 걸어 들어왔다.
# 074803e 위 직접 대결 300판(새 시드 40000번대): 점수 3 이상 대 074803e 44.0 · 337ab49 52.3(기준 58.0) · strong_wide 69.7%(74.0),
# 2 이상 36.7 · 47.7 · 67.0% — 깃발병이 고점 건물에 묶여 점령을 못 한다. 끈 채 남김
FLAG_GUARD_SCORE = 0.0
# 선제 수비 (10/1 분석, 켬): 지키기는 적 깃발병이 GUARD_RADIUS걸음 안에 와야 시작해, 멀리서 오는 소규모 기습조(깃발병 1 + 전투병 2)에게
# 후방 빈 건물을 내줬다(ACE전 학생회관·공학관·도서관). 적 깃발병이 EARLY_GUARD걸음 안이고 우리 전투병이 그 깃발병보다
# EARLY_SLACK턴 이상 먼저 닿지 못하는 우리 건물에 "선제 수비" 과제를 미리 낸다(0 = 끔). 필요 인원 = max(그 칸 위협,
# 깃발병 곁 적 전투병) + 1, 가치 = 건물 가치 × EARLY_GUARD_WEIGHT
# 074803e 위 직접 대결(시간 배율 3, 몰수 0): 새 시드 40000번대 300판 → 고르지 않은 41000번대 400판. 6걸음 여유 2: 대 074803e
# 55.3 → 53.7%, 대 337ab49 58.0 → 62.0 / 56.0 → 60.5%, 대 strong_wide 74.0 → 77.7 / 78.5 → 79.2%. 여유 1은 +2~5%p, 여유 0은 둘째
# 묶음에서 효과 없음, 8걸음은 6걸음과 비슷. 최대 응답 17 ms(기준 15~22)
EARLY_GUARD = 6
EARLY_SLACK = 2
EARLY_GUARD_WEIGHT = 1.0
# 먼 과제 억제: 전투병 과제 배정 점수 = 가치 / (1 + 가장 먼 전투병 거리) ** DIST_POWER (1 = 예전)
DIST_POWER = 1.0
# ---- 값 차이 교전 (moonwon/eval-tuning 9/30, 모두 기본 끔) ----
# 전투병은 1:1로 상쇄되므로, 우리 값이 2이고 상대가 3이면 동수 교환마다 상대가 1자원씩 더 잃는다(공학관을 가진 쪽의 이득).
# 동수 공격: 우리 값이 더 싸면 급습·러시의 필요 인원을 "위협 + 1~2"에서 "위협"(최소 1)으로 — 동수로 상쇄돼도 이득이다
TRADE_TIE = 0
# 소모전: 우리 값이 더 싸면 적 전투병이 TRADE_HUNT_MIN명 이상 선 칸마다 과제(필요 인원 = 그 칸 다음 턴 위협, 동수면 상쇄),
# 가치 = TRADE_HUNT × 적 인원 × (상대 값 − 우리 값) / 우리 값 (0 = 끔)
TRADE_HUNT = 0.0
TRADE_HUNT_MIN = 2
# ---- 한 턴 앞 예측 (moonwon/eval-tuning 9/30, 기본 끔) ----
# 상대 시점으로 이 봇의 판단을 한 번 더 돌려 상대가 이번 턴 둘 수를 예측한다(상대 모델 = 우리 봇, 상대의 기억은 따로 둔다).
# 위협 맵은 "적 전투병이 모두 이 칸으로 온다"는 최악 가정이라 깃발병이 자주 멈추고 필요 인원이 부풀었다.
# FORECAST: 1 = 깃발병 안전 판단만, 2 = 모든 위협 계산에 min(최악, 예측 + FORECAST_SLACK)을 쓴다 (0 = 끔)
FORECAST = 0
FORECAST_SLACK = 1
# 처치 과제를 적 깃발병의 지금 칸이 아니라 예측한 이번 턴 도착 칸에 낸다 (0 = 끔, FORECAST와 따로)
FORECAST_KILL = 0
# 직전 턴 판단이 이 시간(ms, 실제 실행 환경에서 잰 값)을 넘었으면 이번 턴은 예측하지 않는다(응답 제한 300 ms)
FORECAST_SKIP_MS = 90.0
_timing = {"last": 0.0}
# ---- 성혁 테마 브랜치 기능 (sunghyuk/attack-expand bb27671에서 옮김, 모두 기본 끔 = 26fa986과 같은 동작) ----
# 점령 비용(SH_COST_BASE)·광장 미루기(SH_PLAZA_SKIP)·관성(SH_INERTIA)은 7941b88에서 이미 옮겼다. 나머지를 스위치로 옮긴다.
# 건물 가치. 학생회관: 예전 0.02 × 남은 턴은 160턴에 0이 되므로, 1 = max(1.8, 3.6 − 0.2 × (턴 // 5)) (45턴에 하한).
# 공학관: 1 = max(2.0, 3.0 − 0.2 × (턴 // 5)) (복리 경제 건물이라 초반에 더 값지다, 25턴에 하한). 두 값 모두 학습 층이
# HALL_VALUE_PER_TURN · FUNCTION_VALUE["ENG"]를 바꾼 비율만큼 곱한다(학습한 W가 그대로 뜻을 갖게)
SH_HALL_DECAY = 0
SH_ENG_DECAY = 0
# 역: 1 = 순간이동 짝(STATION_MIN_LINK걸음 이상 떨어진 다른 역)과 그 역 주변 건물로 값을 매긴다(station_value). 첫 역은
# STATION_FIRST(순간이동이 아직 안 열림), 짝을 완성하는 역은 STATION_BASE + 가장 연계되는 역 주변 가치, 셋째부터 STATION_EXTRA
SH_STATION = 1
STATION_FIRST = 0.0
STATION_BASE = 2.0
STATION_EXTRA = 0.3
STATION_MIN_LINK = 4
STATION_NEIGHBOR = 3
STATION_NEIGHBOR_VALUE = {"ENG": 1.0, "DEPOT": 0.6, "HALL": 0.3}
# 고립 병원: 본진에서도 어느 역에서도 HOSPITAL_ALONE_DIST걸음 밖에 떨어진 병원의 기능 가치(0 = 끔, 성혁 2.5). 그 구역에
# 병력을 내려놓는 유일한 수단. 성혁 브랜치는 이 밖에 DEPOT_VALUE 3.5 · FUNCTION_VALUE["LIBRARY"] 1.0 (상수만 바꾸면 된다)
HOSPITAL_ISOLATED = 2.5
HOSPITAL_ALONE_DIST = 4
# 호위 인원을 턴별로: 1 = 이동 중 깃발병 호위 인원이 20턴 전 SH_ESCORT_T0 · 40턴 전 SH_ESCORT_T1 · 80턴 전 SH_ESCORT_T2 ·
# 그 뒤 SH_ESCORT_T3 (0명이면 그 구간은 이동 중 호위 없음). 끄면 ESCORT_NEED(1명)로 처음부터 끝까지
SH_ESCORT = 1
SH_ESCORT_T0 = 0
SH_ESCORT_T1 = 1
SH_ESCORT_T2 = 4
SH_ESCORT_T3 = 1
ESCORT_LEAD = 1  # 1 = 호위가 깃발병이 이번 턴 들어갈 칸을 먼저 차지한다(선행), 0 = 깃발병이 지금 있는 칸(동행)
ESCORT_ADAPTIVE = 0  # 1 = 호위 인원 = 그 칸 위협 + 1 (ESCORT_MIN ~ ESCORT_MAX)
ESCORT_MIN = 1
ESCORT_MAX = 6
# 비키기: 1 = 과제 없는 깃발병이 우리 건물 위·옆에 있으면 IDLE_KEEP(공학관·학생회관 1, 나머지 2)걸음까지 물러난다. 소유는
# 떠나도 유지되고, 남으면 깃발 뽑기(내 건물 위 내 깃발병이 죽으면 즉시 중립)의 표적이다. 중립·상대 건물 위에서는 안 비킨다
SH_IDLE = 0
IDLE_KEEP = {"ENG": 1, "HALL": 1}
IDLE_KEEP_DEFAULT = 2
FLAG_STOP_TURN = 999  # 이 턴부터 깃발병을 만들지 않는다 (999 = 끔)
# ---- 성혁 decoy-flex 브랜치 기능 (sunghyuk/decoy-flex 412f1fc, 현진 봇 위에서 만든 것을 옮김. 모두 기본 끔) ----
# 성혁 측정(26fa986 상대, 현진 봇 기준 8%): 양동 항상 17.8 · 조건부 16.0, 기동대 15.5, 역 V3 14.2, 암살 12~13, 최소 3명 9.0%.
# 유동 별동대: 별동대 인원 = 그 칸을 노리는 적(다음 턴 위협, SQUAD_REACH걸음 안 적 전투병 중 큰 쪽) + 1을 SQUAD_MIN~SQUAD_MAX로
SQUAD_FLEX = 1
SQUAD_MIN = 1
SQUAD_MAX = 5
SQUAD_REACH = 2
# 양동: DIVERSION_FROM~DIVERSION_UNTIL턴(FROM 0 = 끔), 주력 전선 가까이(우리 전투병이 DIVERSION_FRONT_REACH걸음 안에
# DIVERSION_MIN_SUPPORT명 이상)이고 수비(DIVERSION_REACH걸음 안 적 전투병)가 DIVERSION_MAX_DEF 이하인 건물 하나에 전투병 "수비 +
# DIVERSION_EXTRA"명(2~DIVERSION_MAX), 깃발병 점령 가치 × DIVERSION_CAPTURE. 학생회관·공학관은 우선순위(× DIVERSION_PRIORITY)일 뿐
# 다른 건물도 된다. DIVERSION_PATIENCE턴 동안 소유자가 안 바뀌면 DIVERSION_COOLDOWN턴 접고, 우리 전투병이 적의 DIVERSION_MIN_RATIO배
# 미만이면 하지 않는다. 상대 병력을 전선에서 분산시키는 것이 목적이다
DIVERSION_FROM = 24
DIVERSION_UNTIL = 120
DIVERSION_PRIORITY_KINDS = {"HALL", "ENG"}
DIVERSION_PRIORITY = 1.5
DIVERSION_REACH = 2
DIVERSION_MAX_DEF = 4
DIVERSION_FRONT_REACH = 5
DIVERSION_MIN_SUPPORT = 4
DIVERSION_PATIENCE = 12
DIVERSION_COOLDOWN = 25
DIVERSION_MIN_RATIO = 0.8
DIVERSION_EXTRA = 1
DIVERSION_MAX = 6
DIVERSION_VALUE = 3.0
DIVERSION_CAPTURE = 1.5
# 조건부 양동: 신호 S = 가치 × 우선순위 / (1 + 수비) / (2 + 가장 가까운 우리 전투병) × (1 + 어그로/12), 어그로 = 목표에서
# DIVERSION_AGGRO_MIN_DIST~MAX_DIST걸음 사이 적 전투병. 시작 = ① 전선 팽팽(전투병 비율 TIGHT_LO~TIGHT_HI)이고 S ≥ SIGNAL_TIGHT, 또는
# ② 쉬운 탈취(수비 ≤ EASY_DEF)에 어그로 ≥ AGGRO_MIN이고 S ≥ SIGNAL_EASY. 시작한 뒤에는 S ≥ SIGNAL_KEEP인 동안 유지(관성)
DIVERSION_COND = 1
DIVERSION_TIGHT_LO = 0.85
DIVERSION_TIGHT_HI = 1.2
DIVERSION_SIGNAL_TIGHT = 0.8
DIVERSION_SIGNAL_EASY = 1.0
DIVERSION_SIGNAL_KEEP = 0.5
DIVERSION_EASY_DEF = 1
DIVERSION_AGGRO_MIN = 6
DIVERSION_AGGRO_MIN_DIST = 3
DIVERSION_AGGRO_MAX_DIST = 7
_diversion: dict = {"target": None, "since": 0, "owner": None, "banned": {}}
# 조건부 암살: 무방비한 적 깃발병(그 칸 위협 0이고 ASSASSIN_GUARD_R걸음 안에 적 전투병 없음)을, 신호 (KILL_VALUE × n + 건물 가치 +
# ASSASSIN_EXTRA × n) / (1 + 가장 가까운 우리 전투병 거리) ≥ ASSASSIN_SIGNAL이고 거리 ≤ ASSASSIN_MAX_DIST일 때 가장 가까운 한 명이
# 잡으러 간다(처치 과제 가치 × ASSASSIN_BOOST, 필요 1명). 누구를 지정하지 않는다
ASSASSIN_COND = 0
ASSASSIN_GUARD_R = 2
ASSASSIN_EXTRA = 2.0
ASSASSIN_SIGNAL = 1.0
ASSASSIN_MAX_DIST = 3
ASSASSIN_BOOST = 3.0
# 최소 명령 인원: MIN_ORDER_FROM턴부터 전투병 과제 필요 인원을 MIN_ORDER명 이상으로 (양동·암살 예외, 0 = 끔)
MIN_ORDER = 0
MIN_ORDER_FROM = 20
ORDER_EXEMPT = {"양동", "암살"}
# 역 가치 V3 (SH_STATION 위에): 이 역 자신의 주변(전진 거점), 순간이동으로 아끼는 걸음(연계 역까지 거리), 근처 우리 공학관·학생회관
# (수비 지원)을 더한다
STATION_V3 = 0
STATION_LINK_GAIN = 0.5
STATION_DEFENSE = 0.6
# 역 차단 (10/1 10:00 리더보드 분석, 기본 끔): 역 가치는 우리 순간이동망만 셌고 상대 망을 끊는 값은 없었다. 그 회차 160턴까지 간 진
# 경기는 상대가 역 2개 이상(턴당 5명 순간이동)을 가진 턴이 116~153턴이었고(이긴 경기는 대부분 80턴 아래), 생산·지출은 같은데 상대
# 전투병이 중앙 32~35 : 우리 18~19로 앞섰다. STATION_DENY > 0 = 상대 역이 n개(≥ 2)일 때 상대 역 가치에 STATION_DENY / (n − 1)을
# 더한다(n − 1개를 빼앗아야 망이 끊긴다). STATION_DENY_PRE > 0 = 상대 역이 1개일 때 그 역과 이어질 중립 역에 STATION_DENY ×
# 이 값(상대 망이 생기기 전에 먼저 차지). STATION_RAID = 1 = 상대 역이 2개 이상이면 상대 역도 급습(전투병) 대상, 2 = 상대 역이
# 딱 2개일 때만(하나를 빼앗으면 망이 끊길 때)
STATION_DENY = 0.0
STATION_DENY_PRE = 0.0
STATION_RAID = 0
# 포위된 깃발병 (10/1 10:00 리더보드 분석, 기본 끔): 진 경기는 깃발병이 판당 12.9명 죽었고(이긴 경기 5.5) 그중 11.7명이 위협(1걸음 안
# 적 전투병)이 우리 전투병보다 많은 칸으로 걸어 들어가 죽었다 — 지금 칸도 이웃도 위험할 때의 "위험해도 목표 쪽으로" 가지. 리더보드
# 두 회차 진 15판에서 이 강행 279번 중 그 칸이 실제로 죽는 칸이었던 것이 181번(65%), 같은 순간 열세(위협 − 우리 전투병)가 가장 작은
# 이웃이었다면 131번(47%). FLAG_ESCAPE = 1 = 포위되면 열세가 가장 작은 이웃으로(같으면 목표에 가까운 쪽), 2 = 제자리도 후보, 0 = 끔.
# ee4ea4b 위 직접 대결(새 시드 63000·64000번대 600판씩): 1은 대 ee4ea4b 64.4 · 68.0%, 337ab49 66.8 → 77.0 · 67.8 → 75.3%,
# strong_wide 82.5 → 85.7 · 79.2 → 85.7%, 현진 7b8b67e 91.8 → 94.5% — 쓴 상대 모두 +. 2는 대 ee4ea4b 54.1%. 로컬 80판에서 우리
# 깃발병 생산 9.8 → 8.8명, 상대 9.8 → 11.2명 (docs/benchmarks.md "진 경기 분석 스위치")
FLAG_ESCAPE = 1
# 목표 쪽 칸보다 열세가 이만큼 이상 작은 칸이 있을 때만 피한다(0 = 조금이라도 작으면 피함). 시드 65000번대 400판: 0 · 1(열세가 정수라
# 0과 같음) 대 ee4ea4b 68.6%, 2 64.8%, 3 60.9%
FLAG_ESCAPE_GAIN = 0
# 기동대: 우리 진영 깊은 곳(상대 본진까지 걸음 ≥ MOBILE_ENEMY_DIST) 건물을 MOBILE_WINDOW턴 안에 MOBILE_FLIPS번 이상 잃으면 그 건물에
# 전담 전투병 MOBILE_SIZE명(가치 × MOBILE_WEIGHT), 마지막으로 잃은 뒤 MOBILE_CALM턴 조용하면 푼다 (0 = 끔)
MOBILE = 1
MOBILE_FLIPS = 2
MOBILE_WINDOW = 80
MOBILE_CALM = 30
MOBILE_SIZE = 3
MOBILE_WEIGHT = 2.0
MOBILE_ENEMY_DIST = 9
# 기동대 수정(성혁 10/1): "우리 진영 깊은 곳"을 상대 본진까지 걸음이 아니라 (상대 본진까지 걸음 − 우리 본진까지 걸음) ≥ MOBILE_DEPTH로
# 본다. 앞 기준은 벽 너머 상대 구석 건물(10,14)을 우리 진영으로 잘못 셌다. 0이면 예전 기준(MOBILE_ENEMY_DIST). 급습이 40턴 안팎
# 간격으로 오는 경기(리플레이: 공학관 (1,2)를 31·72·108·145턴에 잃음)를 잡으려고 횟수·기간을 2번/80턴으로 완화했다.
MOBILE_DEPTH = 3
_lost: dict = {"owner": {}, "turns": {}}  # 건물 id → 지난 소유자 / 우리가 잃은 턴 목록

# 양동 기대값(성혁 10/1): DIVERSION_EV면 무작정 희생하지 않고 성공 확률과 건물 가치를 본다.
#   p = 우리 지원 전투병(목표에서 DIVERSION_FRONT_REACH걸음 안) / (지원 + 목표에서 DIVERSION_RIVAL_REACH걸음 안의 적 전투병)
#   EV = p × (건물 가치 × 우선순위) − (1 − p) × 보낼 인원 × DIVERSION_LOSS_PER_W
# 시작: p ≥ DIVERSION_P_MIN이고 EV ≥ DIVERSION_EV_MIN. 유지: EV ≥ DIVERSION_EV_KEEP. 0이면 끔.
# DIVERSION_SKIP_HOME이면 우리 진영 깊은 곳(MOBILE_DEPTH 기준) 건물은 양동 후보에서 뺀다 — 그건 양동이 아니라 되찾기(탈환·기동대)다.
DIVERSION_EV = 0
DIVERSION_SKIP_HOME = 0
DIVERSION_RIVAL_REACH = 5
DIVERSION_P_MIN = 0.55
DIVERSION_EV_MIN = 1.0
DIVERSION_EV_KEEP = 0.4
DIVERSION_LOSS_PER_W = 0.3

# 사냥꾼 조(성혁 10/1): HUNTERS_FORM_UNTIL턴 안에 만든 전투병 HUNTERS_SIZE명을 하나의 무리(한 칸에 뭉쳐 이동)로 따로 둔다. 다른 과제에는
# 배정하지 않고, 죽지 않는 것을 우선한다(밟을 칸의 적 위협 ≤ 인원 − HUNTERS_MARGIN). 하는 일:
#  1) 무방비한 적 깃발병(HUNTERS_GUARD_R걸음 안에 적 전투병이 없고 그 칸 위협이 안전 범위)을 잡으러 간다.
#  2) 잡을 깃발병이 없으면 미끼: 안전한 칸 중 적 전투병 무리와 HUNTERS_KITE걸음을 유지해 적이 쫓아오게 한다. 어느 무리를 미끼 삼을지는
#     양동 목표가 있으면 그 수비대, 없으면 상대 공학관·학생회관 근처를 지키는 무리다(그 병력을 전선·핵심 건물에서 떼어 놓는다).
# 죽은 인원은 다시 채우지 않는다. 0이면 끔.
HUNTERS = 0
HUNTERS_SIZE = 5
HUNTERS_FORM_UNTIL = 10
HUNTERS_MARGIN = 1
HUNTERS_GUARD_R = 1
HUNTERS_KITE = 3
HUNTERS_FLAG_EXTRA = 1.5  # 적 깃발병 한 명(자원 5 = 전투병 1.7명)의 값
_hunters: dict = {"cells": Counter(), "designated": 0, "formed": False, "deaths": 0}

# 도미노 소탕(성혁 10/1): 우리 점수가 맵 총점의 과반이고, 상대 건물이 SWEEP_ENEMY_MAX곳 이하이고, 우리 전투병이 적 + SWEEP_W_MARGIN 이상이며
# SWEEP_FROM턴 뒤면 소탕 국면에 들어간다(최우선 국면, Latch로 3턴 유지). 남은 상대 건물마다 전투병 "위협 + SWEEP_EXTRA"명을 배정해(필요
# 인원이 적은 건물부터, 합이 우리 전투병 × SWEEP_FRAC를 넘는 건물은 타격 목록에서 뺀다) 한꺼번에 덮친다. 깃발병은 상대 건물 점령 가치를
# 2배로 받아 계속 점령한다. 상대 건물이 모두 중립화되면 상대 점수가 0이 된다. 0 = 끔.
SWEEP = 0
SWEEP_FROM = 40
SWEEP_ENEMY_MAX = 5
SWEEP_W_MARGIN = 0
SWEEP_EXTRA = 1
SWEEP_WEIGHT = 3.0
SWEEP_FRAC = 0.85
HALL_VALUE_REF = 0.02  # 학습 층 비율의 기준 (= 위 HALL_VALUE_PER_TURN 기준값)
ENG_VALUE_REF = 2.0  # (= FUNCTION_VALUE["ENG"] 기준값)
# ---- 상대 스타일 감지 (moonwon/eval-tuning 9/30, 기본 끔) ----
# 서버 리플레이 80여 판에서 우리가 진 강팀(ACE·참새튀김기·페이커·모든상금은…·렛츠고·치명ㄷ)은 공통으로 전투병을 20~40칸에 넓게
# 깔고, 깃발병은 3~6명이며 호위 없이 우리 건물 2칸 안에 오는 일이 드물었다(턴 비율 0.04~0.25). 이긴 상대는 대부분 0.5~0.9.
# STYLE_FROM턴부터 STYLE_UNTIL턴까지 모은 지표로, STYLE_TURN턴 뒤 "적 전투병 칸 평균 ≥ STYLE_CELLS이고 호위 없는 접근 비율
# ≤ STYLE_RAID"이면 넓게 까는 강팀으로 보고 STYLE_MULT(학습 층 상수 → 배수)를 곱한다 (STYLE = 0이면 끔)
STYLE = 0
STYLE_FROM, STYLE_TURN, STYLE_UNTIL = 5, 30, 60
STYLE_CELLS = 19.0
STYLE_RAID = 0.3
STYLE_MULT: dict[str, float] = {}
_style = {"turns": 0, "raid": 0, "cells": 0, "cell_turns": 0, "wide": False}
_enemy_memory: dict[str, object] = {}  # 상대 시점 판단이 쓰는 턴 간 기억 (우리 기억과 섞지 않는다)
_MEMORY_NAMES = ("_phase", "_depots_taken", "_last_owned", "_served", "_flag_goal", "_diversion", "_lost", "_hunters")

_phase = {"name": "EXPAND", "calm": 0}  # 직전 국면과, 그 국면의 조건이 연속으로 풀린 턴 수

_depots_taken: set[int] = set()  # 우리가 소유했던 보급소 id (보너스는 1회뿐). 한 프로세스 = 한 경기
_last_owned: dict[int, int] = {}  # 건물 id → 우리가 마지막으로 소유한 턴 (탈환 과제)
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
        self.deadline: int | None = None  # 막판: 남은 턴 (이 안에 끝낼 수 없는 점령 짝은 배정하지 않는다)
        self.pred: tuple[Counter, dict[Pos, Pos]] | None = None  # 한 턴 앞 예측 (FORECAST)
        self.diversion_ok = False  # 이번 국면이 양동을 켰는가 (점령 과제가 읽는다)
        self.diversion: Building | None = None
        self.hunter_move: tuple[Pos, Pos, int] | None = None  # (출발, 도착, 인원) 이번 턴 사냥꾼 조의 움직임
        self.hunter_stay: dict[Pos, int] = {}  # 집결 중이라 제자리에 있는 사냥꾼

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
    start = time.perf_counter()
    pred = None
    if (FORECAST or FORECAST_KILL) and _timing["last"] <= FORECAST_SKIP_MS:
        pred = predict_enemy(world)
    learned.apply(world, globals())  # 학습한 상황별 가중치 층 (agent/learned.py)
    if STYLE and watch_style(world):
        g = globals()
        for name, mult in STYLE_MULT.items():
            g[name] = int(round(g[name] * mult)) if isinstance(g[name], int) else g[name] * mult
    turn = Turn(world)
    turn.pred = pred
    TURN_TREE.tick(turn)
    _timing["last"] = (time.perf_counter() - start) * 1000
    return turn.actions


def watch_style(world: World) -> bool:
    """상대 스타일 지표를 이번 턴 상태로 갱신하고, 넓게 까는 강팀으로 보이는지 돌려준다(STYLE)."""
    s = _style
    if world.turn <= 1:
        s.update(turns=0, raid=0, cells=0, cell_turns=0, wide=False)
    me, enemy = world.me, world.enemy
    if STYLE_FROM <= world.turn <= STYLE_UNTIL:
        ew = world.units_of(enemy, "W")
        ours = [b.pos for b in world.owned(me)]
        s["turns"] += 1
        if ours and any(min(manhattan(p, b) for b in ours) <= 2 and not any(manhattan(p, q) <= 1 for q, _ in ew)
                        for p, _ in world.units_of(enemy, "F")):
            s["raid"] += 1
        if world.turn >= 20 and ew:
            s["cells"] += len(ew)
            s["cell_turns"] += 1
        if world.turn >= STYLE_TURN and s["cell_turns"]:
            s["wide"] = (s["cells"] / s["cell_turns"] >= STYLE_CELLS and s["raid"] / s["turns"] <= STYLE_RAID)
    return s["wide"]


def predict_enemy(world: World) -> tuple[Counter, dict[Pos, Pos]]:
    """상대가 이번 턴 둘 수를 이 봇의 판단으로 예측: (이동 뒤 (병종, 칸) → 인원, 적 깃발병 출발 칸 → 도착 칸).
    상대 시점 판단은 우리 턴 간 기억(국면·관성 등)을 건드리지 않도록 상대 몫의 기억으로 바꿔 끼운 채 돌린다."""
    g = globals()
    ours = {name: g[name] for name in _MEMORY_NAMES}
    if world.turn <= 1 or not _enemy_memory:
        _enemy_memory.update(_phase={"name": "EXPAND", "calm": 0}, _depots_taken=set(), _last_owned={},
                             _served=set(), _flag_goal={},
                             _diversion={"target": None, "since": 0, "owner": None, "banned": {}},
                             _lost={"owner": {}, "turns": {}},
                             _hunters={"cells": Counter(), "designated": 0, "formed": False, "deaths": 0})
    g.update(_enemy_memory)
    try:
        view = replace(world, me=world.enemy)
        learned.apply(view, g)
        t = Turn(view)
        TURN_TREE.tick(t)
        actions = t.actions
    finally:
        _enemy_memory.update({name: g[name] for name in _MEMORY_NAMES})
        g.update(ours)
    flag_dst: dict[Pos, Pos] = {}
    for a in actions:
        if isinstance(a, Move) and a.kind == "F" and a.src not in flag_dst:
            flag_dst[a.src] = a.dst
    return after_moves(world, world.enemy, actions), flag_dst


def read_situation(t: Turn) -> None:
    """상황 읽기: 적 위치·위협 맵·건물 가치·목표 후보·국면 조건."""
    world = t.world
    me, enemy = world.me, world.enemy
    remember(world)
    t.order = direction_order(world)
    t.key = key = normalizer(world)  # 동점일 때의 순서를 자기 본진 기준으로 맞춘다 → 양 진영이 거울처럼 움직인다
    # 역 순간이동: 우리 역이 2개 이상이면 역끼리 비용 1로 이어진 경로도 최단거리에 넣는다 (전투병 이동에만.
    # 깃발병에 쓰면 효과가 없었다 — docs/benchmarks.md)
    stations = sorted((b.pos for b in world.owned(me, "STATION")), key=key)
    t.gates = tuple(stations) if len(stations) >= 2 else ()
    t.enemy_flags = dict(sorted(world.units_of(enemy, "F"), key=lambda u: key(u[0])))
    t.enemy_warriors = world.units_of(enemy, "W")
    t.threat = threat_map(t.enemy_warriors + enemy_spawnable(world), world.map.passable)
    t.flag_threat = t.threat
    t.flag_dst = {}
    if t.pred is not None:
        moved, t.flag_dst = t.pred
        if FORECAST:
            blend = {p: min(v, moved[("W", p)] + FORECAST_SLACK) for p, v in t.threat.items()}
            t.flag_threat = blend
            if FORECAST >= 2:
                t.threat = blend
    t.values = {b.id: building_value(world, b) for b in world.buildings.values()}
    t.diversion = diversion_target(t)
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
    t.flag_plan1 = assign_flags(t.flags, t.f_tasks, t.dist_to, t.deadline)
    t.capturing_now = capturing(t.flag_plan1, t.dist_to)


def reserve_capture_cost(t: Turn) -> None:
    """이번 턴 점령 비용만 남기고 나머지를 생산 예산으로."""
    world, me = t.world, t.world.me
    need = sum(world.stage_cost(task.building) for task in t.capturing_now if task.stages > 0)  # 수비 깃발은 비용 없음
    income = BASE_INCOME + HALL_BONUS * len(world.owned(me, "HALL"))
    t.budget = max(0, world.gold[me] - max(0, need - income))  # 점령은 이번 턴 수입 뒤에 치른다


def plan_warrior_tasks(t: Turn) -> None:
    """전투병 과제 목록(이번 국면이 켠 종류)과, 과제가 없는 전투병의 공통 목표."""
    t.w_tasks = sorted(trade_weighted(t, t.tasks("W") + hunt_tasks(t)), key=lambda task: t.key(task.pos))
    if MIN_ORDER and t.world.turn >= MIN_ORDER_FROM:  # 소수 전투병에게는 명령을 주지 않는다 (양동·암살 예외)
        t.w_tasks = [task if task.kind in ORDER_EXEMPT or task.need >= MIN_ORDER else replace(task, need=MIN_ORDER)
                     for task in t.w_tasks]
    # 과제가 없는 전투병은 모두 같은 목표 집합으로 가므로, 목표 쪽에서 BFS를 한 번만 한다.
    # (전투병마다 BFS를 하면 유닛 수에 비례해 느려진다 — 서버에서 186명일 때 응답 214 ms)
    t.goals = set(t.enemy_flags) or {b.pos for b in t.free_targets}
    if INTERCEPT_IDLE and t.enemy_flags:
        t.goals = {b.pos for b in intercept_targets(t).values()} or t.goals
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
    want_f = 0 if world.turn >= FLAG_STOP_TURN else max(0, min(len(t.f_tasks) + SPARE_FLAGS, MAX_FLAGS) - nf)
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
    more_f = min(budget // fc, want_f - make_f)
    make_f += more_f
    budget -= more_f * fc
    if make_f == want_f:  # 깃발병이 충분하면 남는 자원은 쌓아 두지 않고 전투병으로
        make_w += budget // wc
    # M4: 생산 위치 — 본진 또는 우리 병원 중 목표에 가장 가까운 안전한 곳 (동점이면 본진)
    passable = world.map.passable
    sites = [world.map.bases[me]] + sorted((b.pos for b in world.owned(me, "HOSPITAL")), key=key)
    bank = ((ENG_BANK and wc > ENG_COST_FLOOR and eng_coming(t)) or (HOSP_BANK and hospital_coming(t, sites)))
    if bank and not bank_unsafe(t):
        # 곧 공학관(값 인하)이나 목표에 가까운 병원(생산 위치)을 얻으면 전투병은 그 뒤에 산다. 다음 턴 자원이 상한을 넘길
        # 만큼은 이번에 쓴다
        income = BASE_INCOME + HALL_BONUS * len(world.owned(me, "HALL"))
        must = max(0, world.gold[me] + income - RESOURCE_CAP - make_f * fc)
        make_w = min(make_w, -(-must // wc))
    t.make_w, t.make_f = make_w, make_f
    # 전투병은 위협받는 병원에서도 만든다: 전투병끼리는 1:1로 상쇄되어 손해가 없고, 그 자리에서 병원을 지킨다.
    # (위협받는 병원을 빼던 때는 적이 다가오는 턴마다 먼 본진에서 생산했다 — 9/28 리더보드 패배 3경기에서 22~27턴)
    t.w_site = spawn_site(sites, distance_map(t.goals | {task.pos for task in t.w_tasks}, passable), {})
    t.f_site = spawn_site(sites, distance_map({task.pos for task in t.f_tasks}, passable), t.threat)
    if make_w:
        t.actions.append(Spawn("W", make_w, None if t.w_site == sites[0] else t.w_site))
    if make_f:
        t.actions.append(Spawn("F", make_f, None if t.f_site == sites[0] else t.f_site))


def eng_coming(t: Turn) -> bool:
    """공학관을 곧 얻는가: ENG_BANK = 1이면 이번 턴 끝(깃발병이 1걸음 안이고 점령 1단계 남음), 2면 다음 턴 끝까지
    (2걸음 안이고 1단계 남음, 또는 1걸음 안이고 2단계 남음 = 이번 턴 중립화 → 다음 턴 점령)."""
    for pos, task in t.flag_plan1:
        if task.building is None or task.building.kind != "ENG":
            continue
        d = t.dist_to(task.pos).get(pos, 99)
        if d <= 1 and task.stages == 1:
            return True
        if ENG_BANK >= 2 and ((d <= 2 and task.stages == 1) or (d <= 1 and task.stages == 2)):
            return True
        if ENG_BANK >= 3 and ((d <= 3 and task.stages == 1) or (d <= 2 and task.stages == 2)):
            return True
    return False


def bank_unsafe(t: Turn) -> bool:
    """BANK_SAFE: 우리 경제 건물마다 BANK_SAFE걸음 안 적 전투병이 우리 전투병보다 많으면 적립하지 않는다."""
    if not BANK_SAFE:
        return False
    world = t.world
    ours = world.units_of(world.me, "W")
    for b in world.owned(world.me):
        if b.kind not in ECON_KINDS:
            continue
        dist = t.dist_to(b.pos)
        if (sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= BANK_SAFE)
                > sum(n for p, n in ours if dist.get(p, 99) <= BANK_SAFE)):
            return True
    return False


def hospital_coming(t: Turn, sites: list[Pos]) -> bool:
    """HOSP_BANK: 이번 턴 끝에 병원을 얻고(깃발병 1걸음 안, 1단계 남음), 그 병원이 전투병 목표까지 지금 생산 칸보다 HOSP_BANK걸음
    이상 가까운가."""
    goal_dist = distance_map(t.goals | {task.pos for task in t.w_tasks}, t.world.map.passable)
    now = min(goal_dist.get(s, 10**6) for s in sites)
    for pos, task in t.flag_plan1:
        b = task.building
        if b is None or b.kind != "HOSPITAL" or task.stages != 1 or t.dist_to(task.pos).get(pos, 99) > 1:
            continue
        if goal_dist.get(b.pos, 10**6) <= now - HOSP_BANK:
            return True
    return False


def plan_warriors(t: Turn) -> None:
    """전투병 배정: 과제마다 가장 가까운 전투병을 붙인다(이번 턴 새로 만든 전투병 포함)."""
    global _served
    hunters_update(t.world)
    warriors = with_spawned(t.world.units_of(t.world.me, "W"), t.w_site, t.make_w, t.key)
    t.hunter_move, t.hunter_stay = None, {}
    if HUNTERS:
        warriors = hunters_plan(t, warriors)
    t.w_plan, t.w_idle, t.arrival = assign_warriors(warriors, t.w_tasks, t.dist_to, frozenset(_served))
    _served = {dst for _, dst in t.w_plan}


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
        groups.append((pos not in gates, tele.get(pos, 0), key(pos), i, pos, n, walk, tele, goal))
    queued = 0  # 이번 턴 순간이동 경로에 태운 인원 = 대기열. 역에 이미 선 인원부터 센다
    enemy_w = dict(t.enemy_warriors)
    for *_, pos, n, walk, tele, goal in sorted(groups):
        if (STAGE and goal is not None and enemy_w.get(goal) and walk.get(pos) == STAGE_GAP
                and t.arrival.get(goal, 0) > STAGE_GAP):
            w_after[pos] += n  # 과제의 나머지 전투병이 STAGE_GAP걸음 안에 올 때까지 그 거리에서 기다린다
            continue
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
    if STAGE >= 2:  # 적 전투병이 선 칸에, 들어갈 우리 인원이 적보다 적으면 들어가지 않는다
        for (src, dst), n in list(w_steps.items()):
            if enemy_w.get(dst, 0) > w_after[dst]:
                del w_steps[(src, dst)]
                w_after[dst] -= n
                w_after[src] += n
    t.actions += [Move(src, "W", n, dst) for (src, dst), n in w_steps.items()]
    if t.hunter_move:  # 사냥꾼 조: 한 무리로 움직인다
        src, dst, n = t.hunter_move
        if dst != src:
            t.actions.append(Move(src, "W", n, dst))
        w_after[dst] += n
    for pos, n in t.hunter_stay.items():
        w_after[pos] += n
    t.w_after = w_after


def replan_flags(t: Turn) -> None:
    """깃발병 2차: 전투병이 깃발을 뽑아 줄 건물을 점령 과제에 넣고, 새로 만든 깃발병까지 다시 배정한다."""
    t.pulled = {b.id for b in t.others if b.pos in t.enemy_flags and b.pos in t.arrival}
    t.targets = t.free_targets + [b for b in t.others if b.id in t.pulled]
    flags = with_spawned(t.flags, t.f_site, t.make_f, t.key)
    t.plan = assign_flags(flags, t.tasks("F"), t.dist_to, t.deadline)


def move_flags(t: Turn) -> None:
    """깃발병 이동: 한 명씩 FLAG_TREE로 다음 칸을 정한다."""
    threat, w_after = t.flag_threat, t.w_after

    def safe(pos: Pos) -> bool:
        # 전투병 수가 같으면 서로 상쇄되고 남은 전투병이 없어 깃발병은 살아남는다
        return threat.get(pos, 0) <= w_after[pos]

    def margin(pos: Pos) -> int:
        """이 칸의 열세: 다음 턴 올 수 있는 적 전투병 − 이동 뒤 우리 전투병 (FLAG_ESCAPE)."""
        return threat.get(pos, 0) - w_after[pos]

    def ahead(pos: Pos) -> bool:
        """나아갈 칸: 안전하고, FLAG_LOOKAHEAD면 두 걸음 안 적 전투병 ≤ 그 칸과 이웃의 우리 전투병(다음 턴 포위 대비)."""
        if not safe(pos):
            return False
        if not FLAG_LOOKAHEAD:
            return True
        dist = t.dist_to(pos)
        enemy = sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= 2)
        ours = sum(n for p, n in w_after.items() if dist.get(p, 99) <= 1)
        return enemy <= ours

    f_steps: Counter[tuple[Pos, Pos]] = Counter()
    goals: dict[Pos, set[Pos]] = {}  # 이동 뒤 칸 → 그 칸 깃발병들의 목표 (다음 턴 FLAG_INERTIA)
    for pos, task in t.plan:
        # 전투병이 이번 턴에 못 오면 한 칸 앞에서 대기
        hold = task.building.id in t.pulled and t.arrival[task.pos] > 1
        step = flag_step(pos, task.pos, t.dist_to(task.pos), t.order, safe, hold, ahead, margin)
        if step:
            f_steps[(pos, step)] += 1
        goals.setdefault(step or pos, set()).add(task.pos)
    if SH_IDLE:  # 과제 없는 깃발병은 우리 건물에서 IDLE_KEEP걸음까지 비킨다
        planned = {pos for pos, _ in t.plan}
        for pos, _ in t.flags:
            if pos not in planned:
                step = idle_step(t, pos, safe)
                if step:
                    f_steps[(pos, step)] += 1
    _flag_goal.clear()
    _flag_goal.update(goals)
    t.actions += [Move(src, "F", n, dst) for (src, dst), n in f_steps.items()]


def idle_step(t: Turn, pos: Pos, safe: Callable[[Pos], bool]) -> Pos | None:
    """SH_IDLE: 과제 없는 깃발병의 다음 칸. 우리 건물에서 IDLE_KEEP(공학관·학생회관 1, 나머지 2)걸음까지 물러난다."""
    near = [b for b in t.world.owned(t.world.me) if manhattan(b.pos, pos) <= IDLE_KEEP_DEFAULT]
    want = [b for b in near if manhattan(b.pos, pos) < IDLE_KEEP.get(b.kind, IDLE_KEEP_DEFAULT)]
    if not want:
        return None
    best = None
    for dx, dy in t.order:
        nxt = (pos[0] + dx, pos[1] + dy)
        if not t.world.map.passable(nxt) or not safe(nxt):
            continue
        gain = min(manhattan(b.pos, nxt) - manhattan(b.pos, pos) for b in want)
        if gain > 0 and (best is None or t.key(nxt) < t.key(best)):
            best = nxt
    return best


def set_priority(t: Turn) -> None:
    """이번 턴 점령할 건물이 둘 이상이면 가치 순으로 PRIORITY."""
    now = sorted(capturing(t.plan, t.dist_to), key=lambda task: -t.values[task.building.id])
    if len(now) >= 2:
        t.actions.append(Priority(tuple(task.pos for task in now)))


def remember(world: World) -> None:
    """턴을 넘어 기억해야 하는 것: 보급소 보너스를 이미 받았는지, 직전 국면, 거리표 캐시."""
    if world.turn <= 1:
        _depots_taken.clear()
        _last_owned.clear()
        _served.clear()
        _flag_goal.clear()
        _phase.update(name="EXPAND", calm=0)
        _diversion.update(target=None, since=0, owner=None, banned={})
        _lost.update(owner={}, turns={})
        _hunters.update(cells=Counter(), designated=0, formed=False, deaths=0)
    _depots_taken.update(b.id for b in world.owned(world.me, "DEPOT"))
    if MOBILE:  # 우리가 잃은 건물 (기동대)
        for b in world.buildings.values():
            if _lost["owner"].get(b.id) == world.me and b.owner != world.me:
                _lost["turns"].setdefault(b.id, []).append(world.turn)
            _lost["owner"][b.id] = b.owner
    _last_owned.update((b.id, world.turn) for b in world.owned(world.me))
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
    """적 깃발병이 GUARD_RADIUS(경제 건물은 ECON_GUARD_RADIUS가 더 크면 그것) 안에 들어온 우리 건물과, 가장 가까운 적
    깃발병까지의 거리."""
    found = []
    for b in world.owned(world.me):
        dist = dist_to(b.pos)
        near = min((dist[p] for p in enemy_flags if p in dist), default=None)
        radius = max(GUARD_RADIUS, ECON_GUARD_RADIUS) if b.kind in ECON_KINDS else GUARD_RADIUS
        if near is not None and near <= radius:
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
    hold = world.turn >= LATE_TURN and mine > theirs
    total = sum(estimated_score(world, b) for b in world.buildings.values())
    sweep = (bool(SWEEP) and world.turn >= SWEEP_FROM and mine * 2 > total and my_w >= enemy_w + SWEEP_W_MARGIN
             and 0 < len(world.owned(enemy)) <= SWEEP_ENEMY_MAX)
    return {
        "SWEEP": sweep,
        "ENDGAME": ENDGAME_TURNS > 0 and world.turn > TOTAL_TURNS - ENDGAME_TURNS,
        "COMEBACK": COMEBACK_TURN > 0 and world.turn >= COMEBACK_TURN and mine < theirs,
        "BEHIND": BEHIND_MARGIN > 0 and enemy_w >= my_w + BEHIND_MARGIN,
        "THREAT": pressure >= THREAT_PRESSURE and not (HOLD_FIRST and hold),
        "HOLD": hold,
        "ATTACK": my_w >= enemy_w + ATTACK_MARGIN and bool(world.owned(enemy)),
        "DEFICIT": bool(ENG_DEFICIT) and world.warrior_cost(me) > world.warrior_cost(enemy),
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
        if b.kind == "PLAZA" and t.world.turn < SH_PLAZA_SKIP:
            continue
        pulled = b.id in t.pulled
        covered = pulled or b.pos in arrival
        stages = 1 if pulled or b.owner is None else 2
        value = (t.values[b.id]
                 * (DIVERSION_CAPTURE if t.diversion_ok and t.diversion is b else 1.0)
                 * (danger if t.threat.get(b.pos, 0) and not covered else 1.0)
                 * (steal if b.owner is not None else 1.0)
                 * (RAID_STEAL if b.owner == t.world.enemy and b.kind in RAID_KINDS else 1.0)
                 * (RUSH_CAPTURE if b.kind == "ENG" and t.world.turn <= RUSH_UNTIL else 1.0)
                 * (RETAKE_CAPTURE if RETAKE_VALUE > 0 and recently_lost(t, b) else 1.0)
                 * (DEFICIT_CAPTURE if b.kind == "ENG" and getattr(t, "eng_focus", False) else 1.0)
                 * (OPENING_NEUTRAL if b.owner is None and t.world.turn <= OPENING_TURNS else 1.0)
                 * (SH_COST_BASE / (SH_COST_BASE + t.world.stage_cost(b) * stages) if SH_COST_BASE > 0 else 1.0))
        tasks.append(Task("점령", "F", b.pos, 1, value, b, stages))
    return tasks + flag_guard_tasks(t)


def flag_guard_tasks(t: Turn) -> list[Task]:
    """수비 깃발(FLAG_GUARD > 0): 적 깃발병이 FLAG_GUARD걸음 안에 온 우리 경제 건물(ECON_KINDS) 위에 우리 깃발병을 세운다.
    규칙상 건물 칸에 양 팀 깃발병이 함께 있으면 그 턴 점령이 진행되지 않으므로(경합), 적 깃발병 혼자로는 빼앗지 못하고
    전투병이 동수로 상쇄돼도 중립화되지 않는다 — 적은 동수가 아니라 +1이 필요하다. 남은 점령 단계는 0(점령비 없음)."""
    if FLAG_GUARD <= 0:
        return []
    tasks = []
    for b in t.world.owned(t.world.me):
        if b.kind not in ECON_KINDS and not (FLAG_GUARD_SCORE and estimated_score(t.world, b) >= FLAG_GUARD_SCORE):
            continue
        dist = t.dist_to(b.pos)
        if any(dist.get(p, 99) <= FLAG_GUARD for p in t.enemy_flags):
            tasks.append(Task("수비 깃발", "F", b.pos, 1, t.values[b.id] * FLAG_GUARD_WEIGHT, b, 0))
    return tasks


def kill_tasks(t: Turn) -> list[Task]:
    """처치: 적 깃발병. 이기려면 그 칸에 모일 수 있는 적 전투병보다 한 명 많아야 한다.
    건물 위면 그 건물 가치를 더한다: 우리 건물이면 방어, 중립이면 점령 저지, 상대 건물이면 깃발 뽑기.
    KILL_REACH > 0이면 우리 전투병이 KILL_REACH걸음 안에 없는 깃발병은 쫓지 않는다(우리 건물 위 깃발병은 늘 쫓는다)."""
    tasks = []
    ours = [p for p, _ in t.world.units_of(t.world.me, "W")] if KILL_REACH > 0 else []
    for pos, n in t.enemy_flags.items():
        b = t.world.building_at(pos)
        if KILL_REACH > 0 and not (b and b.owner == t.world.me):
            dist = t.dist_to(pos)
            if not any(dist.get(p, 99) <= KILL_REACH for p in ours):
                continue
        bonus = t.values[b.id] if b else 0.0
        if FORECAST_KILL and pos in t.flag_dst:  # 예측한 도착 칸에서 잡는다
            pos = t.flag_dst[pos]
        need = t.threat.get(pos, 0) + 1
        if ASSASSIN_COND and need == 1 and assassin_signal(t, pos, n, bonus):  # 무방비한 깃발병은 가장 가까운 한 명이
            tasks.append(Task("암살", "W", pos, 1, (KILL_VALUE * n + bonus) * ASSASSIN_BOOST))
            continue
        tasks.append(Task("처치", "W", pos, need, KILL_VALUE * n + bonus))
    if INTERCEPT_VALUE > 0:
        for flag, b in intercept_targets(t).items():
            if b.owner == t.world.me and b.pos not in t.enemy_flags:
                need = raid_need(t, flag, b) if INTERCEPT_ESCORT else t.threat.get(b.pos, 0) + 1
                tasks.append(Task("요격", "W", b.pos, need, t.values[b.id] * INTERCEPT_VALUE))
    return tasks


def raid_need(t: Turn, flag: Pos, b: Building) -> int:
    """적 깃발병 `flag`가 노리는 우리 건물 `b`를 지킬 전투병: max(그 칸 다음 턴 위협, 깃발병 칸과 이웃의 적 전투병) + 1.
    그 칸 위협만 세면 아직 멀리 있는 기습조(깃발병 + 호위)에 한 명만 보내, 도착해서 상쇄로 지고 건물을 내준다."""
    escort = sum(n for p, n in t.enemy_warriors if manhattan(p, flag) <= 1)
    return max(t.threat.get(b.pos, 0), escort) + 1


def intercept_targets(t: Turn) -> dict[Pos, Building]:
    """적 깃발병마다 갈 것 같은 건물: 상대 것이 아닌 건물 중 걸어서 가장 가까운 것(INTERCEPT_RADIUS걸음 안, 동점이면
    정규화 좌표 순). 이미 건물 위에 선 깃발병은 그 건물을 점령 중이므로 뺀다."""
    if hasattr(t, "_intercept"):
        return t._intercept
    world = t.world
    cands = [b for b in sorted(world.buildings.values(), key=lambda b: t.key(b.pos)) if b.owner != world.enemy]
    found = {}
    for pos in t.enemy_flags:
        if world.building_at(pos):
            continue
        best = min(((t.dist_to(b.pos).get(pos, 99), i) for i, b in enumerate(cands)), default=None)
        if best and best[0] <= INTERCEPT_RADIUS:
            found[pos] = cands[best[1]]
    t._intercept = found
    return found


def trade_weighted(t: Turn, tasks: list[Task]) -> list[Task]:
    """비용 교환: 우리 전투병 값이 상대보다 싸면 TRADE_KINDS 과제 가치 × TRADE_BOOST, 비싸면 ÷ TRADE_BOOST."""
    if TRADE_BOOST == 1.0:
        return tasks
    world = t.world
    ours, theirs = world.warrior_cost(world.me), world.warrior_cost(world.enemy)
    if ours == theirs:
        return tasks
    factor = TRADE_BOOST if ours < theirs else 1 / TRADE_BOOST
    return [replace(task, value=task.value * factor) if task.kind in TRADE_KINDS else task for task in tasks]


def cheaper(t: Turn) -> bool:
    """우리 전투병 값이 상대보다 싼가 (공학관 차이)."""
    return t.world.warrior_cost(t.world.me) < t.world.warrior_cost(t.world.enemy)


def hunt_tasks(t: Turn) -> list[Task]:
    """소모전(TRADE_HUNT > 0, 우리 값이 더 쌀 때): 적 전투병이 TRADE_HUNT_MIN명 이상 선 칸에 그 칸 다음 턴 위협만큼."""
    if TRADE_HUNT <= 0 or not cheaper(t):
        return []
    world = t.world
    ours, theirs = world.warrior_cost(world.me), world.warrior_cost(world.enemy)
    gain = (theirs - ours) / ours
    return [Task("소모전", "W", pos, max(n, t.threat.get(pos, 0)), TRADE_HUNT * n * gain)
            for pos, n in t.enemy_warriors if n >= TRADE_HUNT_MIN]


def escort_tasks(t: Turn) -> list[Task]:
    """호위: 이번 턴 점령 중인 우리 깃발병. 같은 수만 있어도 상쇄되어 깃발병이 산다.
    ESCORT_VALUE > 0이면 나머지 우리 깃발병(이동 중·대기 중)에도 전투병 1명씩."""
    tasks = []
    for c in t.capturing_now:
        b = c.building
        if t.threat.get(b.pos, 0) and b.pos not in t.enemy_flags:
            tasks.append(Task("호위", "W", b.pos, t.threat[b.pos], t.values[b.id]))
    if ESCORT_VALUE <= 0:
        return tasks
    covered = {task.pos for task in tasks}
    if not (SH_ESCORT or ESCORT_LEAD or ESCORT_ADAPTIVE):  # 이동 중 깃발병: 위 호위 과제가 없는 칸마다 전투병 1명
        return tasks + [Task("호위", "W", pos, ESCORT_NEED, ESCORT_VALUE) for pos, _ in t.flags if pos not in covered]
    size = escort_size(t.world.turn) if SH_ESCORT else ESCORT_NEED
    if not size:
        return tasks
    for pos, task in assign_flags(t.flags, t.f_tasks, t.dist_to, t.deadline):
        cell = (step_along(pos, t.dist_to(task.pos), t.order) or task.pos) if ESCORT_LEAD else pos
        if cell in covered:
            continue
        need = min(ESCORT_MAX, max(ESCORT_MIN, t.threat.get(cell, 0) + 1)) if ESCORT_ADAPTIVE else size
        tasks.append(Task("호위", "W", cell, need, ESCORT_VALUE))
        covered.add(cell)
    return tasks


def escort_size(turn: int) -> int:
    """SH_ESCORT: 이 턴의 이동 중 호위 인원 (20·40·80턴 경계)."""
    if turn < 20:
        return SH_ESCORT_T0
    if turn < 40:
        return SH_ESCORT_T1
    if turn < 80:
        return SH_ESCORT_T2
    return SH_ESCORT_T3


def guard_tasks(t: Turn, weight: float) -> list[Task]:
    """지키기: 적 깃발병이 다가오는 우리 건물 위에 전투병을 세운다(가치 × weight). 올라오는 적 깃발병을
    그 칸에서 잡는다."""
    tasks = [Task("지키기", "W", b.pos, defend_need(t, b), t.values[b.id] * weight) for b, _ in t.pressured]
    return tasks + early_guard_tasks(t, weight)


def early_guard_tasks(t: Turn, weight: float) -> list[Task]:
    """선제 수비(EARLY_GUARD > 0): 적 깃발병이 GUARD_RADIUS보다 멀고 EARLY_GUARD걸음 안인 우리 건물 중, 우리 전투병이
    가장 가까운 적 깃발병보다 EARLY_SLACK턴 이상 먼저 닿지 못하는 곳에 전투병을 미리 세운다(가치 × weight × EARLY_GUARD_WEIGHT).
    지키기(적 깃발병 GUARD_RADIUS 안)가 이미 있는 건물은 뺀다."""
    if EARLY_GUARD <= 0 or not t.enemy_flags:
        return []
    world = t.world
    guarded = {b.id for b, _ in t.pressured}
    ours = [p for p, _ in world.units_of(world.me, "W")]
    tasks = []
    for b in world.owned(world.me):
        if b.id in guarded:
            continue
        dist = t.dist_to(b.pos)
        near = min(((dist[p], t.key(p), p) for p in t.enemy_flags if p in dist), default=None)
        if near is None or near[0] > EARLY_GUARD:
            continue
        mine = min((dist[p] for p in ours if p in dist), default=99)
        if mine + EARLY_SLACK <= near[0]:  # 우리가 넉넉히 먼저 닿는다 → 아직 과제로 묶지 않는다
            continue
        tasks.append(Task("선제 수비", "W", b.pos, raid_need(t, near[2], b), t.values[b.id] * weight * EARLY_GUARD_WEIGHT))
    return tasks


def defend_need(t: Turn, b: Building) -> int:
    """우리 건물 `b`를 지키는 데 필요한 전투병: 다음 턴 위협 + 1. 경제 건물은 ECON_DEFEND_REACH걸음 안의 적 전투병이
    더 많으면 그것 + 1, 그리고 DEFEND_MARGIN명을 더한다."""
    near = 0
    econ = b.kind in ECON_KINDS
    if econ and ECON_DEFEND_REACH > 1:
        dist = t.dist_to(b.pos)
        near = sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= ECON_DEFEND_REACH)
    return max(t.threat.get(b.pos, 0), near) + 1 + (int(DEFEND_MARGIN) if econ else 0)


def evict_tasks(t: Turn) -> list[Task]:
    """몰아내기: 적 전투병이 EVICT_RADIUS 안에 온 우리 핵심 건물(EVICT_KINDS) 위에 전투병을 세운다. 건물 위의 적
    전투병은 이겨서 몰아내고, 옆의 적은 올라오지 못하게 한다. 지키기 과제가 이미 있는 건물은 뺀다.
    ENG_WATCH_UNTIL턴까지 우리 공학관은 ENG_WATCH_REACH걸음 안의 적 전투병부터 보고, 그 수 + 1명을 세운다.
    ECON_GARRISON > 0이면 지키기·몰아내기가 없는 우리 경제 건물에 상주 과제(전투병 ECON_GARRISON명)를 더한다."""
    guarded = {b.id for b, _ in t.pressured}
    watch = ENG_WATCH_REACH > 0 and t.world.turn <= ENG_WATCH_UNTIL
    tasks = []
    quiet = []  # 몰아내기가 필요 없는 경제 건물 (상주 후보)
    for b in t.world.owned(t.world.me):
        if b.kind not in EVICT_KINDS or b.id in guarded:
            continue
        econ = b.kind in ECON_KINDS
        radius = ECON_EVICT_RADIUS if econ else EVICT_RADIUS
        weight = EVICT_WEIGHT * (ECON_WEIGHT if econ else 1.0)
        dist = t.dist_to(b.pos)
        need = defend_need(t, b)
        if watch and b.kind == "ENG":
            radius = max(radius, ENG_WATCH_REACH)
            need = max(need, sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= ENG_WATCH_REACH) + 1)
        if any(dist.get(p, 99) <= radius for p, _ in t.enemy_warriors):
            tasks.append(Task("몰아내기", "W", b.pos, need, t.values[b.id] * weight))
        elif econ:
            quiet.append(b)
    if ECON_GARRISON > 0:
        tasks += [Task("상주", "W", b.pos, int(ECON_GARRISON), GARRISON_VALUE) for b in quiet]
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


def rush_tasks(t: Turn) -> list[Task]:
    """공학관 러시: RUSH_UNTIL턴까지 상대 캠퍼스 쪽 공학관(우리 것이 아닌 것)에 전투병 "위협 + RUSH_EXTRA"명."""
    world = t.world
    if world.turn > RUSH_UNTIL or not own_eng_safe(t):
        return []
    home, away = world.map.bases[world.me], world.map.bases[world.enemy]
    tasks = []
    for b in t.others:
        dist = t.dist_to(b.pos)
        if b.kind == "ENG" and dist.get(away, 99) < dist.get(home, 99):
            tasks.append(Task("러시", "W", b.pos, attack_need(t, b, RUSH_EXTRA), RUSH_VALUE))
    return tasks


def sweep_tasks(t: Turn) -> list[Task]:
    """소탕: 남은 상대 건물마다 전투병 "위협 + SWEEP_EXTRA"명. 필요 인원이 적은 건물부터 넣고, 합이 우리 전투병 × SWEEP_FRAC를
    넘게 되는 건물은 뺀다(채우지 못하는 건물을 치면 전투병만 잃는다)."""
    world = t.world
    my_w = sum(n for _, n in world.units_of(world.me, "W"))
    cands = sorted(((attack_need(t, b, SWEEP_EXTRA), -t.values[b.id], t.key(b.pos), b) for b in world.owned(world.enemy)),
                   key=lambda c: c[:3])
    used, tasks = 0, []
    for need, _, _, b in cands:
        if used + need > my_w * SWEEP_FRAC:
            continue
        used += need
        tasks.append(Task("소탕", "W", b.pos, need, t.values[b.id] * SWEEP_WEIGHT))
    return tasks


def attack_need(t: Turn, b: Building, extra: int) -> int:
    """상대 건물 `b`에 들어갈 전투병 수: 그 칸 위협 + `extra`. ATTACK_TIE가 켜져 있고 우리 깃발병이 ATTACK_TIE걸음 안에
    있으면 위협만큼(최소 1): 동수면 서로 상쇄되어 남은 전투병이 없으므로 따라 들어간 우리 깃발병이 살아남아 중립화한다."""
    threat = t.threat.get(b.pos, 0)
    if TRADE_TIE and cheaper(t):
        return max(1, threat)
    if ATTACK_TIE > 0:
        dist = t.dist_to(b.pos)
        if any(dist.get(p, 99) <= ATTACK_TIE for p, _ in t.flags):
            return max(1, threat)
    return threat + extra


def own_eng_safe(t: Turn) -> bool:
    """러시를 내도 되는가: 우리 공학관마다 RUSH_SAFE_REACH걸음 안의 적 전투병 ≤ 우리 전투병 + RUSH_SAFE_MARGIN.
    우리 공학관이 없으면(아직 못 먹었거나 잃었으면) 지킬 것이 없으므로 참. RUSH_SAFE_REACH가 0이면 늘 참."""
    if RUSH_SAFE_REACH <= 0:
        return True
    world = t.world
    ours = world.units_of(world.me, "W")
    for b in world.owned(world.me):
        if b.kind != "ENG":
            continue
        dist = t.dist_to(b.pos)
        enemy = sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= RUSH_SAFE_REACH)
        mine = sum(n for p, n in ours if dist.get(p, 99) <= RUSH_SAFE_REACH)
        if enemy > mine + RUSH_SAFE_MARGIN:
            return False
    return True


def squad_tasks(t: Turn) -> list[Task]:
    """별동대: 위험한 목표(상대 소유이거나 적 전투병이 닿는 건물)로 가는 깃발병을 과제 가치 순(동점이면 정규화 좌표 순)으로,
    목표 건물이 겹치지 않게 1명(SECOND_SQUAD_TURN부터 2명) 골라, 그 깃발병이 이번 턴 들어갈 칸(목표 쪽 한 칸, 목표 위면
    목표)에 전투병 SQUAD_SIZE명을 보낸다(점령 과제 가치 × SQUAD_WEIGHT). 전투병이 그 칸을 먼저 차지하므로 깃발병의 안전
    판단(적 위협 ≤ 우리 전투병)이 통과되어 가는 길에서도 함께 움직인다. 깃발병 배정은 깃발병 1차와 같은 입력으로 다시 구한다."""
    world = t.world
    count = 2 if world.turn >= SECOND_SQUAD_TURN else 1
    cands = []
    for pos, task in assign_flags(t.flags, t.f_tasks, t.dist_to, t.deadline):
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


def squad_size(t: Turn, cell: Pos) -> int:
    """별동대 인원. SQUAD_FLEX면 그 칸을 노리는 적(다음 턴 위협, SQUAD_REACH걸음 안 적 전투병 중 큰 쪽) + 1을 SQUAD_MIN~SQUAD_MAX로
    자른다. 아니면 SQUAD_SIZE 고정."""
    if not SQUAD_FLEX:
        return SQUAD_SIZE
    reach = t.dist_to(cell)
    near = sum(n for p, n in t.enemy_warriors if reach.get(p, 99) <= SQUAD_REACH)
    return max(SQUAD_MIN, min(SQUAD_MAX, max(t.threat.get(cell, 0), near) + 1))


def assassin_signal(t: Turn, cell: Pos, n: int, bonus: float) -> bool:
    """무방비한 적 깃발병(`cell`)을 우리 전투병 한 명이 혼자 잡을 만한가 (ASSASSIN_COND)."""
    if any(manhattan(cell, p) <= ASSASSIN_GUARD_R for p, _ in t.enemy_warriors):
        return False
    dist = t.dist_to(cell)
    near = min((dist.get(p, 99) for p, _ in t.world.units_of(t.world.me, "W")), default=99)
    if near > ASSASSIN_MAX_DIST:
        return False
    return (KILL_VALUE * n + bonus + ASSASSIN_EXTRA * n) / (1 + near) >= ASSASSIN_SIGNAL


def enemy_defenders(t: Turn, b: Building) -> int:
    """건물 `b` 주변 DIVERSION_REACH걸음 안의 적 전투병 수."""
    dist = t.dist_to(b.pos)
    return sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= DIVERSION_REACH)


def diversion_aggro(t: Turn, b: Building) -> int:
    """건물 `b`를 건드리면 달려올 적 전투병: DIVERSION_AGGRO_MIN_DIST~MAX_DIST걸음 사이."""
    dist = t.dist_to(b.pos)
    return sum(n for p, n in t.enemy_warriors if DIVERSION_AGGRO_MIN_DIST <= dist.get(p, 99) <= DIVERSION_AGGRO_MAX_DIST)


def diversion_signal(t: Turn, b: Building, defenders: int, nearest: int) -> float:
    """양동 신호 S (DIVERSION_COND). 가치가 크고 수비가 약하고 가까울수록, 건드리면 달려올 적이 많을수록 크다."""
    prio = DIVERSION_PRIORITY if b.kind in DIVERSION_PRIORITY_KINDS else 1.0
    return t.values[b.id] * prio / (1 + defenders) / (2 + nearest) * (1 + min(diversion_aggro(t, b), 12) / 12)


def diversion_start(t: Turn, b: Building, defenders: int, nearest: int, ratio: float) -> bool:
    """이 건물로 양동을 새로 시작해도 되는가. DIVERSION_COND가 꺼져 있으면 늘 참."""
    if not DIVERSION_COND:
        return True
    signal = diversion_signal(t, b, defenders, nearest)
    tight = DIVERSION_TIGHT_LO <= ratio <= DIVERSION_TIGHT_HI
    easy = defenders <= DIVERSION_EASY_DEF and diversion_aggro(t, b) >= DIVERSION_AGGRO_MIN
    if not ((tight and signal >= DIVERSION_SIGNAL_TIGHT) or (easy and signal >= DIVERSION_SIGNAL_EASY)):
        return False
    if DIVERSION_EV:
        p, ev = diversion_ev(t, b)
        return p >= DIVERSION_P_MIN and ev >= DIVERSION_EV_MIN
    return True


def home_depth(t: Turn, b: Building) -> int:
    """건물 `b`가 우리 진영 안쪽으로 얼마나 깊은가 = (상대 본진까지 걸음) − (우리 본진까지 걸음). 클수록 상대에게서 멀다."""
    world = t.world
    dist = t.dist_to(b.pos)
    return dist.get(world.map.bases[world.enemy], 99) - dist.get(world.map.bases[world.me], 99)


def diversion_ev(t: Turn, b: Building) -> tuple[float, float]:
    """양동의 (성공 확률 p, 기대값 EV) — DIVERSION_EV 설명."""
    world = t.world
    dist = t.dist_to(b.pos)
    support = sum(n for p, n in world.units_of(world.me, "W") if dist.get(p, 99) <= DIVERSION_FRONT_REACH)
    rival = sum(n for p, n in t.enemy_warriors if dist.get(p, 99) <= DIVERSION_RIVAL_REACH)
    p = support / (support + rival) if support + rival else 1.0
    need = max(2, min(DIVERSION_MAX, max(t.threat.get(b.pos, 0), enemy_defenders(t, b)) + DIVERSION_EXTRA))
    prio = DIVERSION_PRIORITY if b.kind in DIVERSION_PRIORITY_KINDS else 1.0
    return p, p * t.values[b.id] * prio - (1 - p) * need * DIVERSION_LOSS_PER_W


def rush_target(t: Turn, b: Building) -> bool:
    """러시가 이미 노리는 건물(RUSH_UNTIL턴까지 상대 캠퍼스 쪽 공학관)인가."""
    world = t.world
    if b.kind != "ENG" or world.turn > RUSH_UNTIL:
        return False
    dist = t.dist_to(b.pos)
    return dist.get(world.map.bases[world.enemy], 99) < dist.get(world.map.bases[world.me], 99)


def diversion_target(t: Turn) -> Building | None:
    """양동 목표. 후보 = 우리 것이 아니고 러시가 노리지 않는 건물 중, 수비 ≤ DIVERSION_MAX_DEF, 우리 전투병 DIVERSION_FRONT_REACH걸음 안
    DIVERSION_MIN_SUPPORT명 이상. 신호가 큰 곳을 고르고, 이미 고른 목표는 조건이 유지되는 동안 잡되 DIVERSION_PATIENCE턴 진전(소유자
    변화)이 없으면 DIVERSION_COOLDOWN턴 접는다. 우리 전투병이 적의 DIVERSION_MIN_RATIO배 미만이면 하지 않는다."""
    world = t.world
    st = _diversion
    if not DIVERSION_FROM or not DIVERSION_FROM <= world.turn <= DIVERSION_UNTIL:
        return None
    mine = world.units_of(world.me, "W")
    mine_n, theirs_n = sum(n for _, n in mine), sum(n for _, n in t.enemy_warriors)
    if mine_n < DIVERSION_MIN_RATIO * theirs_n:
        st["target"] = None
        return None
    cands = []
    for b in sorted(world.buildings.values(), key=lambda b: t.key(b.pos)):
        if b.owner == world.me or rush_target(t, b) or st["banned"].get(b.id, 0) > world.turn:
            continue
        if DIVERSION_SKIP_HOME and MOBILE_DEPTH and home_depth(t, b) >= MOBILE_DEPTH:
            continue  # 우리 진영 깊은 곳 건물을 되찾는 것은 양동이 아니다
        dist = t.dist_to(b.pos)
        if sum(n for p, n in mine if dist.get(p, 99) <= DIVERSION_FRONT_REACH) < DIVERSION_MIN_SUPPORT:
            continue
        nearest = min((dist.get(p, 99) for p, _ in mine), default=99)
        cands.append((enemy_defenders(t, b), nearest, b))
    ratio = mine_n / max(1, theirs_n)
    keep = st["target"]
    if keep is not None:
        for d, near, b in cands:
            if b.id == keep and d <= DIVERSION_MAX_DEF + 1 and (
                    not DIVERSION_COND or diversion_signal(t, b, d, near) >= DIVERSION_SIGNAL_KEEP) and (
                    not DIVERSION_EV or diversion_ev(t, b)[1] >= DIVERSION_EV_KEEP):
                if b.owner != st["owner"]:
                    st.update(since=world.turn, owner=b.owner)  # 소유자가 바뀌었다 = 진전
                elif world.turn - st["since"] >= DIVERSION_PATIENCE:
                    st["banned"][b.id] = world.turn + DIVERSION_COOLDOWN
                    st["target"] = None
                    break
                return b
        else:
            st["target"] = None
    opened = [(-diversion_signal(t, b, d, near), t.key(b.pos), b) for d, near, b in cands
              if d <= DIVERSION_MAX_DEF and b.id != st["target"] and diversion_start(t, b, d, near, ratio)]
    if not opened:
        return None
    target = min(opened, key=lambda c: c[:2])[2]
    st.update(target=target.id, since=world.turn, owner=target.owner)
    return target


def diversion_tasks(t: Turn) -> list[Task]:
    """양동 과제: 목표 건물에 전투병 (수비 + DIVERSION_EXTRA)명(2~DIVERSION_MAX). 깃발병은 점령 가치 배율로 따라온다."""
    b = t.diversion
    if b is None:
        return []
    need = max(2, min(DIVERSION_MAX, max(t.threat.get(b.pos, 0), enemy_defenders(t, b)) + DIVERSION_EXTRA))
    return [Task("양동", "W", b.pos, need, DIVERSION_VALUE)]


def mobile_tasks(t: Turn) -> list[Task]:
    """기동대 (MOBILE 설명)."""
    if not MOBILE:
        return []
    world = t.world
    away = world.map.bases[world.enemy]
    tasks = []
    for b in sorted(world.buildings.values(), key=lambda b: t.key(b.pos)):
        turns = _lost["turns"].get(b.id)
        if not turns:
            continue
        if MOBILE_DEPTH:
            if home_depth(t, b) < MOBILE_DEPTH:
                continue
        elif t.dist_to(b.pos).get(away, 0) < MOBILE_ENEMY_DIST:
            continue
        recent = [x for x in turns if world.turn - x <= MOBILE_WINDOW]
        if len(recent) >= MOBILE_FLIPS and world.turn - turns[-1] <= MOBILE_CALM:
            tasks.append(Task("기동대", "W", b.pos, MOBILE_SIZE, t.values[b.id] * MOBILE_WEIGHT))
    return tasks


def hunters_update(world: World) -> None:
    """사냥꾼이 살아 있는지 본다: 기억한 칸마다 우리 전투병 수와 견줘 줄었으면 죽은 것으로 센다(유닛에 ID가 없어 칸으로 추적)."""
    h = _hunters
    if not HUNTERS or not h["cells"]:
        return
    alive = dict(world.units_of(world.me, "W"))
    for pos, n in list(h["cells"].items()):
        have = min(n, alive.get(pos, 0))
        if have < n:
            h["deaths"] += n - have
        if have:
            h["cells"][pos] = have
        else:
            del h["cells"][pos]


def hunters_plan(t: Turn, warriors: list[tuple[Pos, int]]) -> list[tuple[Pos, int]]:
    """사냥꾼 조를 전투병 풀에서 빼고 이번 턴 움직임을 정한다. 형성 기간에는 새로 만든 전투병을 뽑아 생산 칸에서 모은다."""
    h, world = _hunters, t.world
    if world.turn <= HUNTERS_FORM_UNTIL and h["designated"] < HUNTERS_SIZE and t.make_w:
        take = min(t.make_w, HUNTERS_SIZE - h["designated"])
        h["cells"][t.w_site] += take
        h["designated"] += take
    if not h["cells"]:
        return warriors
    pool = Counter(dict(warriors))
    total = sum(h["cells"].values())
    if not h["formed"] and total < HUNTERS_SIZE and world.turn < HUNTERS_FORM_UNTIL:
        for pos, n in h["cells"].items():  # 아직 모으는 중: 제자리
            pool[pos] -= n
        t.hunter_stay = dict(h["cells"])
        return sorted(((p, n) for p, n in pool.items() if n > 0), key=lambda item: t.key(item[0]))
    h["formed"] = True
    pos, n = max(h["cells"].items(), key=lambda kv: kv[1])  # 흩어졌으면 가장 큰 무리만 남긴다
    h["cells"] = Counter({pos: n})
    pool[pos] -= n
    dst = hunters_step(t, pos, n)
    h["cells"] = Counter({dst: n})
    t.hunter_move = (pos, dst, n)
    return sorted(((p, m) for p, m in pool.items() if m > 0), key=lambda item: t.key(item[0]))


def hunters_step(t: Turn, pos: Pos, n: int) -> Pos:
    """사냥꾼 무리(`n`명)의 다음 칸(제자리 포함). 죽지 않는 것이 먼저: 적 위협이 n − HUNTERS_MARGIN 이하인 칸만 밟는다."""
    world = t.world
    x, y = pos
    cells = [pos] + [(x + dx, y + dy) for dx, dy in t.order if world.map.passable((x + dx, y + dy))]
    home = t.dist_to(world.map.bases[world.me])
    safe = [c for c in cells if t.threat.get(c, 0) <= n - HUNTERS_MARGIN]
    if not safe:  # 어디든 위험하면 위협이 가장 낮은 칸, 같으면 우리 본진 쪽
        return min(cells, key=lambda c: (t.threat.get(c, 0), home.get(c, 99), c != pos))
    # 1) 무방비한 적 깃발병
    free = []
    for fp, fn in t.enemy_flags.items():
        if any(manhattan(fp, p) <= HUNTERS_GUARD_R for p, _ in t.enemy_warriors) or t.threat.get(fp, 0) > n - HUNTERS_MARGIN:
            continue
        d = t.dist_to(fp).get(pos)
        if d is None:
            continue
        b = world.building_at(fp)
        free.append((-((t.values[b.id] if b else 0.0) + 1.0 + HUNTERS_FLAG_EXTRA) * fn / (1 + d), t.key(fp), fp))
    if free:
        dist = t.dist_to(min(free)[2])
        return min(safe, key=lambda c: (dist.get(c, 99), c != pos, t.key(c)))
    # 2) 미끼: 양동 목표의 수비대, 없으면 상대 공학관·학생회관 근처를 지키는 무리
    anchors = [t.diversion.pos] if t.diversion is not None else [
        b.pos for b in world.buildings.values() if b.kind in ("ENG", "HALL") and b.owner != world.me
        and home_depth(t, b) < MOBILE_DEPTH]
    best = None
    for sp, m in t.enemy_warriors:
        near_anchor = any(manhattan(sp, a) <= 3 for a in anchors)
        d = t.dist_to(sp).get(pos)
        if d is None:
            continue
        score = m * (3 if near_anchor else 1) / (1 + d)
        if best is None or score > best[0]:
            best = (score, sp)
    if best is None:
        return pos
    dist = t.dist_to(best[1])
    return min(safe, key=lambda c: (abs(dist.get(c, 99) - HUNTERS_KITE), c != pos, t.key(c)))


def recently_lost(t: Turn, b: Building) -> bool:
    """우리 것이 아닌 건물 `b`(RETAKE_KINDS, 기본 공학관)를 최근 RETAKE_MEMORY턴 안에 우리가 가지고 있었는가."""
    last = _last_owned.get(b.id)
    return (b.kind in RETAKE_KINDS and b.owner != t.world.me and last is not None
            and t.world.turn - last <= RETAKE_MEMORY)


def retake_tasks(t: Turn) -> list[Task]:
    """탈환: 최근 잃은 우리 공학관 칸에 전투병 "위협 + RETAKE_EXTRA"명 (RETAKE_VALUE > 0일 때). 중립화된 턴에 가면 상대
    깃발병이 점령을 마치기 전에 그 칸에서 잡고, 이미 빼앗겼으면 깃발을 뽑아 우리 깃발병이 되찾게 한다."""
    if RETAKE_VALUE <= 0:
        return []
    return [Task("탈환", "W", b.pos, t.threat.get(b.pos, 0) + RETAKE_EXTRA, RETAKE_VALUE)
            for b in t.others if recently_lost(t, b)]


def eng_focus_tasks(t: Turn) -> list[Task]:
    """공학관 집중(열세 국면): 우리 것이 아닌 공학관 전부에 전투병 "위협 + DEFICIT_EXTRA"명. 어느 쪽이든 하나를 먹으면 된다
    — 배정은 가치 / (1 + 가장 먼 전투병 거리)라 적이 덜 지키고 가까운 쪽이 먼저 찬다."""
    return [Task("공학관 집중", "W", b.pos, t.threat.get(b.pos, 0) + DEFICIT_EXTRA, DEFICIT_VALUE)
            for b in t.others if b.kind == "ENG"]


def final_capture_tasks(t: Turn, danger: float) -> list[Task]:
    """막판 점령: 160턴 순간의 점수만 센다. 중립은 점령 1단계로 + 점수, 상대 건물은 중립화 1단계로 상대 점수 − (× 2로 셈).
    끝낼 수 없는 짝은 assign_flags가 t.deadline으로 뺀다."""
    tasks = []
    arrival = getattr(t, "arrival", {})
    for b in t.targets:
        covered = b.id in t.pulled or b.pos in arrival
        value = (estimated_score(t.world, b) * (2.0 if b.owner is not None else 1.0)
                 * (danger if t.threat.get(b.pos, 0) and not covered else 1.0))
        tasks.append(Task("막판 점령", "F", b.pos, 1, value, b, 1))
    return tasks


def final_guard_tasks(t: Turn) -> list[Task]:
    """막판 수비: 남은 턴 안에 적 깃발병이 닿을 수 있는 우리 건물마다 전투병 "위협 + 1"명 (가치 = 점수 × FINAL_GUARD_WEIGHT).
    160턴 뒤 전투병은 동점일 때만 세므로 아끼지 않는다."""
    if FINAL_GUARD_WEIGHT <= 0:
        return []
    left = TOTAL_TURNS - t.world.turn
    tasks = []
    for b in t.world.owned(t.world.me):
        dist = t.dist_to(b.pos)
        if any(dist.get(p, 99) <= left + 1 for p in t.enemy_flags):
            tasks.append(Task("막판 수비", "W", b.pos, t.threat.get(b.pos, 0) + 1,
                              estimated_score(t.world, b) * FINAL_GUARD_WEIGHT))
    return tasks


def picket_tasks(t: Turn) -> list[Task]:
    """초소: 상대 건물마다(적 깃발병이 선 곳은 처치 과제가 맡으므로 뺀다) 전투병 1명 (PICKET_VALUE > 0일 때)."""
    if PICKET_VALUE <= 0:
        return []
    return [Task("초소", "W", b.pos, PICKET_NEED, PICKET_VALUE) for b in t.others
            if b.owner == t.world.enemy and b.pos not in t.enemy_flags]


def raid_tasks(t: Turn, weight: float) -> list[Task]:
    """급습: 상대 공학관·학생회관(RAID_KINDS) 위에 전투병을 "그 칸 위협 + 1"명 보낸다(가치 × weight). 전투병이 서면
    깃발병이 위험 할인 없이 뒤따라 중립화 → 점령한다. 우리 전투병이 적 + RAID_SURPLUS보다 적으면 하지 않는다."""
    world = t.world
    if sum(n for _, n in world.units_of(world.me, "W")) < sum(n for _, n in t.enemy_warriors) + RAID_SURPLUS:
        return []
    their_stations = len(world.owned(world.enemy, "STATION"))
    station_raid = their_stations == 2 if STATION_RAID == 2 else (STATION_RAID and their_stations >= 2)
    kinds = RAID_KINDS | ({"STATION"} if station_raid else set())
    return [Task("급습", "W", b.pos, attack_need(t, b, 1), t.values[b.id] * weight)
            for b in sorted(world.owned(world.enemy), key=lambda b: t.key(b.pos)) if b.kind in kinds]


# ------------------------------------------------------------------ 깃발병


def assign_flags(
    flags: list[tuple[Pos, int]], tasks: list[Task], dist_to: Callable[[Pos], dict[Pos, int]],
    deadline: int | None = None,
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
        if d is None:
            return None
        if deadline is not None and max(d - 1, 0) + task.stages - 1 > deadline:  # 막판: 160턴 전에 못 끝냄
            return None
        keep = FLAG_INERTIA if task.pos in _flag_goal.get(pos, ()) else 1.0  # 지난 턴 이 칸 깃발병의 목표
        return keep * task.value / (d + task.stages + ETA_OFFSET)

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
        safe: Callable[[Pos], bool], hold: bool, ahead: Callable[[Pos], bool] | None = None,
        margin: Callable[[Pos], int] | None = None,
    ) -> None:
        self.pos, self.goal, self.dist, self.safe, self.hold = pos, goal, dist, safe, hold
        self.ahead = ahead or safe  # 목표 쪽으로 나아갈 칸의 판단 (기본 = 안전)
        self.margin = margin  # 칸의 열세 (FLAG_ESCAPE)
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

    def escape(self) -> bool:
        """FLAG_ESCAPE: 포위됐을 때 열세가 가장 작은 칸으로 (같으면 목표에 가까운 칸, 2면 제자리도 후보). 제자리를 고르면 step = None."""
        if not FLAG_ESCAPE or self.margin is None:
            return False
        cands = [n for n in self.neighbors if self.enterable(n)] + ([self.pos] if FLAG_ESCAPE == 2 else [])
        if not cands:
            return False
        best = min(cands, key=lambda n: (self.margin(n), self.dist[n]))
        forward = next((n for n in self.closer if self.enterable(n)), None)
        if forward is not None and self.margin(forward) - self.margin(best) < FLAG_ESCAPE_GAIN:
            best = forward  # 목표 쪽 칸보다 열세가 FLAG_ESCAPE_GAIN 이상 줄지 않으면 그대로 나아간다
        self.step = None if best == self.pos else best
        return True


def flag_step(
    pos: Pos,
    goal: Pos,
    dist: dict[Pos, int],
    order: tuple[Pos, ...],
    safe: Callable[[Pos], bool],
    hold: bool,
    ahead: Callable[[Pos], bool] | None = None,
    margin: Callable[[Pos], int] | None = None,
) -> Pos | None:
    """깃발병 한 명의 다음 칸 (None = 제자리). 판단은 FLAG_TREE:

    목표 쪽으로 한 칸 줄이는 칸 중 안전한 곳 → 없으면 지금 칸이 안전할 때 대기 → 아니면 안전한 이웃으로
    피한다 → 그것도 없으면 그냥 목표 쪽으로 간다. `hold`면 목표 칸에 들어가지 않고 앞에서 기다린다.
    """
    m = FlagMove(pos, goal, dist, order, safe, hold, ahead, margin)
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

    돌려주는 값: (전투병 칸, 목표 칸) 목록, 과제를 못 받은 전투병 칸 목록, 과제 칸 → 전원 도착까지 턴 수.

    전투병은 칸 단위 [칸, 인원]으로 다룬다. 한 명씩 펼쳐 정렬하면 전투병 수에 비례해 느려져, 9/28 22:00
    리더보드에서 전투병 540명일 때 서버 응답이 274 ms(제한 300 ms)까지 갔다. 같은 칸은 거리가 같으므로
    칸 순서로 동점을 가르면 한 명씩 고르던 때와 같은 전투병을 같은 순서로 고른다.
    """
    cells = [[pos, n] for pos, n in warriors if n > 0]
    plan: list[tuple[Pos, Pos]] = []
    arrival: dict[Pos, int] = {}
    remaining = list(tasks)
    opened: list[str] = []  # 연 과제 종류 (TASK_LIMIT)
    main_goals: list[Pos] = []  # 연 과제 중 깃발병 돕기가 아닌 것의 칸 (TASK_LIMIT 합류 목표)
    while remaining and cells:
        best: tuple[float, Task, list[tuple[int, int, int]]] | None = None
        full = TASK_LIMIT and sum(1 for k in opened if k not in FLAG_SUPPORT) >= TASK_LIMIT
        for task in remaining:
            if full and task.kind not in FLAG_SUPPORT:
                continue
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
            if SH_INERTIA and task.pos in sticky:  # 지난 턴에 맡던 과제는 SH_INERTIA칸 더 가깝다고 친다
                far = max(0, far - SH_INERTIA)
            score = task.value / (1 + far) ** DIST_POWER
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
        opened.append(task.kind)
        if task.kind not in FLAG_SUPPORT:
            main_goals.append(task.pos)
        remaining.remove(task)
    if TASK_LIMIT and TASK_MERGE and main_goals and cells:  # 남는 전투병은 고른 (깃발병 돕기가 아닌) 과제 중 가장 가까운 곳에 합류한다
        rest = []
        for pos, n in cells:
            near = min(main_goals, key=lambda goal: (dist_to(goal).get(pos, 10**6), goal))
            if pos in dist_to(near):
                plan += [(pos, near)] * n
            else:
                rest.append([pos, n])
        cells = rest
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
    """상대가 이번 턴 본진에서 새로 만들 수 있는 전투병 (생산한 유닛은 같은 턴에 바로 움직인다).
    HOSPITAL_THREAT면 상대 병원마다 같은 수를 더한다(어느 곳에서 만들지 모르므로 곳마다 최대)."""
    enemy = world.enemy
    n = world.gold[enemy] // world.warrior_cost(enemy)
    if not n:
        return []
    sites = [world.map.bases[enemy]]
    if HOSPITAL_THREAT:
        sites += [b.pos for b in world.owned(enemy, "HOSPITAL")]
    return [(pos, n) for pos in sites]


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
    step = world.turn // 5
    if b.kind == "HALL" and SH_HALL_DECAY:
        bonus = max(1.8, 3.6 - 0.2 * step) * HALL_VALUE_PER_TURN / HALL_VALUE_REF
    elif b.kind == "HALL":
        bonus = HALL_VALUE_PER_TURN * max(0, TOTAL_TURNS - world.turn)
    elif b.kind == "ENG" and SH_ENG_DECAY:
        bonus = max(2.0, 3.0 - 0.2 * step) * FUNCTION_VALUE["ENG"] / ENG_VALUE_REF
    elif b.kind == "DEPOT":
        bonus = 0.0 if b.id in _depots_taken else DEPOT_VALUE
    elif b.kind == "STATION" and SH_STATION:
        bonus = station_value(world, b)
    elif b.kind == "HOSPITAL" and HOSPITAL_ISOLATED > 0 and isolated_hospital(world, b):
        bonus = HOSPITAL_ISOLATED
    else:
        bonus = FUNCTION_VALUE.get(b.kind, 0.0)
    if b.kind == "STATION" and STATION_DENY > 0:
        bonus += station_deny(world, b)
    return score + bonus


def station_deny(world: World, b: Building) -> float:
    """역 차단(STATION_DENY): 상대 순간이동망(역 2개 이상)을 끊는 가치. 상대 역이 n개면 그 역마다 STATION_DENY / (n − 1),
    상대 역이 1개면 그 역과 STATION_MIN_LINK걸음 이상 떨어진 중립 역에 STATION_DENY × STATION_DENY_PRE."""
    theirs = [s for s in world.owned(world.enemy, "STATION")]
    if b.owner == world.enemy and len(theirs) >= 2:
        return STATION_DENY / (len(theirs) - 1)
    if (b.owner is None and STATION_DENY_PRE > 0 and len(theirs) == 1
            and manhattan(b.pos, theirs[0].pos) >= STATION_MIN_LINK):
        return STATION_DENY * STATION_DENY_PRE
    return 0.0


def station_value(world: World, b: Building) -> float:
    """역의 기능 가치(SH_STATION). 순간이동은 우리 역이 2개 이상이라야 열리므로, 쓸 만큼 떨어진(STATION_MIN_LINK걸음 이상)
    다른 역이 없으면 0, 그런 역 중 우리 것이 없으면 STATION_FIRST, 하나면 짝을 완성하므로 STATION_BASE + 가장 연계되는 역
    주변 가치, 둘 이상이면 STATION_EXTRA. 우리가 이미 가진 역에도 같은 값이 나온다(잃으면 짝이 깨진다)."""
    linked = [s for s in world.buildings.values()
              if s.kind == "STATION" and s.id != b.id and manhattan(b.pos, s.pos) >= STATION_MIN_LINK]
    if not linked:
        return 0.0
    mine = [s for s in linked if s.owner == world.me]
    if not mine:
        return STATION_FIRST
    if STATION_V3:  # 전진 거점(이 역 자신의 주변 포함) + 아끼는 걸음 + 근처 우리 경제 건물 수비
        dest = max([station_neighbors(world, b)] + [station_neighbors(world, s) for s in linked])
        span = max(manhattan(b.pos, s.pos) for s in linked)
        saved = STATION_LINK_GAIN * max(0, min(6, span - STATION_MIN_LINK)) / 6
        guard = STATION_DEFENSE * sum(1 for o in world.buildings.values()
                                      if o.owner == world.me and o.kind in ("ENG", "HALL")
                                      and manhattan(o.pos, b.pos) <= STATION_NEIGHBOR)
        return (STATION_EXTRA if len(mine) > 1 else STATION_BASE + dest) + saved + guard
    if len(mine) > 1:
        return STATION_EXTRA
    return STATION_BASE + max(station_neighbors(world, s) for s in linked)


def station_neighbors(world: World, s: Building) -> float:
    """역 `s` 주변 STATION_NEIGHBOR걸음 안의 건물 가치 합 (병원 제외 — 역이 있으면 병원을 쓸 이유가 없다)."""
    return sum(STATION_NEIGHBOR_VALUE.get(o.kind, 0.0) for o in world.buildings.values()
               if o.id != s.id and manhattan(o.pos, s.pos) <= STATION_NEIGHBOR)


def isolated_hospital(world: World, b: Building) -> bool:
    """본진에서도, 어느 역에서도 HOSPITAL_ALONE_DIST걸음 밖에 떨어진 병원인가."""
    if manhattan(b.pos, world.map.bases[world.me]) <= HOSPITAL_ALONE_DIST:
        return False
    return all(manhattan(b.pos, s.pos) > HOSPITAL_ALONE_DIST
               for s in world.buildings.values() if s.kind == "STATION")


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
    test = Condition(condition, lambda ctx: ctx.active.get(name, False))
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


def rush() -> Node:
    return enable("러시 과제: RUSH_UNTIL턴까지 상대 캠퍼스 공학관에 전투병", "W", rush_tasks)


def picket() -> Node:
    return enable("초소 과제: 상대 건물마다 전투병 1명 (PICKET_VALUE > 0일 때)", "W", picket_tasks)


def retake() -> Node:
    return enable(f"탈환 과제: {RETAKE_MEMORY}턴 안에 잃은 우리 공학관 (RETAKE_VALUE > 0일 때)", "W", retake_tasks)


def eng_focus() -> Node:
    def on(t: Turn) -> None:
        t.eng_focus = True
        t.makers["W"].append(eng_focus_tasks)
    return Act(f"공학관 집중 과제: 우리 것이 아닌 공학관에 전투병 위협 + {DEFICIT_EXTRA}, 점령 가치 ×{DEFICIT_CAPTURE:g}", on)


def final_capture(danger: float) -> Node:
    def on(t: Turn) -> None:
        t.deadline = TOTAL_TURNS - t.world.turn
        t.makers["F"].append(lambda t: final_capture_tasks(t, danger))
    return Act(f"막판 점령 과제: 160턴 전에 끝낼 수 있는 건물만, 최종 점수로 (적 전투병이 닿는 건물 ×{danger:g})", on)


def final_guard() -> Node:
    return enable(f"막판 수비 과제: 남은 턴 안에 적 깃발병이 닿는 우리 건물 (점수 ×{FINAL_GUARD_WEIGHT:g})", "W", final_guard_tasks)


def diversion() -> Node:
    def on(t: Turn) -> None:
        t.diversion_ok = True
        t.makers["W"].append(diversion_tasks)
    return Act("양동 과제: 전선 가까이 수비가 약한 건물 하나에 전투병 (DIVERSION_FROM > 0일 때)", on)


def sweep() -> Node:
    return enable("소탕 과제: 남은 상대 건물마다 전투병 위협 + SWEEP_EXTRA명 (SWEEP일 때)", "W", sweep_tasks)


def mobile() -> Node:
    return enable("기동대 과제: 우리 진영 깊은 곳 건물을 자주 잃으면 전담 전투병 (MOBILE일 때)", "W", mobile_tasks)


def warriors(extra: int) -> Node:
    return Act(f"전투병 목표 인원 = 적 전투병 + {extra}", lambda t: setattr(t, "extra_warriors", extra))


PHASE_TREE = Selector(
    "국면 선택 → 이번 턴 과제 구성 (위에서부터 처음 성립하는 가지)",
    phase_branch(
        "SWEEP", "우리 점수가 과반이고 상대 건물이 SWEEP_ENEMY_MAX곳 이하 (SWEEP일 때)",
        capture(steal=2.0, danger=0.8), kill(), escort(), guard(1.0), evict(), sweep(), retake(), warriors(1),
    ),
    phase_branch(
        "ENDGAME", "마지막 ENDGAME_TURNS턴 (ENDGAME_TURNS > 0일 때)",
        final_capture(danger=THREAT_DANGER), kill(), escort(), guard(THREAT_GUARD), evict(), final_guard(), frontline(1.0), raid(1.0), squad(), rush(), picket(), retake(), warriors(THREAT_EXTRA),
    ),
    phase_branch(
        "COMEBACK", "COMEBACK_TURN턴 뒤 추정 점수가 뒤짐 (COMEBACK_TURN > 0일 때)",
        capture(steal=2.0, danger=0.8), kill(), escort(), guard(1.0), evict(), frontline(0.5), raid(2.0), squad(), rush(), picket(), retake(), warriors(1),
    ),
    phase_branch(
        "BEHIND", "적 전투병 ≥ 우리 전투병 + BEHIND_MARGIN (BEHIND_MARGIN > 0일 때)",
        capture(steal=1.0, danger=0.3), kill(), escort(), guard(2.0), evict(), squad(), retake(), warriors(2),
    ),
    phase_branch(
        "THREAT", f"적 깃발병이 {GUARD_RADIUS}칸 안에 온 우리 건물의 추정 점수 합 ≥ {THREAT_PRESSURE:g}",
        capture(steal=1.0, danger=THREAT_DANGER), kill(), escort(), guard(THREAT_GUARD), evict(), frontline(1.0), raid(1.0), squad(), rush(), picket(), retake(), diversion(), mobile(), warriors(THREAT_EXTRA),
    ),
    phase_branch(
        "DEFICIT", "우리 전투병 값 > 상대 전투병 값 (공학관 열세, ENG_DEFICIT일 때)",
        capture(steal=1.5, danger=0.5), eng_focus(), kill(), escort(), guard(1.0), evict(), squad(), retake(), warriors(1),
    ),
    phase_branch(
        "HOLD", f"{LATE_TURN}턴 이후이고 추정 점수가 앞섬",
        capture(steal=1.0, danger=0.3), kill(), escort(), guard(1.5), evict(), frontline(1.5), raid(1.0), squad(), rush(), picket(), retake(), diversion(), mobile(), warriors(2),
    ),
    phase_branch(
        "ATTACK", f"우리 전투병 ≥ 적 전투병 + {ATTACK_MARGIN}이고 상대가 건물을 가짐",
        capture(steal=1.5, danger=0.5), kill(), escort(), guard(0.5), evict(), frontline(0.5), raid(2.0), squad(), rush(), picket(), retake(), diversion(), mobile(), warriors(1),
    ),
    phase_branch(
        "EXPAND", None,
        capture(steal=1.0, danger=DANGER_DISCOUNT), kill(), escort(), guard(1.0), evict(), frontline(1.0), raid(1.0), squad(), rush(), picket(), retake(), diversion(), mobile(), warriors(1),
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
        (n for n in m.closer if m.ahead(n) and m.enterable(n)), None))),
    Sequence("대기", Condition("지금 칸이 안전", lambda m: m.safe(m.pos)), Act("제자리", lambda m: None)),
    Act("가장 목표에 가까운 안전한 이웃으로 피하기", lambda m: m.go(min(
        (n for n in m.neighbors if m.safe(n)), key=lambda n: m.dist[n], default=None))),
    Act("포위되면 열세가 가장 작은 칸으로 (FLAG_ESCAPE)", lambda m: m.escape()),
    Act("위험해도 목표 쪽으로", lambda m: m.go(
        m.closer[0] if m.closer and m.enterable(m.closer[0]) else None)),
    Act("제자리", lambda m: None),
)


def tree_text() -> str:
    """판단 트리 전체를 글로 (보고서·문서용): python -c "from agent.strategy import tree_text; print(tree_text())" """
    return "\n".join(TURN_TREE.lines() + [""] + FLAG_TREE.lines())
