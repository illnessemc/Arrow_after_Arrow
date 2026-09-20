"""关卡目录：一关手工教学关，加上在线确定性生成的正式关卡。

教学关继续显式保存路径，方便讲解和精细调整。正式关只填写尺寸、种子和
长度范围，实际箭头路径由生成器构造，并在加入目录前通过求解器验证。
"""

from arrow_game.core import BoardLayout, Level, LevelRole, LevelSolver

from .builders import ManualLevelBuilder
from .generator import (
    ArrowShapeMix,
    CoveragePattern,
    GeneratedLevel,
    GeneratedLevelSpec,
    SerpentineLevelGenerator,
)


def build_tutorial_level() -> Level:
    """手工 12×10 教学关：长折线与短箭头交替形成明确依赖。"""
    builder = ManualLevelBuilder(
        "折线入门",
        BoardLayout.rectangle(12, 10),
        role=LevelRole.TUTORIAL,
        intro="",
        mistake_limit=5,
    )
    for pair in range(6):
        top = pair * 2
        bottom = top + 1
        if pair % 2 == 0:
            long_path = (
                *((top, col) for col in range(10)),
                *((bottom, col) for col in range(9, 4, -1)),
            )
            short_path = tuple((bottom, col) for col in range(4, -1, -1))
        else:
            long_path = (
                *((top, col) for col in range(9, -1, -1)),
                *((bottom, col) for col in range(5)),
            )
            short_path = tuple((bottom, col) for col in range(5, 10))
        builder.add_path(f"T-{pair * 2 + 1}", long_path)
        builder.add_path(f"T-{pair * 2 + 2}", short_path)
    return builder.build()


def raised_board_cells(rows: int, cols: int) -> frozenset[tuple[int, int]]:
    """创建“凸”字轮廓：上半部较窄，下半部铺满。"""
    shoulder_row = rows // 3
    stem_width = max(6, cols // 2)
    stem_left = (cols - stem_width) // 2
    return frozenset(
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if row >= shoulder_row or stem_left <= col < stem_left + stem_width
    )


# 新增正式关卡只需要增加一条规格，不再逐格编写路径。
GENERATED_SPECS: tuple[GeneratedLevelSpec, ...] = (
    GeneratedLevelSpec(
        "初级回路", 22, 16, seed=20260923,
        min_arrow_length=2, max_arrow_length=16, boundary_break_chance=0.5,
        path_mix_factor=2.0,
        coverage_pattern=CoveragePattern.GLOBAL_WEAVE,
        shape_mix=ArrowShapeMix(straight=0.3, single_turn=0.45, multi_turn=0.25),
        nested_region_ratio=0.35,
        vertical_region_ratio=0.45,
    ),
    GeneratedLevelSpec(
        "折返迷阵", 26, 18, seed=20260922,
        min_arrow_length=2, max_arrow_length=16, boundary_break_chance=0.4,
        path_mix_factor=2.0,
        coverage_pattern=CoveragePattern.GLOBAL_WEAVE,
        shape_mix=ArrowShapeMix(straight=0.25, single_turn=0.4, multi_turn=0.35),
        nested_region_ratio=0.3,
        vertical_region_ratio=0.55,
    ),
    GeneratedLevelSpec(
        "密集交织", 30, 20, seed=20261118,
        min_arrow_length=2, max_arrow_length=18, boundary_break_chance=0.25,
        path_mix_factor=2.0,
        coverage_pattern=CoveragePattern.GLOBAL_WEAVE,
        shape_mix=ArrowShapeMix(straight=0.2, single_turn=0.4, multi_turn=0.4),
        nested_region_ratio=0.4,
        vertical_region_ratio=0.5,
    ),
    GeneratedLevelSpec(
        "异形挑战", 30, 20, seed=20261037,
        min_arrow_length=2, max_arrow_length=10, boundary_break_chance=0.2,
        path_mix_factor=2.0,
        coverage_pattern=CoveragePattern.GLOBAL_WEAVE,
        shape_mix=ArrowShapeMix(straight=0.3, single_turn=0.4, multi_turn=0.3),
        playable_cells=raised_board_cells(30, 20),
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
