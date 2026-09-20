"""固定关卡目录：一关稀疏教学关和五关手工主题关。

固定关不会在启动时调用自动生成器。每支箭头的路径都保存在
``manual_levels`` 中；自动生成器只供无尽模式使用。
"""

from arrow_game.core import BoardLayout, Direction, Level, LevelRole, LevelSolver

from .builders import ManualLevelBuilder
from .manual_levels import HANDCRAFTED_LEVELS


def build_tutorial_level() -> Level:
    """手工稀疏教学关：六支箭头组成唯一且容易观察的移除顺序。"""
    builder = ManualLevelBuilder(
        "方向入门",
        BoardLayout.rectangle(9, 8),
        role=LevelRole.TUTORIAL,
        intro="",
        mistake_limit=3,
        require_full_coverage=False,
        time_limit_seconds=60.0,
    )
    # 正确顺序为 T-2 → T-1 → T-4 → T-3 → T-5 → T-6。
    # 依赖链依次展示右、上、左、下四个方向和一支简单折线箭头。
    builder.add_path("T-1", ((1, 1), (1, 2), (1, 3)))
    builder.add_path("T-2", ((1, 6),), Direction.UP)
    builder.add_path("T-3", ((7, 6),), Direction.LEFT)
    builder.add_path("T-4", ((7, 2),), Direction.UP)
    builder.add_path("T-5", ((2, 6), (3, 6), (4, 6)))
    builder.add_path("T-6", ((3, 0), (4, 0), (4, 1)))
    return builder.build()


_solver = LevelSolver()

TUTORIAL_LEVEL = build_tutorial_level()
LEVELS: tuple[Level, ...] = (
    TUTORIAL_LEVEL,
    *HANDCRAFTED_LEVELS,
)

# 固定关数据变更后立即验证，避免错误路径进入选关界面。
LEVEL_REPORTS = tuple(_solver.require_solvable(level) for level in LEVELS)
