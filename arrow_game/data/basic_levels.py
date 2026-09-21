"""基础模式的三关手工单格箭头关卡。

基础模式复现项目早期版本的规则表现：每支箭头只占一个格子，玩家只需判断
箭头朝向上的直线路径。三关均允许棋盘留空，并通过显式坐标保持设计可控。
"""

from arrow_game.core import BoardLayout, Direction, Level, LevelRole, LevelSolver

from .builders import ManualLevelBuilder


def _build_four_way_start() -> Level:
    """第一关：用外圈安全箭头展示四个方向，并加入一条短依赖链。"""
    builder = ManualLevelBuilder(
        "四向起步",
        BoardLayout.rectangle(5, 5),
        role=LevelRole.TUTORIAL,
        intro="",
        mistake_limit=3,
        require_full_coverage=False,
        time_limit_seconds=45.0,
    )
    arrows = (
        ("B1-01", 0, 2, Direction.UP),
        ("B1-02", 2, 4, Direction.RIGHT),
        ("B1-03", 4, 2, Direction.DOWN),
        ("B1-04", 2, 0, Direction.LEFT),
        # B1-05 被右侧的 B1-02 阻挡；移除后 B1-06 才能向上离开。
        ("B1-05", 2, 2, Direction.RIGHT),
        ("B1-06", 3, 2, Direction.UP),
    )
    for arrow_id, row, col, direction in arrows:
        builder.add_path(arrow_id, ((row, col),), direction)
    return builder.build()


def _build_crossroads() -> Level:
    """第二关：六组不同朝向的箭头在横纵路径上互相制约。"""
    builder = ManualLevelBuilder(
        "交错路口",
        BoardLayout.rectangle(7, 7),
        role=LevelRole.FORMAL,
        intro="",
        mistake_limit=3,
        require_full_coverage=False,
        time_limit_seconds=70.0,
    )
    arrows = (
        ("B2-01", 0, 1, Direction.LEFT),
        ("B2-02", 1, 6, Direction.UP),
        ("B2-03", 6, 5, Direction.LEFT),
        ("B2-04", 5, 0, Direction.DOWN),
        ("B2-05", 1, 1, Direction.UP),
        ("B2-06", 1, 4, Direction.RIGHT),
        ("B2-07", 4, 5, Direction.DOWN),
        ("B2-08", 5, 2, Direction.LEFT),
        ("B2-09", 2, 3, Direction.LEFT),
        ("B2-10", 4, 3, Direction.UP),
        ("B2-11", 3, 6, Direction.DOWN),
        ("B2-12", 3, 2, Direction.RIGHT),
    )
    for arrow_id, row, col, direction in arrows:
        builder.add_path(arrow_id, ((row, col),), direction)
    return builder.build()


def _build_linked_center() -> Level:
    """第三关：中心四向依赖与角落长依赖链组合成完整观察题。"""
    builder = ManualLevelBuilder(
        "中心连锁",
        BoardLayout.rectangle(8, 8),
        role=LevelRole.FORMAL,
        intro="",
        mistake_limit=3,
        require_full_coverage=False,
        time_limit_seconds=90.0,
    )
    arrows = (
        # 外层出口。
        ("B3-01", 0, 3, Direction.LEFT),
        ("B3-02", 3, 7, Direction.UP),
        ("B3-03", 7, 4, Direction.RIGHT),
        ("B3-04", 4, 0, Direction.DOWN),
        # 第二层分别被外层箭头阻挡。
        ("B3-05", 2, 3, Direction.UP),
        ("B3-06", 3, 5, Direction.RIGHT),
        ("B3-07", 5, 4, Direction.DOWN),
        ("B3-08", 4, 2, Direction.LEFT),
        # 中心箭头继续依赖第二层，形成多级清除顺序。
        ("B3-09", 5, 3, Direction.UP),
        ("B3-10", 2, 4, Direction.DOWN),
        ("B3-11", 4, 5, Direction.LEFT),
        ("B3-12", 3, 2, Direction.RIGHT),
        # 左上到右下再返回右上的四步链。
        ("B3-13", 1, 1, Direction.UP),
        ("B3-14", 6, 1, Direction.UP),
        ("B3-15", 6, 6, Direction.LEFT),
        ("B3-16", 1, 6, Direction.DOWN),
    )
    for arrow_id, row, col, direction in arrows:
        builder.add_path(arrow_id, ((row, col),), direction)
    return builder.build()


BASIC_LEVELS: tuple[Level, ...] = (
    _build_four_way_start(),
    _build_crossroads(),
    _build_linked_center(),
)

_solver = LevelSolver()
BASIC_LEVEL_REPORTS = tuple(
    _solver.require_solvable(level) for level in BASIC_LEVELS
)
