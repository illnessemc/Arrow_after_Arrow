"""棋盘地图与格子占用关系。

GameBoard 统一管理地图大小、箭头集合和每个格子的主人。以后箭头占多个格子
或出现折线时，阻挡规则仍可通过相同接口查询，而不需要重写占用逻辑。
"""

from collections.abc import Iterator

from .arrow import Arrow
from .direction import Cell, Direction


class GameBoard:
    """保存一局游戏中会发生变化的地图状态。"""

    def __init__(self, rows: int, cols: int) -> None:
        if rows <= 0 or cols <= 0:
            raise ValueError("棋盘行数和列数必须为正数")
        self.rows = rows
        self.cols = cols
        self._arrows: dict[str, Arrow] = {}
        self._cell_owners: dict[Cell, str] = {}

    @property
    def arrows(self) -> tuple[Arrow, ...]:
        """以只读元组形式提供棋盘中的箭头。"""
        return tuple(self._arrows.values())

    @property
    def arrow_count(self) -> int:
        return len(self._arrows)

    @property
    def is_empty(self) -> bool:
        return not self._arrows

    def is_inside(self, cell: Cell) -> bool:
        row, col = cell
        return 0 <= row < self.rows and 0 <= col < self.cols

    def add_arrow(self, arrow: Arrow) -> None:
        """放入整支箭头，并为它的每个身体格建立占用索引。"""
        if arrow.arrow_id in self._arrows:
            raise ValueError(f"重复的箭头 ID：{arrow.arrow_id}")
        for cell in arrow.cells:
            if not self.is_inside(cell):
                raise ValueError(f"箭头 {arrow.arrow_id} 的格子 {cell} 超出棋盘")
            if cell in self._cell_owners:
                raise ValueError(f"格子 {cell} 已被箭头 {self._cell_owners[cell]} 占用")

        self._arrows[arrow.arrow_id] = arrow
        for cell in arrow.cells:
            self._cell_owners[cell] = arrow.arrow_id

    def get_arrow(self, arrow_id: str) -> Arrow | None:
        return self._arrows.get(arrow_id)

    def arrow_at(self, cell: Cell) -> Arrow | None:
        """查找占据格子的箭头，点击多格箭头的任意部位同样有效。"""
        arrow_id = self._cell_owners.get(cell)
        return self._arrows.get(arrow_id) if arrow_id is not None else None

    def remove_arrow(self, arrow_id: str) -> Arrow | None:
        """移除整支箭头，并同步释放全部身体格。"""
        arrow = self._arrows.pop(arrow_id, None)
        if arrow is None:
            return None
        for cell in arrow.cells:
            self._cell_owners.pop(cell, None)
        return arrow

    def cells_to_edge(self, start: Cell, direction: Direction) -> Iterator[Cell]:
        """从起点的下一个格子开始，生成直到边界的直线路径。"""
        row, col = start
        row += direction.row_step
        col += direction.col_step
        while self.is_inside((row, col)):
            yield row, col
            row += direction.row_step
            col += direction.col_step

    def first_blocker(self, arrow: Arrow) -> Arrow | None:
        """返回箭头头部前进方向上的第一支阻挡箭头。"""
        for cell in self.cells_to_edge(arrow.head, arrow.direction):
            owner_id = self._cell_owners.get(cell)
            # 排除自身能兼容未来可能绕到头部前方的复杂折线路径。
            if owner_id is not None and owner_id != arrow.arrow_id:
                return self._arrows[owner_id]
        return None

