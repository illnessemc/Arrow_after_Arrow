"""当前三关的手工关卡数据。

三关都要求箭头完整覆盖可玩区域。路径按“尾部 -> 头部”填写，解题时按编号
倒序移除：最后一支先从边界飞出，再逐步释放前面的箭头。

第三关刻意保留为显式手工路径，便于逐格调整正式关卡。后续自动生成器应
实现 ``LevelBuilder`` 接口，并在生成后继续交给 Level 做重叠和覆盖校验。
"""

from arrow_game.core import BoardLayout, Level, LevelRole

from .builders import ManualLevelBuilder


def build_test_level() -> Level:
    """4x4 测试关：覆盖直线、折线、点击身体和连锁释放。"""
    builder = ManualLevelBuilder(
        "路径测试",
        BoardLayout.rectangle(4, 4),
        role=LevelRole.TEST,
        intro="测试关：蓝色线条是一整支箭，点击任意部位都可选中",
        mistake_limit=5,
    )
    return (
        builder
        .add_path("T-1", ((0, 0), (0, 1), (0, 2)))
        .add_path("T-2", ((0, 3), (1, 3), (1, 2)))
        .add_path("T-3", ((1, 1), (1, 0), (2, 0), (2, 1)))
        .add_path("T-4", ((2, 2), (2, 3), (3, 3), (3, 2)))
        .add_path("T-5", ((3, 1), (3, 0)))
        .build()
    )


def build_tutorial_level() -> Level:
    """5x5 教学关：箭头更长，继续使用清晰的单链消除顺序。"""
    builder = ManualLevelBuilder(
        "折线教学",
        BoardLayout.rectangle(5, 5),
        role=LevelRole.TUTORIAL,
        intro="教学关：先找头部朝向畅通的箭头，再按释放顺序消除",
        mistake_limit=4,
    )
    return (
        builder
        .add_path("G-1", ((0, 0), (0, 1), (0, 2)))
        .add_path("G-2", ((0, 3), (0, 4), (1, 4), (1, 3), (1, 2)))
        .add_path("G-3", ((1, 1), (1, 0), (2, 0), (2, 1), (2, 2)))
        .add_path("G-4", ((2, 3), (2, 4), (3, 4), (3, 3), (3, 2)))
        .add_path("G-5", ((3, 1), (3, 0), (4, 0), (4, 1), (4, 2)))
        .add_path("G-6", ((4, 3), (4, 4)))
        .build()
    )


def build_formal_level() -> Level:
    """7x7 正式关：显式手工填写七支长折线箭头并铺满棋盘。"""
    builder = ManualLevelBuilder(
        "回环交错",
        BoardLayout.rectangle(7, 7),
        role=LevelRole.FORMAL,
        intro="正式关：观察长折线之间的依赖，从唯一出口开始拆解",
        mistake_limit=3,
    )
    return (
        builder
        .add_path("F-1", ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4)))
        .add_path(
            "F-2",
            ((0, 5), (0, 6), (1, 6), (1, 5), (1, 4), (1, 3), (1, 2)),
        )
        .add_path(
            "F-3",
            ((1, 1), (1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4)),
        )
        .add_path(
            "F-4",
            ((2, 5), (2, 6), (3, 6), (3, 5), (3, 4), (3, 3), (3, 2)),
        )
        .add_path(
            "F-5",
            ((3, 1), (3, 0), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4)),
        )
        .add_path(
            "F-6",
            ((4, 5), (4, 6), (5, 6), (5, 5), (5, 4), (5, 3), (5, 2)),
        )
        .add_path(
            "F-7",
            (
                (5, 1), (5, 0), (6, 0), (6, 1), (6, 2),
                (6, 3), (6, 4), (6, 5), (6, 6),
            ),
        )
        .build()
    )


LEVELS: tuple[Level, ...] = (
    build_test_level(),
    build_tutorial_level(),
    build_formal_level(),
)

