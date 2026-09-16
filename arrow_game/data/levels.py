"""基础版关卡数据。

本模块只描述地图中摆放哪些箭头，不包含点击、阻挡或界面逻辑。新增关卡
只需向 LEVELS 添加一个 Level，无需修改游戏主循环。
"""

from arrow_game.core import Arrow, Direction, Level


LEVELS: tuple[Level, ...] = (
    Level(
        "初识方向", 5, 5,
        (
            Arrow.single("1-A", 2, 0, Direction.RIGHT),
            Arrow.single("1-B", 2, 3, Direction.UP),
            Arrow.single("1-C", 4, 1, Direction.UP),
            Arrow.single("1-D", 1, 1, Direction.LEFT),
            Arrow.single("1-E", 0, 4, Direction.DOWN),
            Arrow.single("1-F", 3, 4, Direction.RIGHT),
        ),
        mistake_limit=3,
    ),
    Level(
        "连锁释放", 6, 6,
        (
            Arrow.single("2-A", 3, 0, Direction.RIGHT),
            Arrow.single("2-B", 3, 2, Direction.UP),
            Arrow.single("2-C", 3, 5, Direction.DOWN),
            Arrow.single("2-D", 1, 2, Direction.LEFT),
            Arrow.single("2-E", 5, 5, Direction.LEFT),
            Arrow.single("2-F", 1, 0, Direction.LEFT),
            Arrow.single("2-G", 5, 3, Direction.UP),
        ),
        mistake_limit=3,
    ),
    Level(
        "纵横交错", 7, 7,
        (
            Arrow.single("3-A", 3, 0, Direction.RIGHT),
            Arrow.single("3-B", 3, 3, Direction.UP),
            Arrow.single("3-C", 3, 6, Direction.DOWN),
            Arrow.single("3-D", 0, 3, Direction.RIGHT),
            Arrow.single("3-E", 0, 5, Direction.DOWN),
            Arrow.single("3-F", 5, 5, Direction.LEFT),
            Arrow.single("3-G", 5, 1, Direction.UP),
            Arrow.single("3-H", 2, 1, Direction.LEFT),
            Arrow.single("3-I", 6, 6, Direction.LEFT),
            Arrow.single("3-J", 6, 2, Direction.UP),
            Arrow.single("3-K", 1, 6, Direction.UP),
            Arrow.single("3-L", 2, 4, Direction.RIGHT),
        ),
        mistake_limit=4,
    ),
)

