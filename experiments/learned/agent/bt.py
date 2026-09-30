"""행동 트리(BT) 뼈대. 게임을 모르는 범용 노드만 있고, 트리 조립은 strategy.py가 한다.

노드는 tick(ctx)로 실행하고 성공(True)·실패(False)를 돌려준다. 매 턴 루트부터 한 번 끝까지 평가한다.
매 턴 모든 유닛의 행동을 새로 정하므로 여러 턴에 걸쳐 "실행 중"인 노드는 없다(RUNNING 상태를 두지 않는다).
턴을 넘어 기억해야 하는 것(지금 국면)은 Latch 노드가 ctx.phase에 적어 둔다.
"""

from __future__ import annotations

from collections.abc import Callable


class Node:
    """BT 노드. `name`은 사람이 읽는 이름으로, tree_text()와 보고서의 트리 그림에 그대로 나온다."""

    kind = "?"

    def __init__(self, name: str, *children: Node) -> None:
        self.name = name
        self.children = children

    def tick(self, ctx) -> bool:
        raise NotImplementedError

    def lines(self, depth: int = 0) -> list[str]:
        out = ["  " * depth + f"{self.kind} {self.name}"]
        for child in self.children:
            out += child.lines(depth + 1)
        return out


class Selector(Node):
    """대안 목록: 자식을 차례로 실행해 처음 성공한 곳에서 멈춘다. 모두 실패하면 실패."""

    kind = "?"

    def tick(self, ctx) -> bool:
        return any(child.tick(ctx) for child in self.children)


class Sequence(Node):
    """순서대로 실행: 자식이 모두 성공해야 성공. 하나라도 실패하면 거기서 멈춘다."""

    kind = "→"

    def tick(self, ctx) -> bool:
        return all(child.tick(ctx) for child in self.children)


class Condition(Node):
    """조건 잎: `test(ctx)`가 참이면 성공. 상태를 바꾸지 않는다."""

    kind = "◇"

    def __init__(self, name: str, test: Callable[..., bool]) -> None:
        super().__init__(name)
        self.test = test

    def tick(self, ctx) -> bool:
        return bool(self.test(ctx))


class Act(Node):
    """행동 잎: `run(ctx)`를 실행한다. False를 돌려주면 실패(할 수 없었다), 그 밖에는 성공."""

    kind = "▶"

    def __init__(self, name: str, run: Callable[..., bool | None]) -> None:
        super().__init__(name)
        self.run = run

    def tick(self, ctx) -> bool:
        return self.run(ctx) is not False


class Latch(Node):
    """국면 유지(히스테리시스): 조건 노드를 감싸, 조건이 풀려도 이 국면이 지금 국면이면 `hold - 1`턴 더
    성공으로 본다. 더 급한 국면은 Selector에서 앞에 있으므로 언제든 바로 끼어든다.

    ctx.phase = {"name": 지금 국면, "calm": 지금 국면의 조건이 연속으로 풀린 턴 수}
    """

    kind = "◇"

    def __init__(self, phase: str, condition: Node, hold: int) -> None:
        super().__init__(f"{condition.name} (풀려도 {hold - 1}턴 유지)")
        self.phase = phase
        self.condition = condition
        self.hold = hold

    def tick(self, ctx) -> bool:
        current = ctx.phase["name"] == self.phase
        if self.condition.tick(ctx):
            if current:
                ctx.phase["calm"] = 0
            return True
        if current and ctx.phase["calm"] + 1 < self.hold:
            ctx.phase["calm"] += 1
            return True
        return False
