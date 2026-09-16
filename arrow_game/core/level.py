"""关卡模板：保存初始配置，并负责创建全新的棋盘。"""

from dataclasses import dataclass

from .arrow import Arrow
from .board import GameBoard


@dataclass(frozen=True, slots=True)
class Level:
    """一关的名称、地图大小、初始箭头和失误上限。"""

    name: str
    rows: int
    cols: int
    arrows: tuple[Arrow, ...]
    mistake_limit: int = 3

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("关卡名称不能为空")
        if self.mistake_limit <= 0:
            raise ValueError("失误次数必须为正数")
        # 复用地图的边界、重复 ID 和格子重叠校验。
        self.create_board()

    def create_board(self) -> GameBoard:
        """根据不可变的关卡模板创建一块新的可变地图。"""
        board = GameBoard(self.rows, self.cols)
        for arrow in self.arrows:
            board.add_arrow(arrow)
        return board

