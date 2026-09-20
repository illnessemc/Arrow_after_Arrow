"""可配置的在线关卡生成器。

生成器支持交错条带、由外向内的嵌套环以及多区域混合构图，再按形状权重在
合法位置切分为长短不一的箭头。所有候选都由求解器独立验证，固定种子保证
同一关每次启动完全一致。
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache
from typing import Protocol

from arrow_game.core import BoardLayout, Direction, Level, LevelRole
from arrow_game.core.direction import Cell
from arrow_game.core.solver import LevelSolver, SolveReport

from .builders import ManualLevelBuilder


class CoveragePattern(Enum):
    """全覆盖路径的结构类型，便于后续继续增加关卡构图算法。"""

    INTERLEAVED = auto()
    NESTED_RINGS = auto()
    MIXED_REGIONS = auto()


@dataclass(frozen=True, slots=True)
class ArrowShapeMix:
    """切分路径时三类箭头的相对权重，而不是要求精确百分比。"""

    straight: float = 0.3
    single_turn: float = 0.4
    multi_turn: float = 0.3

    def __post_init__(self) -> None:
        weights = (self.straight, self.single_turn, self.multi_turn)
        if any(weight < 0 for weight in weights) or sum(weights) <= 0:
            raise ValueError("箭头类型权重不能为负，且至少有一项大于 0")

    def choose_turn_category(self, randomizer: random.Random) -> int:
        """返回 0、1、2，分别表示直线、单转角和多转角。"""
        return randomizer.choices(
            (0, 1, 2),
            weights=(self.straight, self.single_turn, self.multi_turn),
            k=1,
        )[0]


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
    coverage_pattern: CoveragePattern = CoveragePattern.INTERLEAVED
    shape_mix: ArrowShapeMix = ArrowShapeMix()
    nested_region_ratio: float = 0.35
    vertical_region_ratio: float = 0.5
    max_generation_attempts: int = 40
    playable_cells: frozenset[Cell] | None = None

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
        if not 0.0 <= self.nested_region_ratio <= 1.0:
            raise ValueError("嵌套区域比例必须处于 0~1")
        if not 0.0 <= self.vertical_region_ratio <= 1.0:
            raise ValueError("纵向区域比例必须处于 0~1")
        if self.max_generation_attempts <= 0:
            raise ValueError("生成尝试次数必须为正数")
        if self.playable_cells is not None:
            # 交给 BoardLayout 复用边界和空布局校验。
            BoardLayout(self.rows, self.cols, self.playable_cells)

    def create_layout(self) -> BoardLayout:
        """创建本规格使用的布局；未提供掩码时使用完整矩形。"""
        if self.playable_cells is None:
            return BoardLayout.rectangle(self.rows, self.cols)
        return BoardLayout(self.rows, self.cols, self.playable_cells)


@dataclass(frozen=True, slots=True)
class GeneratedLevel:
    """生成结果及其流程验证报告。"""

    level: Level
    report: SolveReport
    seed: int
    attempts: int


@dataclass(frozen=True, slots=True)
class LevelQualityPolicy:
    """自动关卡的最低质量门槛，避免生成单一方向的重复堆叠。"""

    min_secondary_axis_ratio: float = 0.3
    min_bent_arrow_ratio: float = 0.3
    min_short_arrow_ratio: float = 0.1
    min_shape_category_ratio: float = 0.1
    max_average_choice_ratio: float = 0.18
    min_each_direction: int = 2
    max_repeated_shape_ratio: float = 0.2

    def accepts(self, level: Level, report: SolveReport) -> bool:
        arrow_count = len(level.arrows)
        if arrow_count < 16:
            return True

        horizontal = sum(
            arrow.direction in (Direction.LEFT, Direction.RIGHT)
            for arrow in level.arrows
        )
        vertical = arrow_count - horizontal
        if min(horizontal, vertical) / arrow_count < self.min_secondary_axis_ratio:
            return False

        direction_counts = {
            direction: sum(arrow.direction is direction for arrow in level.arrows)
            for direction in Direction
        }
        if min(direction_counts.values()) < self.min_each_direction:
            return False

        bent = sum(self._turn_count(arrow.cells) > 0 for arrow in level.arrows)
        if bent / arrow_count < self.min_bent_arrow_ratio:
            return False

        short = sum(len(arrow.cells) <= 4 for arrow in level.arrows)
        if short / arrow_count < self.min_short_arrow_ratio:
            return False

        shape_categories = Counter(
            min(self._turn_count(arrow.cells), 2) for arrow in level.arrows
        )
        if any(
            shape_categories[category] / arrow_count < self.min_shape_category_ratio
            for category in (0, 1, 2)
        ):
            return False

        # 忽略整体朝向，只比较各直线段长度与左右转序列。这样同一形状旋转后
        # 仍会被识别为重复，防止整关堆满同长度的 U 形或直线箭头。
        shape_counts = Counter(
            self._shape_signature(arrow.cells) for arrow in level.arrows
        )
        if max(shape_counts.values()) / arrow_count > self.max_repeated_shape_ratio:
            return False

        return report.average_choices / arrow_count <= self.max_average_choice_ratio

    @staticmethod
    def _turn_count(cells: tuple[Cell, ...]) -> int:
        return sum(
            (
                cells[index][0] - cells[index - 1][0],
                cells[index][1] - cells[index - 1][1],
            )
            != (
                cells[index + 1][0] - cells[index][0],
                cells[index + 1][1] - cells[index][1],
            )
            for index in range(1, len(cells) - 1)
        )

    @staticmethod
    def _shape_signature(cells: tuple[Cell, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
        """返回与整体旋转无关的形状签名：段长序列和转向序列。"""
        steps = [
            (following[0] - current[0], following[1] - current[1])
            for current, following in zip(cells, cells[1:])
        ]
        runs: list[tuple[tuple[int, int], int]] = []
        for step in steps:
            if not runs or runs[-1][0] != step:
                runs.append((step, 1))
            else:
                runs[-1] = (step, runs[-1][1] + 1)
        turns = tuple(
            first[0] * second[1] - first[1] * second[0]
            for (first, _), (second, _) in zip(runs, runs[1:])
        )
        return tuple(length for _, length in runs), turns


class LevelGenerator(Protocol):
    """自动关卡生成器接口，后续算法只需实现相同的入口。"""

    def generate(self, spec: GeneratedLevelSpec) -> GeneratedLevel:
        ...


class SerpentineLevelGenerator:
    """生成全覆盖、可复现且保证可解的多结构折线关卡。"""

    def __init__(
        self,
        solver: LevelSolver | None = None,
        quality_policy: LevelQualityPolicy | None = None,
    ) -> None:
        self.solver = solver or LevelSolver()
        self.quality_policy = quality_policy or LevelQualityPolicy()

    def generate(self, spec: GeneratedLevelSpec) -> GeneratedLevel:
        last_report: SolveReport | None = None

        # 混合后的折线路径可能形成额外的远距离依赖。使用确定性的多次候选
        # 生成并让求解器验收，比在生成器中复制一套规则判断更可靠。
        for attempt in range(1, spec.max_generation_attempts + 1):
            randomizer = random.Random(spec.seed * 1000 + attempt)
            layout = spec.create_layout()
            coverage_paths = self._coverage_paths(layout, spec, randomizer)
            try:
                parts = tuple(
                    part
                    for path in coverage_paths
                    for part in self._split_path(
                        path,
                        min(spec.min_arrow_length, len(path)),
                        min(spec.max_arrow_length, len(path)),
                        layout,
                        spec.boundary_break_chance,
                        spec.shape_mix,
                        randomizer,
                    )
                )
            except ValueError:
                continue

            builder = ManualLevelBuilder(
                spec.name,
                layout,
                role=LevelRole.FORMAL,
                intro=f"自动关卡 · {spec.rows}×{spec.cols} · 找到折线的释放顺序",
                mistake_limit=spec.mistake_limit,
            )
            for index, cells in enumerate(parts, start=1):
                builder.add_path(f"P{spec.seed % 1000:03d}-{index:02d}", cells)

            level = builder.build()
            last_report = self.solver.solve(level)
            quality_ok = self.quality_policy.accepts(level, last_report)
            if last_report.solved and quality_ok:
                return GeneratedLevel(
                    level=level,
                    report=last_report,
                    seed=spec.seed,
                    attempts=attempt,
                )

        remaining = last_report.remaining_arrow_ids if last_report else ()
        raise ValueError(
            f"关卡 {spec.name} 在 {spec.max_generation_attempts} 次内未生成满足"
            f"可解性与质量门槛的布局，"
            f"最后剩余箭头：{remaining}"
        )

    def _coverage_paths(
        self,
        layout: BoardLayout,
        spec: GeneratedLevelSpec,
        randomizer: random.Random,
    ) -> tuple[tuple[Cell, ...], ...]:
        """为布局生成一组互不重叠、完整覆盖的连续路径。"""
        if spec.coverage_pattern is CoveragePattern.NESTED_RINGS:
            nested_paths = self._nested_ring_paths(layout)
            if nested_paths is not None:
                return nested_paths
        elif spec.coverage_pattern is CoveragePattern.MIXED_REGIONS:
            mixed_paths = self._mixed_region_paths(layout, spec, randomizer)
            if mixed_paths is not None:
                return mixed_paths

        bands = self._rectangular_bands(layout)
        if bands is not None:
            paths: list[tuple[Cell, ...]] = []
            for index, (top, bottom, left, right) in enumerate(bands):
                path = self._rect_path(
                    top,
                    bottom,
                    left,
                    right,
                    horizontal=index % 2 == 0,
                    randomizer=randomizer,
                )
                paths.append(
                    self._mix_path(
                        path,
                        len(path) * spec.path_mix_factor,
                        randomizer,
                    )
                )
            return tuple(paths)
        return self._row_run_paths(layout, randomizer)

    def _mixed_region_paths(
        self,
        layout: BoardLayout,
        spec: GeneratedLevelSpec,
        randomizer: random.Random,
    ) -> tuple[tuple[Cell, ...], ...] | None:
        """在同一关中混合局部嵌套、横向折返和纵向折返区域。

        区域全部横跨棋盘宽度，路径最终仍可朝左右边界释放；这样获得局部
        图案变化的同时，不需要为每种图案复制一套特殊碰撞规则。
        """
        if len(layout.playable_cells) != layout.rows * layout.cols:
            return None

        # 用 4~7 行的非等高区域打破固定条带节奏，并确保最后一块不太窄。
        bands: list[tuple[int, int]] = []
        top = 0
        while top < layout.rows:
            remaining = layout.rows - top
            if remaining <= 8:
                height = remaining
            else:
                maximum = min(7, remaining - 4)
                height = randomizer.randint(4, maximum)
            bands.append((top, top + height))
            top += height

        nested_count = round(len(bands) * spec.nested_region_ratio)
        if 0 < spec.nested_region_ratio < 1 and len(bands) > 1:
            nested_count = min(len(bands) - 1, max(1, nested_count))
        nested_indices = set(randomizer.sample(range(len(bands)), nested_count))

        paths: list[tuple[Cell, ...]] = []
        for index, (band_top, band_bottom) in enumerate(bands):
            if index in nested_indices:
                paths.extend(
                    self._nested_rect_paths(
                        band_top,
                        band_bottom,
                        0,
                        layout.cols,
                    )
                )
                continue

            vertical = randomizer.random() < spec.vertical_region_ratio
            path = self._rect_path(
                band_top,
                band_bottom,
                0,
                layout.cols,
                horizontal=not vertical,
                randomizer=randomizer,
            )
            paths.append(
                self._mix_path(
                    path,
                    len(path) * spec.path_mix_factor,
                    randomizer,
                )
            )
        return tuple(paths)

    @staticmethod
    def _nested_ring_paths(
        layout: BoardLayout,
    ) -> tuple[tuple[Cell, ...], ...] | None:
        """把完整矩形逐层剥成向内嵌套的连续环形路径。

        每一层从左边开始绕行，并在左上角以向左的方向结束。外层箭头先
        飞出后，内层路径才获得出口，因此视觉上的“包围”同时对应真实依赖。
        单行或单列的中心区域也会生成一条连续路径，不留下空格。
        """
        if len(layout.playable_cells) != layout.rows * layout.cols:
            return None

        return SerpentineLevelGenerator._nested_rect_paths(
            0,
            layout.rows,
            0,
            layout.cols,
        )

    @staticmethod
    def _nested_rect_paths(
        top: int,
        bottom: int,
        left: int,
        right: int,
    ) -> tuple[tuple[Cell, ...], ...]:
        """为一个矩形区域生成逐层向内的环，边界参数使用左闭右开。"""
        bottom -= 1
        right -= 1

        paths: list[tuple[Cell, ...]] = []
        layer_index = 0
        while top <= bottom and left <= right:
            if top == bottom:
                path = tuple((top, col) for col in range(right, left - 1, -1))
                paths.append(path if layer_index % 2 == 0 else tuple(reversed(path)))
            elif left == right:
                path = tuple((row, left) for row in range(bottom, top - 1, -1))
                paths.append(path if layer_index % 2 == 0 else tuple(reversed(path)))
            else:
                ring = [
                    *((row, left) for row in range(top + 1, bottom + 1)),
                    *((bottom, col) for col in range(left + 1, right + 1)),
                    *((row, right) for row in range(bottom - 1, top - 1, -1)),
                    *((top, col) for col in range(right - 1, left - 1, -1)),
                ]
                if layer_index % 2:
                    # 奇数层水平镜像，使相邻环从相反侧打开，减少同构重复。
                    ring = [(row, left + right - col) for row, col in ring]
                paths.append(tuple(ring))
            top += 1
            bottom -= 1
            left += 1
            right -= 1
            layer_index += 1
        return tuple(paths)

    @staticmethod
    def _rectangular_bands(
        layout: BoardLayout,
    ) -> tuple[tuple[int, int, int, int], ...] | None:
        """把行凸布局识别为矩形带，并将过高区域再一分为二。"""
        raw_bands: list[tuple[int, int, int, int]] = []
        current: tuple[int, int, int] | None = None
        for row in range(layout.rows):
            columns = sorted(
                col for cell_row, col in layout.playable_cells if cell_row == row
            )
            if not columns or columns != list(range(columns[0], columns[-1] + 1)):
                return None
            signature = (columns[0], columns[-1] + 1)
            if current is None:
                current = (row, *signature)
            elif signature != current[1:]:
                raw_bands.append((current[0], row, current[1], current[2]))
                current = (row, *signature)
        if current is not None:
            raw_bands.append((current[0], layout.rows, current[1], current[2]))

        if len(layout.playable_cells) != layout.rows * layout.cols:
            shaped_bands: list[tuple[int, int, int, int]] = []
            for top, bottom, left, right in raw_bands:
                if bottom - top >= 16:
                    middle = top + (bottom - top) // 2
                    shaped_bands.extend(
                        ((top, middle, left, right), (middle, bottom, left, right))
                    )
                else:
                    shaped_bands.append((top, bottom, left, right))
            return tuple(shaped_bands)

        bands: list[tuple[int, int, int, int]] = []
        for top, bottom, left, right in raw_bands:
            cursor = top
            # 控制每个区域高度，令横向和纵向路径在整张地图中多次交替，
            # 而不是简单形成“上半全横、下半全竖”的两块堆叠。
            while bottom - cursor > 7:
                bands.append((cursor, cursor + 6, left, right))
                cursor += 6
            bands.append((cursor, bottom, left, right))
        return tuple(bands)

    @staticmethod
    def _rect_path(
        top: int,
        bottom: int,
        left: int,
        right: int,
        *,
        horizontal: bool,
        randomizer: random.Random,
    ) -> tuple[Cell, ...]:
        """按指定主方向生成覆盖一个矩形带的连续路径。"""
        rows = bottom - top
        cols = right - left
        if horizontal:
            path = [
                (top + row, left + col)
                for row in range(rows)
                for col in (
                    range(cols) if row % 2 == 0 else range(cols - 1, -1, -1)
                )
            ]
        else:
            path = [
                (top + row, left + col)
                for col in range(cols)
                for row in (
                    range(rows) if col % 2 == 0 else range(rows - 1, -1, -1)
                )
            ]
        if randomizer.choice((True, False)):
            path.reverse()
        return tuple(path)

    @staticmethod
    def _row_run_paths(
        layout: BoardLayout,
        randomizer: random.Random,
    ) -> tuple[tuple[Cell, ...], ...]:
        """把异形棋盘拆成连续行区段，作为可靠的全覆盖降级策略。

        这种策略不假设棋盘必须是矩形，因此凸字形、缺角和带空洞布局都能
        生成。每个区段至少需要两个格子，以维持当前多格箭头约束。
        """
        paths: list[tuple[Cell, ...]] = []
        for row in range(layout.rows):
            columns = sorted(col for cell_row, col in layout.playable_cells if cell_row == row)
            if not columns:
                continue

            run: list[int] = [columns[0]]
            for col in columns[1:]:
                if col == run[-1] + 1:
                    run.append(col)
                    continue
                if len(run) < 2:
                    raise ValueError("异形棋盘包含无法组成多格箭头的孤立格")
                if randomizer.choice((True, False)):
                    run.reverse()
                paths.append(tuple((row, item) for item in run))
                run = [col]

            if len(run) < 2:
                raise ValueError("异形棋盘包含无法组成多格箭头的孤立格")
            if randomizer.choice((True, False)):
                run.reverse()
            paths.append(tuple((row, item) for item in run))
        return tuple(paths)

    @staticmethod
    def _mix_path(
        path: tuple[Cell, ...],
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
        layout: BoardLayout,
        boundary_break_chance: float,
        shape_mix: ArrowShapeMix,
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
            return not layout.contains(next_cell)

        def turn_category(start: int, end: int) -> int:
            """把候选片段归为直线、单转角或多转角三类。"""
            turns = 0
            for index in range(start + 1, end):
                before = (
                    path[index][0] - path[index - 1][0],
                    path[index][1] - path[index - 1][1],
                )
                after = (
                    path[index + 1][0] - path[index][0],
                    path[index + 1][1] - path[index][1],
                )
                turns += before != after
            return min(turns, 2)

        # 在部分边界转角主动断开依赖链，产生多个同时可飞出的候选箭头。
        boundary_cuts = {
            end
            for end in range(1, count - 1)
            if points_outside(end) and randomizer.random() < boundary_break_chance
        }

        @lru_cache(maxsize=None)
        def partition(start: int) -> tuple[tuple[Cell, ...], ...] | None:
            remaining = count - start
            if minimum <= remaining <= maximum:
                return (path[start:],)

            candidates = [
                end
                for end in range(
                    start + minimum - 1,
                    min(start + maximum - 1, count - minimum - 1) + 1,
                )
                if is_straight_cut(end) or end in boundary_cuts
            ]
            randomizer.shuffle(candidates)
            desired_shape = shape_mix.choose_turn_category(randomizer)
            # 先匹配本段需要的形状类别；同类别内优先采用选中的边界断点。
            # 若首选形状无法完成后续切分，回溯仍会尝试其他候选。
            candidates.sort(
                key=lambda end: (
                    turn_category(start, end) != desired_shape,
                    end not in boundary_cuts,
                )
            )
            for end in candidates:
                tail = partition(end + 1)
                if tail is not None:
                    return (path[start : end + 1], *tail)
            return None

        parts = partition(0)
        if parts is None:
            raise ValueError(
                f"无法用长度 {minimum}~{maximum} 切分 {count} 格路径"
            )
        return parts
