"""游戏核心层：只保存数据结构和玩法规则，不依赖 Pygame。"""

from .arrow import Arrow
from .board import GameBoard
from .direction import Cell, Direction
from .game import ClickResult, GameSession
from .layout import BoardLayout
from .level import CoverageMode, Level, LevelRole
from .rules import ExitRule, StraightExitRule
from .scoring import RoundScore, ScoreLedger, ScoreRules, TimedScoreSession
from .solver import LevelSolver, SolveReport

__all__ = [
    "Arrow",
    "BoardLayout",
    "Cell",
    "ClickResult",
    "CoverageMode",
    "Direction",
    "ExitRule",
    "GameBoard",
    "GameSession",
    "Level",
    "LevelRole",
    "LevelSolver",
    "RoundScore",
    "ScoreLedger",
    "ScoreRules",
    "SolveReport",
    "StraightExitRule",
    "TimedScoreSession",
]

