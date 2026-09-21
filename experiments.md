# Experiments / 실험 기록

Every strategy or tuning change gets a row, whether or not we keep it. A change merges on
an arena result, not on intuition - and knowing what *failed* saves us from retrying it at
2am on day 3.

모든 전략 변경과 튜닝은, 채택 여부와 관계없이 한 행으로 기록합니다. 변경은 직감이 아니라 아레나
결과로 머지합니다. 무엇이 *실패했는지* 남겨 두면 3일차 새벽 2시에 같은 시도를 반복하지 않게
됩니다.

Record the arena result as win rate against the version on `main` at the time, with the
number of games (a 3-game result is noise).

아레나 결과는 그 시점의 `main` 버전을 상대로 한 승률과 경기 수를 함께 적습니다(3판짜리 결과는
그냥 잡음입니다).

| Date / 날짜 | Change / 변경 내용 | Arena result / 아레나 결과 | Kept? / 채택 여부 |
|---|---|---|---|
| | | | |

<!-- Example of the expected format - delete once there are real rows:
     형식 예시입니다. 실제 기록이 쌓이면 지우세요:
| 2026-09-22 | Prefer nearest uncaptured flag over nearest enemy / 가장 가까운 적보다 미점령 깃발 우선 | 62% over 50 games vs main / 50판 기준 62% | yes / 채택 |
| 2026-09-22 | Retreat below 30% health / 체력 30% 미만이면 후퇴 | 44% over 50 games vs main / 50판 기준 44% | no - too passive / 미채택 - 너무 소극적 |
-->
