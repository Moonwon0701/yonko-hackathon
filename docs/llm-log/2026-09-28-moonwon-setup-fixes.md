# 새 환경에서 README대로 설치하면 막히는 곳 고치기

- 날짜: 2026-09-28
- 요청한 사람: 문원
- 모델: Claude Opus 5.5 (`claude-opus-5-5`), Claude Code CLI
- PR: (브랜치 `moonwon/setup-fixes`)

## 프롬프트 (원문 그대로)

1. > 팀원이 새 환경에서 현재 readme대로 하면 작업  가능해? 그리고 파이썬 설치는 되어있어야하지?
2. > 응 그거 다 고쳐서 PR 올려. 깃헙익스텐션으로 설치하는 것도 방법인가?

## 목적

- 팀원이 새 PC에서 README만 보고 개발 환경을 만들 수 있는지 확인하고, 막히는 곳을 없앤다.

## 범위 — LLM이 한 것

- 확인: GitHub `main`을 임시 폴더에 새로 clone해 README 순서(`py -m venv` → 활성화 →
  `pip install -e ".[dev]"` → `pytest`)를 그대로 실행했다. `pytest`가
  `ModuleNotFoundError: No module named 'sim'`으로 테스트 파일 4개를 못 불러오는 것,
  `ruff check .`가 에러 3개로 실패하는 것, README에 Python·Git 설치 방법이 없는 것을 찾았다.
- `pyproject.toml`: `[tool.pytest.ini_options]`에 `pythonpath = ["."]` 추가. `sim/`은 설치
  패키지가 아니어서 `python -m pytest`로만 되던 것을 그냥 `pytest`로도 되게 했다.
- `README.md`: "먼저 설치할 것" 절(Python 3.12·Git 받는 곳, py launcher, 설치 확인 명령) 추가.
  Store Python·VS Code Python 확장·GitHub Desktop으로는 대신할 수 없다는 설명 추가. 금방 틀려지는
  테스트 개수("784개") 대신 "실패 1개만 나오면 정상"으로 바꾸고 `ruff check .` 확인을 넣었다.
- `agent/strategy.py`, `tests/test_parity.py`: `ruff check --fix`로 import 정렬만 고쳤다(동작 변화 없음).
- `main.py`: 로그 실패를 삼키는 `try`-`except`-`pass`는 의도된 코드라 `noqa`에 `S110`을 더했다.

## 사람이 한 것

- 문원: 확인 결과를 보고 전부 고쳐서 PR로 올리라고 결정했다.

## 검증

- 이 브랜치에서 새 venv를 만들어 `pip install -e ".[dev]"` 후 그냥 `pytest`: 793개 통과,
  1개 실패(`test_devtool_is_unmodified`, README에 적은 예상된 실패).
- `ruff check .`: All checks passed!
