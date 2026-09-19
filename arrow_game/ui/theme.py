"""参考原版观感的深色主题，以及关卡箭头配色。"""

from __future__ import annotations

import random
from dataclasses import dataclass

from arrow_game.core import Level

Color = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class GameTheme:
    """集中保存界面颜色，避免颜色常量散落在 Pygame 主循环中。"""

    background: Color
    panel: Color
    panel_light: Color
    ink: Color
    muted: Color
    grid: Color
    success: Color
    danger: Color
    accent: Color
    arrow_palette: tuple[Color, ...]


DARK_THEME = GameTheme(
    background=(61, 69, 96),
    panel=(52, 59, 84),
    panel_light=(75, 84, 116),
    ink=(247, 249, 255),
    muted=(171, 181, 211),
    grid=(112, 122, 153),
    success=(76, 220, 184),
    danger=(255, 105, 117),
    accent=(57, 208, 194),
    arrow_palette=(
        (255, 204, 45),
        (242, 139, 146),
        (115, 190, 240),
        (119, 211, 167),
        (194, 133, 219),
        (239, 168, 104),
        (147, 139, 235),
        (113, 193, 187),
        (126, 186, 43),
        (235, 126, 179),
    ),
)


def assign_arrow_colors(
    level: Level,
    palette: tuple[Color, ...],
    seed: int,
) -> dict[str, Color]:
    """为箭头确定性配色，并保证正交相邻的不同箭头不使用同色。

    先建立箭头邻接图，再按邻居数量从多到少贪心着色。当前棋盘邻接图使用
    十种颜色有充分余量；若未来极端布局耗尽颜色，会选择冲突数最少的颜色。
    """
    if not palette:
        raise ValueError("箭头调色板不能为空")

    board = level.create_board()
    neighbours: dict[str, set[str]] = {
        arrow.arrow_id: set() for arrow in level.arrows
    }
    for row, col in level.layout.playable_cells:
        current = board.arrow_at((row, col))
        if current is None:
            continue
        for cell in ((row + 1, col), (row, col + 1)):
            other = board.arrow_at(cell)
            if other is None or other.arrow_id == current.arrow_id:
                continue
            neighbours[current.arrow_id].add(other.arrow_id)
            neighbours[other.arrow_id].add(current.arrow_id)

    randomizer = random.Random(seed)
    order = [arrow.arrow_id for arrow in level.arrows]
    randomizer.shuffle(order)
    order.sort(key=lambda arrow_id: len(neighbours[arrow_id]), reverse=True)

    color_indexes: dict[str, int] = {}
    for arrow_id in order:
        used = {
            color_indexes[neighbour]
            for neighbour in neighbours[arrow_id]
            if neighbour in color_indexes
        }
        choices = [index for index in range(len(palette)) if index not in used]
        if choices:
            color_indexes[arrow_id] = randomizer.choice(choices)
            continue

        # 理论上的兜底：选择与已着色邻居冲突最少的颜色。
        color_indexes[arrow_id] = min(
            range(len(palette)),
            key=lambda index: sum(
                color_indexes.get(neighbour) == index
                for neighbour in neighbours[arrow_id]
            ),
        )

    return {
        arrow_id: palette[color_index]
        for arrow_id, color_index in color_indexes.items()
    }
