"""可配置的在线关卡生成器。

生成过程先铺出覆盖全棋盘的蛇形 Hamilton 路径，再在合法位置随机切分。
连续切口形成稳定的依赖链，少量朝向边界的切口产生多个可选入口；最终再由
求解器独立验证关卡。固定种子保证同一关每次启动完全一致。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

from arrow_game.core import BoardLayout, Direction, Level, LevelRole
from arrow_game.core.direction import Cell
from arrow_game.core.solver import LevelSolver, SolveReport

from .builders import ManualLevelBuilder


@dataclass(frozen=True, slots=True)
class GeneratedLevelSpec:
    """生成一关所需的少量参数，替代逐格手写箭头。"""

    name: str
    rows: int
    cols: int
    seed: int
    min_arrow_length: int = 4
    max_arrow_length: int = 11
    mistake_limit: int = 3
    boundary_break_chance: float = 0.3
    path_mix_factor: int = 2
    max_generation_attempts: int = 40

    def __post_init__(self) -> None:
        if self.rows < 4 or self.cols < 4:
            raise ValueError("自动生成棋盘至少为 4×4")
        if self.min_arrow_length < 2:
            raise ValueError("多格箭头的最短长度不能小于 2")
        if self.max_arrow_length < self.min_arrow_length:
            raise ValueError("最大箭头长度不能小于最短长度")
        if not 0.0 <= self.boundary_break_chance <= 1.0:
            raise ValueError("边界断链概率必须处于 0~1")
        if self.path_mix_factor < 0:
            raise ValueError("路径混合强度不能为负数")
        if self.max_generation_attempts <= 0:
            raise ValueError("生成尝试次数必须为正数")


@dataclass(frozen=True, slots=True)
class GeneratedLevel:
    """生成结果及其流程验证报告。"""

    level: Level
    report: SolveReport
    seed: int
    attempts: int


class LevelGenerator(Protocol):
    """自动关卡生成器接口，后续算法只需实现相同的入口。"""

    def generate(self, spec: GeneratedLevelSpec) -> GeneratedLevel:
        ...


class SerpentineLevelGenerator:
    """生成全覆盖、可复现且保证可解的长折线关卡。"""

    def __init__(self, solver: LevelSolver | None = None) -> None:
        self.solver = solver or LevelSolver()

    def generate(self, spec: GeneratedLevelSpec) -> GeneratedLevel:
        last_report: SolveReport | None = None

        # 混合后的折线路径可能形成额外的远距离依赖。使用确定性的多次候选
        # 生成并让求解器验收，比在生成器中复制一套规则判断更可靠。
        for attempt in range(1, spec.max_generation_attempts + 1):
            randomizer = random.Random(spec.seed * 1000 + attempt)
            path = self._board_path(spec.rows, spec.cols, randomizer)
            path = self._mix_path(
                path,
                spec.rows,
                spec.cols,
                len(path) * spec.path_mix_factor,
                randomizer,
            )
            try:
                parts = self._split_path(
                    path,
                    spec.min_arrow_length,
                    spec.max_arrow_length,
                    spec.rows,
                    spec.cols,
                    spec.boundary_break_chance,
                    randomizer,
                )
            except ValueError:
                continue

            builder = ManualLevelBuilder(
                spec.name,
                BoardLayout.rectangle(spec.rows, spec.cols),
                role=LevelRole.FORMAL,
                intro=f"自动关卡 · {spec.rows}×{spec.cols} · 找到折线的释放顺序",
                mistake_limit=spec.mistake_limit,
            )
            for index, cells in enumerate(parts, start=1):
                builder.add_path(f"P{spec.seed % 1000:03d}-{index:02d}", cells)

            level = builder.build()
            last_report = self.solver.solve(level)
            if last_report.solved:
                return GeneratedLevel(
                    level=level,
                    report=last_report,
                    seed=spec.seed,
                    attempts=attempt,
                )

        remaining = last_report.remaining_arrow_ids if last_report else ()
        raise ValueError(
            f"关卡 {spec.name} 在 {spec.max_generation_attempts} 次内未生成可解布局，"
            f"最后剩余箭头：{remaining}"
        )

    @staticmethod
    def _board_path(
        rows: int,
        cols: int,
        randomizer: random.Random,
    ) -> tuple[Cell, ...]:
        """生成覆盖矩形的连续蛇形路径，并随机改变主方向和镜像。"""
        horizontal = randomizer.choice((True, False))
        if horizontal:
            path = [
                (row, col)
                for row in range(rows)
                for col in (
                    range(cols) if row % 2 == 0 else range(cols - 1, -1, -1)
                )
            ]
        else:
            path = [
                (row, col)
                for col in range(cols)
                for row in (
                    range(rows) if col % 2 == 0 else range(rows - 1, -1, -1)
                )
            ]

        if randomizer.choice((True, False)):
            path = [(rows - 1 - row, col) for row, col in path]
        if randomizer.choice((True, False)):
            path = [(row, cols - 1 - col) for row, col in path]
        if randomizer.choice((True, False)):
            path.reverse()
        return tuple(path)

    @staticmethod
    def _mix_path(
        path: tuple[Cell, ...],
        rows: int,
        cols: int,
        steps: int,
        randomizer: random.Random,
    ) -> tuple[Cell, ...]:
        """用 backbite 变换打散规则蛇形，同时保持全覆盖和连续性。

        每次把路径起点接到一个相邻的内部节点，并翻转二者之间的路径片段。
        变换不会增删格子，也不会破坏相邻关系；末端及末段保持不变，因此最终
        箭头仍天然朝向棋盘外。相比完全回溯搜索，这种方式耗时稳定。
        """
        mixed = list(path)
        positions = {cell: index for index, cell in enumerate(mixed)}

        for _ in range(steps):
            row, col = mixed[0]
            neighbours = (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            )
            candidates = [
                positions[cell]
                for cell in neighbours
                if 2 <= positions.get(cell, -1) < len(mixed) - 1
            ]
            if not candidates:
                continue

            cut = randomizer.choice(candidates)
            mixed[:cut] = reversed(mixed[:cut])
            # 只有翻转的前缀下标发生变化，无需重建整个索引。
            for index in range(cut):
                positions[mixed[index]] = index

        return tuple(mixed)

    def _split_path(
        self,
        path: tuple[Cell, ...],
        minimum: int,
        maximum: int,
        rows: int,
        cols: int,
        boundary_break_chance: float,
        randomizer: random.Random,
    ) -> tuple[tuple[Cell, ...], ...]:
        """在合法位置随机切分路径，并通过回溯保证能完整切到终点。"""
        count = len(path)

        def is_straight_cut(end: int) -> bool:
            if end >= count - 1:
                return True
            previous, current, following = path[end - 1], path[end], path[end + 1]
            before = (current[0] - previous[0], current[1] - previous[1])
            after = (following[0] - current[0], following[1] - current[1])
            return before == after

        def points_outside(end: int) -> bool:
            """判断箭头若在此处结束，最后一段是否正好指向棋盘外。"""
            previous, current = path[end - 1], path[end]
            step = (current[0] - previous[0], current[1] - previous[1])
            next_cell = (current[0] + step[0], current[1] + step[1])
            return not (0 <= next_cell[0] < rows and 0 <= next_cell[1] < cols)

        # 在部分边界转角主动断开依赖链，产生多个同时可飞出的候选箭头。
        boundary_cuts = {
            end
            for end in range(1, count - 1)
            if points_outside(end) and randomizer.random() < boundary_break_chance
        }

        def partition(start: int) -> list[tuple[Cell, ...]] | None:
            remaining = count - start
            if minimum <= remaining <= maximum:
                return [path[start:]]

            candidates = [
                end
                for end in range(
                    start + minimum - 1,
                    min(start + maximum - 1, count - minimum - 1) + 1,
                )
                if is_straight_cut(end) or end in boundary_cuts
            ]
            randomizer.shuffle(candidates)
            # 随机顺序相同时优先尝试选中的边界断点，确保参数确实影响分支数。
            candidates.sort(key=lambda end: end not in boundary_cuts)
            for end in candidates:
                tail = partition(end + 1)
                if tail is not None:
                    return [path[start : end + 1], *tail]
            return None

        parts = partition(0)
        if parts is None:
            raise ValueError(
                f"无法用长度 {minimum}~{maximum} 切分 {count} 格路径"
            )
        return tuple(parts)
