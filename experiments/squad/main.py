"""실험 봇 진입 파일: 저장소 main.py를 그대로 돌리되 판단만 squad.decide로 바꾼다.

python -m sim arena experiments/squad git:main --seed 100 --seeds 25
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import squad

import main as root_main

root_main.decide = squad.decide

if __name__ == "__main__":
    root_main.main()
