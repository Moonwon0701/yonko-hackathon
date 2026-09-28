"""실험 봇 진입 파일: 저장소 main.py를 그대로 돌리되 판단만 agent.strategy_rally.decide로 바꾼다.

python -m sim arena experiments/rally git:main --seeds 25
제출 ZIP에는 들어가지 않는다(scripts/build_submission.py는 저장소 main.py·agent/·submission.json만 넣는다).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import main as root_main
from agent import strategy_rally

root_main.decide = strategy_rally.decide

if __name__ == "__main__":
    root_main.main()
