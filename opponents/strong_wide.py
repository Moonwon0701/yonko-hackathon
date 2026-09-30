"""흉내 봇: 넓게 까는 강팀 (ACE·참새튀김기·페이커·모든상금은…·렛츠고).

9/30 서버 리플레이 80여 판에서 우리가 진 강팀은 10~60턴에 전투병을 20~42칸에 넓게 깔고, 깃발병은 3~6명이며, 호위 없는
깃발병이 우리 건물 2칸 안에 오는 턴이 0.04~0.25로 드물었다(이긴 상대는 대부분 0.5~0.9). 기존 흉내 봇(`opponents/base` = `main`
`8fd93ee` 위)은 모두 이 지표가 우리 봇과 비슷해 강팀 스타일이 없었다.

이 봇은 학습 봇(`26fa986` = `daa1888` + ES 240세대, `opponents/base_uo/`에 고정)에 깃발병 총원 3명, 상대 건물 초소 × 3, 깃발병
호위 × 2를 준 것이다(실험 이름 sw1). 지표는 전투병 칸 23.4 · 호위 없는 접근 0.14 · 깃발병 2.9 · 전투병 점유율 0.52로 강팀에
가장 가깝고, `26fa986`의 승점률이 64.5~67.3%로 가장 낮은 로컬 상대다(다른 팀원·흉내 봇 상대 85~96%).
docs/benchmarks.md "예측·스타일 감지·값 차이 교전".

학습 층(agent/learned.py)은 첫 판단에서 기준값을 읽으므로, 아래 값이 학습 층의 기준값이 된다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "base_uo"))

# 경로를 먼저 넣어야 고정한 학습 봇(opponents/base_uo)의 agent를 불러온다
from agent import strategy as s  # noqa: E402

s.MAX_FLAGS = 3
s.PICKET_VALUE = 3.0
s.ESCORT_VALUE = 2.0

import main  # noqa: E402

if __name__ == "__main__":
    main.main()
