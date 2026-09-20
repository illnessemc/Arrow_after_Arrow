"""关卡构建接口。

当前使用 ``ManualLevelBuilder`` 明确填写每支箭头的路径。以后可以增加随机、
模板或文件驱动的构建器，只要同样提供 ``build()`` 并返回 Level，游戏主循环
就无需区分关卡来自哪种设计方式。
"""

from __future__ import annotations

from typing import Protocol

from arrow_game.core import (
    Arrow,
    BoardLayout,
    Cell,
    CoverageMode,
    Direction,
    Level,
    LevelRole,
)


class LevelBuilder(Protocol):
    """后续所有关卡生成方式共同遵守的接口。"""

    def build(self) -> Level:
        ...


class ManualLevelBuilder:
    """通过代码逐支填写箭头的关卡构建器。"""

    def __init__(
        self,
        name: str,
        layout: BoardLayout,
        *,
        role: LevelRole,
        intro: str,
        mistake_limit: int = 3,
        require_full_coverage: bool = True,
        time_limit_seconds: float = 120.0,
    ) -> None:
        self.name = name
        self.layout = layout
        self.role = role
        self.intro = intro
        self.mistake_limit = mistake_limit
        self.require_full_coverage = require_full_coverage
        self.time_limit_seconds = time_limit_seconds
        self._arrows: list[Arrow] = []

    def add_arrow(self, arrow: Arrow) -> ManualLevelBuilder:
        """加入一支已经构造好的箭头，返回自身以支持链式调用。"""
        self._arrows.append(arrow)
        return self

    def add_path(
        self,
        arrow_id: str,
        cells: tuple[Cell, ...],
        direction: Direction | None = None,
    ) -> ManualLevelBuilder:
        """用路径添加箭头；多格路径可从最后一段自动推断朝向。"""
        if direction is None:
            if len(cells) < 2:
                raise ValueError("单格箭头无法自动推断方向")
            previous, head = cells[-2:]
            delta = (head[0] - previous[0], head[1] - previous[1])
            try:
                direction = Direction(delta)
            except ValueError as error:
                raise ValueError(f"箭头 {arrow_id} 的最后一段不是相邻格子") from error
        return self.add_arrow(Arrow(arrow_id, cells, direction))

    def build(self) -> Level:
        coverage = (
            CoverageMode.REQUIRE_FULL
            if self.require_full_coverage
            else CoverageMode.ALLOW_EMPTY
        )
        return Level(
            name=self.name,
            layout=self.layout,
            arrows=tuple(self._arrows),
            mistake_limit=self.mistake_limit,
            role=self.role,
            intro=self.intro,
            coverage=coverage,
            time_limit_seconds=self.time_limit_seconds,
        )
