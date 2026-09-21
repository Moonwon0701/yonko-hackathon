"""Version-vs-version evaluation harness.

Runs repeated matches between two versions of the agent and reports the win rate, so that
"is this change actually better?" is answered by evidence rather than intuition. Results
belong in ``experiments.md``.

Boundary: contains no agent logic - it only sets up matches, collects outcomes, and
reports.

TODO (day 1): implement once the game can be run locally or against the API.

버전 대 버전 평가 도구.

에이전트의 두 버전 사이에서 경기를 반복해 돌리고 승률을 보고합니다. "이 변경이 정말 더
나은가?"라는 질문에 직감이 아니라 근거로 답하기 위한 것입니다. 결과는 ``experiments.md``에
기록합니다.

경계: 에이전트 로직을 포함하지 않습니다. 경기를 구성하고, 결과를 모으고, 보고할 뿐입니다.

TODO (1일차): 게임을 로컬이나 API 상대로 돌릴 수 있게 되면 구현할 것.
"""
