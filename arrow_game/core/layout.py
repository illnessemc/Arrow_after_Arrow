"""棋盘布局定义。

布局只描述棋盘外形，不保存箭头。当前使用完整矩形；``playable_cells`` 的
设计允许后续增加缺角、空洞等异形棋盘，而不必修改箭头和游戏会话。
"""

from __future__ import annotations

from dataclasses import dataclass

from .direction import Cell


@dataclass(frozen=True, slots=True)
class BoardLayout:
    """棋盘边界以及其中可以放置箭头的格子集合。"""

    rows: int
    cols: int
    playable_cells: frozenset[Cell]

    def __post_init__(self) -> None:
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("棋盘行数和列数必须为正数")
        if not self.playable_cells:
            raise ValueError("棋盘至少需要一个可用格子")
        for row, col in self.playable_cells:
            if not (0 <= row < self.rows and 0 <= col < self.cols):
                raise ValueError(f"可用格子 {(row, col)} 超出棋盘边界")

    @classmethod
    def rectangle(cls, rows: int, cols: int) -> BoardLayout:
        """创建当前玩法使用的完整矩形棋盘。"""
        return cls(
            rows=rows,
            cols=cols,
            playable_cells=frozenset(
                (row, col) for row in range(rows) for col in range(cols)
            ),
        )

    def contains(self, cell: Cell) -> bool:
        """判断坐标是不是棋盘中的可玩格。"""
        return cell in self.playable_cells
