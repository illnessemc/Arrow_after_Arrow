"""关卡目录：一关手工教学关，加上在线确定性生成的正式关卡。

教学关继续显式保存路径，方便讲解和精细调整。正式关只填写尺寸、种子和
长度范围，实际箭头路径由生成器构造，并在加入目录前通过求解器验证。
"""

from arrow_game.core import BoardLayout, Level, LevelRole, LevelSolver

from .builders import ManualLevelBuilder
from .generator import GeneratedLevel, GeneratedLevelSpec, SerpentineLevelGenerator


def build_tutorial_level() -> Level:
    """手工 7×9 教学关：用明确的依赖链介绍长折线玩法。"""
    builder = ManualLevelBuilder(
        "折线入门",
        BoardLayout.rectangle(7, 9),
        role=LevelRole.TUTORIAL,
        intro="教学关：整条折线是一支箭，可点击线段的任意位置",
        mistake_limit=5,
    )
    return (
        builder
        .add_path(
            "T-1",
            ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6)),
        )
        .add_path("T-2", ((0, 7), (0, 8), (1, 8), (1, 7), (1, 6)))
        .add_path(
            "T-3",
            ((1, 5), (1, 4), (1, 3), (1, 2), (1, 1), (1, 0), (2, 0), (2, 1), (2, 2)),
        )
        .add_path(
            "T-4",
            ((2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 8), (3, 7), (3, 6)),
        )
        .add_path(
            "T-5",
            ((3, 5), (3, 4), (3, 3), (3, 2), (3, 1), (3, 0), (4, 0), (4, 1), (4, 2)),
        )
        .add_path(
            "T-6",
            ((4, 3), (4, 4), (4, 5), (4, 6), (4, 7), (4, 8), (5, 8), (5, 7), (5, 6)),
        )
        .add_path(
            "T-7",
            ((5, 5), (5, 4), (5, 3), (5, 2), (5, 1), (5, 0), (6, 0), (6, 1), (6, 2)),
        )
        .add_path("T-8", ((6, 3), (6, 4), (6, 5), (6, 6), (6, 7), (6, 8)))
        .build()
    )


# 新增正式关卡只需要增加一条规格，不再逐格编写路径。
GENERATED_SPECS: tuple[GeneratedLevelSpec, ...] = (
    GeneratedLevelSpec(
        "初级回路", 8, 10, seed=20260921,
        min_arrow_length=4, max_arrow_length=10, boundary_break_chance=0.55,
    ),
    GeneratedLevelSpec(
        "折返迷阵", 9, 11, seed=20260922,
        min_arrow_length=5, max_arrow_length=12, boundary_break_chance=0.4,
    ),
    GeneratedLevelSpec(
        "密集交织", 10, 12, seed=20260923,
        min_arrow_length=5, max_arrow_length=13, boundary_break_chance=0.25,
    ),
    GeneratedLevelSpec(
        "长线挑战", 11, 13, seed=20260924,
        min_arrow_length=6, max_arrow_length=15, boundary_break_chance=0.15,
    ),
)

_solver = LevelSolver()
_generator = SerpentineLevelGenerator(_solver)

TUTORIAL_LEVEL = build_tutorial_level()
TUTORIAL_REPORT = _solver.require_solvable(TUTORIAL_LEVEL)
GENERATED_LEVELS: tuple[GeneratedLevel, ...] = tuple(
    _generator.generate(spec) for spec in GENERATED_SPECS
)

LEVELS: tuple[Level, ...] = (
    TUTORIAL_LEVEL,
    *(generated.level for generated in GENERATED_LEVELS),
)
