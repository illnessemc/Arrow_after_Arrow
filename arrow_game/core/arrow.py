"""箭头实体。

虽然基础版只有单格箭头，但 Arrow 使用“尾部到头部”的有序坐标序列保存
完整身体。因此它也能描述多格直线和折线路径，后续扩展时不必推翻模型。
"""

from __future__ import annotations

from dataclasses import dataclass

from .direction import Cell, Direction


@dataclass(frozen=True, slots=True)
class Arrow:
    """一支由连续网格坐标组成的箭头。

    cells 示例：单格 ``((2, 3),)``；直线 ``((2, 1), (2, 2))``；
    折线 ``((1, 1), (2, 1), (2, 2))``。
    """

    arrow_id: str
    cells: tuple[Cell, ...]
    direction: Direction

    def __post_init__(self) -> None:
        """创建时检查路径，尽早发现错误的关卡数据。"""
        if not self.arrow_id:
            raise ValueError("箭头 ID 不能为空")
        if not self.cells:
            raise ValueError(f"箭头 {self.arrow_id} 至少占一个格子")
        if len(set(self.cells)) != len(self.cells):
            raise ValueError(f"箭头 {self.arrow_id} 的路径存在重复格子")

        # 多格路径必须上下或左右相接，不能斜连或跳格。
        for previous, current in zip(self.cells, self.cells[1:]):
            row_distance = abs(previous[0] - current[0])
            col_distance = abs(previous[1] - current[1])
            if row_distance + col_distance != 1:
                raise ValueError(f"箭头 {self.arrow_id} 的路径不连续：{previous} -> {current}")

    @classmethod
    def single(
        cls, arrow_id: str, row: int, col: int, direction: Direction
    ) -> Arrow:
        """创建当前基础版使用的单格箭头。"""
        return cls(arrow_id, ((row, col),), direction)

    @property
    def head(self) -> Cell:
        """箭头头部是路径中的最后一个格子。"""
        return self.cells[-1]

    @property
    def tail(self) -> Cell:
        return self.cells[0]

    def contains(self, cell: Cell) -> bool:
        """判断格子是否属于箭头的任意部位。"""
        return cell in self.cells

