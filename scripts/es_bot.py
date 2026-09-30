"""ES 학습용 봇 실행기 (제출본에 넣지 않는다): 봇 폴더의 main.py를 가중치 파일을 넣고 실행한다.

    python scripts/es_bot.py <봇 폴더> <가중치.json>

제출본은 가중치를 agent/learned.py 안의 상수로 갖는다. 학습 중에는 후보마다 파일을 새로 만들 수 없어 이 실행기가
learned.W를 파일 내용으로 채운 뒤 main.main()을 부른다.
"""

import json
import os
import sys
from pathlib import Path

bot_dir = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(bot_dir))

from agent import learned  # noqa: E402

learned.W.clear()
learned.W.update(json.loads(Path(sys.argv[2]).read_text()))

# 환경 변수 ES_CFG = "이름=값 이름=값": strategy 상수(스위치)를 덮어쓴다(es_train.py --cfg). "A.B=값"은 dict 상수 A의 키 B.
# 학습 층이 첫 판단에서 기준값을 읽으므로 여기서 바꾼 값이 기준값이 된다
if os.environ.get("ES_CFG"):
    from agent import strategy

    for item in os.environ["ES_CFG"].split():
        name, value = item.split("=")
        if "." in name:
            top, key = name.split(".")
            setattr(strategy, top, {**getattr(strategy, top), key: float(value)})
        else:
            old = getattr(strategy, name)
            setattr(strategy, name, type(old)(float(value)))

import main  # noqa: E402

main.main()
