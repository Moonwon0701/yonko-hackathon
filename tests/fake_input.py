"""테스트용 무작위 입력 생성기.

게임 엔진이 아니다. 턴 사이의 인과(이동·전투·점령)는 없고, 입출력 규격(규칙서 11장)에 맞는
형식의 INIT·TURN 블록만 무작위로 만든다. 파서와 봇이 어떤 형태의 입력에도 END까지 응답하는지,
두 구현이 같은 입력에 같은 출력을 내는지 확인하는 데 쓴다.
"""

import random

SIZE = 15
BUILDING_KINDS = (
    ["PLAZA"]
    + ["HALL", "LIBRARY", "ENG", "HOSPITAL", "STATION"] * 2
    + ["STATION", "WATCH", "DEPOT"] * 2
)


def random_game(seed: int, turns: int, team: str | None = None) -> str:
    rng = random.Random(seed)
    team = team or rng.choice("YK")
    cells = [(x, y) for y in range(SIZE) for x in range(SIZE)]
    rng.shuffle(cells)
    bases = {"Y": cells[0], "K": cells[1]}
    buildings = cells[2:19]
    obstacles = set(cells[19:39])

    grid = [["."] * SIZE for _ in range(SIZE)]
    for x, y in obstacles:
        grid[y][x] = "#"
    for x, y in buildings:
        grid[y][x] = "B"
    for x, y in bases.values():
        grid[y][x] = "H"
    open_cells = [c for c in cells if c not in obstacles]

    out = [f"INIT {SIZE} {SIZE}", f"TEAM {team}"]
    out += ["MAP " + "".join(row) for row in grid]
    out.append("BUILDINGS 17")
    out += [f"{i} {x} {y} {kind}" for i, ((x, y), kind) in enumerate(zip(buildings, BUILDING_KINDS))]
    out += [f"BASE Y {bases['Y'][0]} {bases['Y'][1]}", f"BASE K {bases['K'][0]} {bases['K'][1]}"]
    out.append("END")

    for turn in range(1, turns + 1):
        units = {}
        for _ in range(rng.randint(0, 14)):
            key = (rng.choice("YK"), rng.choice("FWS"), rng.choice(open_cells))
            units[key] = rng.randint(1, 6)
        order = sorted(units, key=lambda k: ("YK".index(k[0]), "FWS".index(k[1]), k[2][1], k[2][0]))
        out.append(f"TURN {turn}")
        out.append(f"RESOURCE {rng.randint(0, 40)} {rng.randint(0, 40)}")
        out.append(f"UNITS {len(units)}")
        out += [f"{t} {k} {x} {y} {units[(t, k, (x, y))]}" for t, k, (x, y) in order]
        out.append("BUILDINGS 17")
        for i, ((x, y), kind) in enumerate(zip(buildings, BUILDING_KINDS)):
            owner = rng.choice("NNYK")
            stage = 2 if owner != "N" else rng.choice((0, 0, 1))
            score = rng.choice((-1, -1, rng.randint(1, 4)))
            out.append(f"{i} {x} {y} {kind} {owner} {stage} {score}")
        out.append("END")
    return "\n".join(out) + "\n"
