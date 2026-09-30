"""스위치 실험용 봇 실행기 (제출본에 넣지 않는다): 봇 폴더의 main.py를 strategy 상수만 바꿔 실행한다.

    python scripts/cfg_bot.py <봇 폴더> "이름=값 이름=값"

`es_bot.py`와 달리 학습 가중치(agent/learned.py의 W)는 봇에 박힌 그대로 둔다. 값 형식은 es_bot.py와 같다:
"A.B=값"은 dict 상수 A의 키 B, 원래 상수의 형(int·float)으로 바꾼다. 집합 상수는 "A=HALL,ENG"처럼 쉼표로 쓴다.
빼 보기 실험용: "OFF=별동대,초소"는 그 종류의 과제를 빼고, "W=0"은 학습 가중치를 비운다.
"""

import sys
from pathlib import Path

bot_dir = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(bot_dir))

from agent import learned, strategy  # noqa: E402

off: set[str] = set()
for item in (sys.argv[2] if len(sys.argv) > 2 else "").split():
    name, value = item.split("=")
    if name == "OFF":  # 이 종류의 과제를 목록에서 뺀다(빼 보기 실험). 가치 0으로는 남는 전투병이 끝에 배정되어 완전히 꺼지지 않는다
        off |= set(filter(None, value.split(",")))
        continue
    if name == "W":  # W=0: 학습 가중치를 비운다(학습 층 끔 = 기준값 그대로)
        learned.W.clear()
        continue
    if "." in name:
        top, key = name.split(".")
        setattr(strategy, top, {**getattr(strategy, top), key: float(value)})
        continue
    old = getattr(strategy, name)
    if isinstance(old, (set, frozenset)):
        setattr(strategy, name, set(filter(None, value.split(","))))
    else:
        setattr(strategy, name, type(old)(float(value)))

if off:
    _tasks = strategy.Turn.tasks
    strategy.Turn.tasks = lambda self, unit: [t for t in _tasks(self, unit) if t.kind not in off]

import main  # noqa: E402

main.main()
