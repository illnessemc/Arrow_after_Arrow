"""界面动画队列。

队列只管理动画生命周期和同一箭头的去重，不参与碰撞或消除判定。这样玩家
连续点击时，核心规则可以立即更新，表现层仍按点击顺序平滑播放。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator

from arrow_game.core import Arrow, Cell


class AnimationKind(Enum):
    FLY = auto()
    BLOCKED = auto()


@dataclass(slots=True)
class ArrowAnimation:
    """一次箭头反馈所需的不可丢失快照。"""

    kind: AnimationKind
    arrow: Arrow
    duration: float
    movement_cells: float
    trail_cells: tuple[Cell, ...] = ()
    elapsed: float = 0.0
    emitted_steps: int = 0

    @property
    def progress(self) -> float:
        return min(self.elapsed / self.duration, 1.0)

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration


class AnimationQueue:
    """先进先出的动画容器，同一箭头同一时刻最多排队一次。"""

    def __init__(self) -> None:
        self._items: deque[ArrowAnimation] = deque()
        self._arrow_ids: set[str] = set()

    @property
    def active(self) -> ArrowAnimation | None:
        return self._items[0] if self._items else None

    def contains(self, arrow_id: str) -> bool:
        return arrow_id in self._arrow_ids

    def append(self, animation: ArrowAnimation) -> bool:
        if animation.arrow.arrow_id in self._arrow_ids:
            return False
        self._items.append(animation)
        self._arrow_ids.add(animation.arrow.arrow_id)
        return True

    def update(self, dt: float) -> ArrowAnimation | None:
        """推进当前动画；完成时弹出并返回它。"""
        active = self.active
        if active is None:
            return None
        active.elapsed += dt
        if not active.done:
            return None
        completed = self._items.popleft()
        self._arrow_ids.discard(completed.arrow.arrow_id)
        return completed

    def clear(self) -> None:
        self._items.clear()
        self._arrow_ids.clear()

    def __bool__(self) -> bool:
        return bool(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[ArrowAnimation]:
        return iter(self._items)
