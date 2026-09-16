"""方向定义，供箭头、地图扫描和界面绘制共同使用。"""

from enum import Enum

# 游戏中的坐标统一使用 (row, column)，即 (行, 列)。
Cell = tuple[int, int]


class Direction(Enum):
    """四种方向，枚举值表示前进一步时行、列的变化。"""

    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

    @property
    def row_step(self) -> int:
        return self.value[0]

    @property
    def col_step(self) -> int:
        return self.value[1]

