"""可替换的玩法规则。

基础玩法保持不变：从箭头头部沿最终方向检查到棋盘边界。将该判断放进规则
对象后，未来加入传送、转向或特殊出口时，可以新增规则类而不改游戏会话。
"""

from typing import Protocol

from .arrow import Arrow
from .board import GameBoard


class ExitRule(Protocol):
    """所有箭头出界规则需要实现的最小接口。"""

    def first_blocker(self, board: GameBoard, arrow: Arrow) -> Arrow | None:
        """返回阻挡箭头；路径畅通时返回 None。"""
        ...


class StraightExitRule:
    """当前基础玩法：沿头部朝向直线飞出棋盘。"""

    def first_blocker(self, board: GameBoard, arrow: Arrow) -> Arrow | None:
        return board.first_blocker(arrow)
