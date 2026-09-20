"""关卡模板：保存初始配置，并负责创建全新的棋盘。"""

from dataclasses import dataclass
from enum import Enum, auto

from .arrow import Arrow
from .board import GameBoard
from .layout import BoardLayout


class LevelRole(Enum):
    """关卡在整体流程中的用途，方便 UI 和后续选关界面展示。"""

    TEST = auto()
    TUTORIAL = auto()
    FORMAL = auto()

    @property
    def label(self) -> str:
        return {
            LevelRole.TEST: "测试关",
            LevelRole.TUTORIAL: "教学关",
            LevelRole.FORMAL: "正式关",
        }[self]


class CoverageMode(Enum):
    """关卡是否要求所有可玩格都被箭头覆盖。"""

    ALLOW_EMPTY = auto()
    REQUIRE_FULL = auto()


@dataclass(frozen=True, slots=True)
class Level:
    """一关的名称、地图大小、初始箭头和失误上限。"""

    name: str
    layout: BoardLayout
    arrows: tuple[Arrow, ...]
    mistake_limit: int = 3
    role: LevelRole = LevelRole.FORMAL
    intro: str = "找出前方没有阻挡的箭头"
    coverage: CoverageMode = CoverageMode.REQUIRE_FULL
    time_limit_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("关卡名称不能为空")
        if self.mistake_limit <= 0:
            raise ValueError("失误次数必须为正数")
        if self.time_limit_seconds <= 0:
            raise ValueError("关卡时限必须大于 0")
        # 复用地图的边界、重复 ID 和格子重叠校验。
        board = self.create_board()
        if self.coverage is CoverageMode.REQUIRE_FULL and board.empty_cells:
            raise ValueError(
                f"关卡 {self.name} 没有铺满棋盘，缺少格子：{sorted(board.empty_cells)}"
            )

    @property
    def rows(self) -> int:
        return self.layout.rows

    @property
    def cols(self) -> int:
        return self.layout.cols

    def create_board(self) -> GameBoard:
        """根据不可变的关卡模板创建一块新的可变地图。"""
        board = GameBoard(self.layout)
        for arrow in self.arrows:
            board.add_arrow(arrow)
        return board

