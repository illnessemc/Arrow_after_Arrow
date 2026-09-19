"""当前关卡的一次游戏过程：负责点击、失误、通关和失败规则。"""

from enum import Enum, auto

from .arrow import Arrow
from .board import GameBoard
from .direction import Cell
from .level import Level
from .rules import ExitRule, StraightExitRule


class ClickResult(Enum):
    """一次网格点击可能产生的结果。"""

    REMOVED = auto()
    BLOCKED = auto()
    EMPTY_CELL = auto()
    GAME_OVER = auto()


class GameSession:
    """协调关卡模板和可变地图，但不包含界面代码。"""

    def __init__(self, level: Level, rule: ExitRule | None = None) -> None:
        self.level = level
        self.rule = rule or StraightExitRule()
        self.board: GameBoard
        self.mistakes_left: int
        self.restart()

    def restart(self) -> None:
        """重建地图并恢复失误次数。"""
        self.board = self.level.create_board()
        self.mistakes_left = self.level.mistake_limit

    @property
    def remaining_arrows(self) -> int:
        return self.board.arrow_count

    @property
    def is_cleared(self) -> bool:
        return self.board.is_empty

    @property
    def is_failed(self) -> bool:
        return self.mistakes_left <= 0

    @property
    def is_over(self) -> bool:
        return self.is_cleared or self.is_failed

    def blocker_of(self, arrow: Arrow) -> Arrow | None:
        return self.rule.first_blocker(self.board, arrow)

    def can_exit(self, arrow: Arrow) -> bool:
        """只有仍在地图中且头部前方无阻挡的箭头可以飞出。"""
        return self.board.get_arrow(arrow.arrow_id) is not None and self.blocker_of(arrow) is None

    def click_cell(self, cell: Cell) -> tuple[ClickResult, Arrow | None]:
        """处理网格点击，返回规则结果以及被点击的箭头。

        返回箭头对象是为了让 UI 在箭头从地图移除后仍可播放飞出动画；规则
        本身并不知道动画的存在。
        """
        if self.is_over:
            return ClickResult.GAME_OVER, None
        arrow = self.board.arrow_at(cell)
        if arrow is None:
            return ClickResult.EMPTY_CELL, None
        if self.can_exit(arrow):
            self.board.remove_arrow(arrow.arrow_id)
            return ClickResult.REMOVED, arrow

        # 只有被阻挡的有效箭头会消耗机会，空白格不会受到惩罚。
        self.mistakes_left -= 1
        return ClickResult.BLOCKED, arrow

