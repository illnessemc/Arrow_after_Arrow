"""可配置的在线关卡生成器。

生成器支持交错条带、嵌套环、多区域混合和全棋盘交织构图，再按形状权重在
合法位置切分为长短不一的箭头。全局模式还会为每个片段选择可出界方向；所有
候选最终都由求解器独立验证，固定种子保证同一关每次启动完全一致。
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
    GLOBAL_WEAVE = auto()


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
class ArrowShapeLimits:
    """按转角数量限制长度，防止生成贯穿大半棋盘的直线箭头。"""

    max_straight_length: int = 6
    max_single_turn_length: int = 14
    max_axis_span: int = 9

    def __post_init__(self) -> None:
        if self.max_straight_length < 2:
            raise ValueError("直线箭头长度上限不能小于 2")
        if self.max_single_turn_length < self.max_straight_length:
            raise ValueError("单转角箭头上限不能短于直线箭头上限")
        if self.max_axis_span < 2:
            raise ValueError("箭头单轴跨度上限不能小于 2")

    def allows(self, length: int, turn_category: int, axis_span: int) -> bool:
        """长直线被拒绝；更长的箭头必须包含至少两个转角。"""
        if axis_span > self.max_axis_span:
            return False
        if turn_category == 0:
            return length <= self.max_straight_length
        if turn_category == 1:
            return length <= self.max_single_turn_length
        return True


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
    path_mix_factor: float = 2.0
    coverage_pattern: CoveragePattern = CoveragePattern.INTERLEAVED
    shape_mix: ArrowShapeMix = ArrowShapeMix()
    shape_limits: ArrowShapeLimits = ArrowShapeLimits()
    nested_region_ratio: float = 0.35
    vertical_region_ratio: float = 0.5
    max_generation_attempts: int = 40
    playable_cells: frozenset[Cell] | None = None
    time_limit_seconds: float = 150.0

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
        if self.time_limit_seconds <= 0:
            raise ValueError("关卡时限必须大于 0")
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
class DependencyMetrics:
    """描述初始棋盘的箭头制约网络，用于拒绝彼此孤立的关卡。"""

    arrow_count: int
    edge_count: int
    initial_safe_count: int
    constrained_count: int
    cross_direction_edges: int
    same_direction_only_count: int
    same_direction_first_count: int
    longest_same_direction_chain: int
    largest_component_size: int

    @property
    def average_dependencies(self) -> float:
        return self.edge_count / self.arrow_count if self.arrow_count else 0.0

    @property
    def initial_safe_ratio(self) -> float:
        return self.initial_safe_count / self.arrow_count if self.arrow_count else 0.0

    @property
    def cross_direction_ratio(self) -> float:
        return self.cross_direction_edges / self.edge_count if self.edge_count else 0.0

    @property
    def same_direction_only_ratio(self) -> float:
        if not self.constrained_count:
            return 0.0
        return self.same_direction_only_count / self.constrained_count

    @property
    def same_direction_first_ratio(self) -> float:
        if not self.constrained_count:
            return 0.0
        return self.same_direction_first_count / self.constrained_count

    @property
    def largest_component_ratio(self) -> float:
        return self.largest_component_size / self.arrow_count if self.arrow_count else 0.0


@dataclass(frozen=True, slots=True)
class LevelQualityPolicy:
    """自动关卡的最低质量门槛，避免生成单一方向的重复堆叠。"""

    min_secondary_axis_ratio: float = 0.25
    min_bent_arrow_ratio: float = 0.3
    min_short_arrow_ratio: float = 0.1
    min_shape_category_ratio: float = 0.1
    max_average_choice_ratio: float = 0.18
    min_each_direction: int = 2
    max_repeated_shape_ratio: float = 0.2
    min_average_dependencies: float = 2.0
    max_initial_safe_ratio: float = 0.2
    min_cross_direction_dependency_ratio: float = 0.65
    max_same_direction_only_ratio: float = 0.1
    max_same_direction_first_ratio: float = 0.4
    max_same_direction_chain: int = 3
    min_largest_dependency_component_ratio: float = 0.9

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

        dependencies = self.dependency_metrics(level)
        if dependencies.average_dependencies < self.min_average_dependencies:
            return False
        if dependencies.initial_safe_ratio > self.max_initial_safe_ratio:
            return False
        if (
            dependencies.cross_direction_ratio
            < self.min_cross_direction_dependency_ratio
        ):
            return False
        if (
            dependencies.same_direction_only_ratio
            > self.max_same_direction_only_ratio
        ):
            return False
        if (
            dependencies.same_direction_first_ratio
            > self.max_same_direction_first_ratio
        ):
            return False
        if (
            dependencies.longest_same_direction_chain
            > self.max_same_direction_chain
        ):
            return False
        if (
            dependencies.largest_component_ratio
            < self.min_largest_dependency_component_ratio
        ):
            return False

        return report.average_choices / arrow_count <= self.max_average_choice_ratio

    @staticmethod
    def dependency_metrics(level: Level) -> DependencyMetrics:
        """扫描每支箭头的完整出界射线，建立有向依赖边和无向连通图。"""
        board = level.create_board()
        arrows = {arrow.arrow_id: arrow for arrow in level.arrows}
        edges: set[tuple[str, str]] = set()
        for arrow in level.arrows:
            for cell in board.cells_to_edge(arrow.head, arrow.direction):
                blocker = board.arrow_at(cell)
                if blocker is not None and blocker.arrow_id != arrow.arrow_id:
                    edges.add((arrow.arrow_id, blocker.arrow_id))

        constrained = {source for source, _ in edges}
        cross_direction_edges = sum(
            arrows[source].direction is not arrows[target].direction
            for source, target in edges
        )
        dependencies_by_source: dict[str, set[str]] = {
            arrow_id: set() for arrow_id in arrows
        }
        for source, target in edges:
            dependencies_by_source[source].add(target)
        same_direction_only_count = sum(
            bool(targets)
            and all(
                arrows[source].direction is arrows[target].direction
                for target in targets
            )
            for source, targets in dependencies_by_source.items()
        )
        same_direction_first_count = sum(
            blocker is not None and blocker.direction is arrow.direction
            for arrow in level.arrows
            for blocker in (board.first_blocker(arrow),)
        )
        same_direction_first = {
            arrow.arrow_id: blocker.arrow_id
            for arrow in level.arrows
            for blocker in (board.first_blocker(arrow),)
            if blocker is not None and blocker.direction is arrow.direction
        }
        longest_same_direction_chain = 0
        for arrow_id in arrows:
            visited_in_chain: set[str] = set()
            current: str | None = arrow_id
            chain_length = 0
            while current in same_direction_first and current not in visited_in_chain:
                visited_in_chain.add(current)
                chain_length += 1
                current = same_direction_first[current]
            if chain_length:
                # 边数加一才是链条实际包含的箭头数。
                chain_length += 1
            longest_same_direction_chain = max(
                longest_same_direction_chain,
                chain_length,
            )
        graph = {arrow_id: set() for arrow_id in arrows}
        for source, target in edges:
            graph[source].add(target)
            graph[target].add(source)

        visited: set[str] = set()
        largest_component = 0
        for root in graph:
            if root in visited:
                continue
            stack = [root]
            visited.add(root)
            component_size = 0
            while stack:
                current = stack.pop()
                component_size += 1
                for neighbour in graph[current]:
                    if neighbour not in visited:
                        visited.add(neighbour)
                        stack.append(neighbour)
            largest_component = max(largest_component, component_size)

        return DependencyMetrics(
            arrow_count=len(arrows),
            edge_count=len(edges),
            initial_safe_count=len(arrows) - len(constrained),
            constrained_count=len(constrained),
            cross_direction_edges=cross_direction_edges,
            same_direction_only_count=same_direction_only_count,
            same_direction_first_count=same_direction_first_count,
            longest_same_direction_chain=longest_same_direction_chain,
            largest_component_size=largest_component,
        )

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
                        spec.shape_limits,
                        spec.coverage_pattern is CoveragePattern.GLOBAL_WEAVE,
                        randomizer,
                    )
                )
            except ValueError:
                continue
            oriented_parts = self._orient_parts_for_exit(parts, layout, randomizer)
            if oriented_parts is None:
                continue

            builder = ManualLevelBuilder(
                spec.name,
                layout,
                role=LevelRole.FORMAL,
                intro=f"自动关卡 · {spec.rows}×{spec.cols} · 找到折线的释放顺序",
                mistake_limit=spec.mistake_limit,
                time_limit_seconds=spec.time_limit_seconds,
            )
            for index, cells in enumerate(oriented_parts, start=1):
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

    @staticmethod
    def _orient_parts_for_exit(
        parts: tuple[tuple[Cell, ...], ...],
        layout: BoardLayout,
        randomizer: random.Random,
    ) -> tuple[tuple[Cell, ...], ...] | None:
        """为全局切分结果选择方向，同时构造一条可行的移除顺序。

        每个未定向片段都尝试正向和反向；若某个端点沿末段方向扫描时没有
        遇到其他剩余片段，就可以把该方向固定并从临时占用中移除。移除只会
        减少阻挡，因此任意安全选择都不会破坏后续已经存在的机会。
        """
        owners = {
            cell: index
            for index, cells in enumerate(parts)
            for cell in cells
        }
        all_owners = dict(owners)
        remaining = set(range(len(parts)))
        oriented: list[tuple[Cell, ...] | None] = [None] * len(parts)
        oriented_steps: dict[int, tuple[int, int]] = {}
        direction_counts = {
            (-1, 0): 0,
            (1, 0): 0,
            (0, -1): 0,
            (0, 1): 0,
        }

        def exit_step(cells: tuple[Cell, ...]) -> tuple[int, int]:
            previous, head = cells[-2], cells[-1]
            return head[0] - previous[0], head[1] - previous[1]

        def can_exit(index: int, cells: tuple[Cell, ...]) -> bool:
            head = cells[-1]
            step = exit_step(cells)
            cursor = (head[0] + step[0], head[1] + step[1])
            while layout.contains(cursor):
                owner = owners.get(cursor)
                if owner is not None and owner != index:
                    return False
                cursor = (cursor[0] + step[0], cursor[1] + step[1])
            return True

        def dependency_ids(index: int, cells: tuple[Cell, ...]) -> list[int]:
            """返回该方向射线上已经安排为更早移除的箭头。"""
            head = cells[-1]
            step = exit_step(cells)
            cursor = (head[0] + step[0], head[1] + step[1])
            dependencies: list[int] = []
            while layout.contains(cursor):
                owner = all_owners.get(cursor)
                if owner is not None and owner != index and owner not in remaining:
                    if owner not in dependencies:
                        dependencies.append(owner)
                cursor = (cursor[0] + step[0], cursor[1] + step[1])
            return dependencies

        while remaining:
            candidates: list[tuple[int, tuple[Cell, ...]]] = []
            for index in remaining:
                forward = parts[index]
                backward = tuple(reversed(forward))
                if can_exit(index, forward):
                    candidates.append((index, forward))
                if can_exit(index, backward):
                    candidates.append((index, backward))
            if not candidates:
                return None

            def candidate_score(
                candidate: tuple[int, tuple[Cell, ...]],
            ) -> tuple[int, int, float, int, int, int, int]:
                index, cells = candidate
                step = exit_step(cells)
                dependencies = dependency_ids(index, cells)
                cross_direction = sum(
                    oriented_steps[dependency] != step
                    for dependency in dependencies
                )
                first_is_cross_direction = bool(dependencies) and (
                    oriented_steps[dependencies[0]] != step
                )
                same_direction = len(dependencies) - cross_direction
                cross_ratio = (
                    cross_direction / len(dependencies) if dependencies else 0.0
                )
                return (
                    int(bool(dependencies)),
                    int(first_is_cross_direction),
                    cross_ratio,
                    cross_direction,
                    -same_direction,
                    len(dependencies),
                    -direction_counts[step],
                )

            best_score = max(candidate_score(candidate) for candidate in candidates)
            best_candidates = [
                candidate
                for candidate in candidates
                if candidate_score(candidate) == best_score
            ]
            index, cells = randomizer.choice(best_candidates)
            oriented[index] = cells
            step = exit_step(cells)
            oriented_steps[index] = step
            direction_counts[step] += 1
            remaining.remove(index)
            for cell in parts[index]:
                owners.pop(cell, None)

        return tuple(cells for cells in oriented if cells is not None)

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
        elif spec.coverage_pattern is CoveragePattern.GLOBAL_WEAVE:
            global_path = self._whole_board_path(layout, randomizer)
            if global_path is not None:
                mixed_path = self._mix_path(
                    global_path,
                    len(global_path) * spec.path_mix_factor,
                    randomizer,
                )
                return (
                    self._break_long_runs(
                        mixed_path,
                        spec.shape_limits.max_straight_length,
                        randomizer,
                    ),
                )

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

    def _whole_board_path(
        self,
        layout: BoardLayout,
        randomizer: random.Random,
    ) -> tuple[Cell, ...] | None:
        """构造一条覆盖整个布局的连续路径，避免按区域分别生成箭头。"""
        if len(layout.playable_cells) == layout.rows * layout.cols:
            return self._rect_path(
                0,
                layout.rows,
                0,
                layout.cols,
                horizontal=randomizer.choice((True, False)),
                randomizer=randomizer,
            )
        return self._raised_layout_path(layout)

    @classmethod
    def _raised_layout_path(cls, layout: BoardLayout) -> tuple[Cell, ...] | None:
        """为上窄下宽的“凸”形布局拼接一条全局 Hamilton 路径。

        上部矩形使用蛇形路径，末端连接下部矩形 Hamilton 环上的相邻格。
        将环从连接点断开后，两部分会成为一条不重复、无断点的全图路径。
        其他异形布局返回 ``None``，继续使用通用降级策略。
        """
        spans: list[tuple[int, int]] = []
        for row in range(layout.rows):
            columns = sorted(
                col for cell_row, col in layout.playable_cells if cell_row == row
            )
            if not columns or columns != list(range(columns[0], columns[-1] + 1)):
                return None
            spans.append((columns[0], columns[-1] + 1))

        shoulder = next(
            (row for row in range(1, layout.rows) if spans[row] != spans[0]),
            None,
        )
        if shoulder is None:
            return None
        stem_left, stem_right = spans[0]
        if any(span != (stem_left, stem_right) for span in spans[:shoulder]):
            return None
        if any(span != (0, layout.cols) for span in spans[shoulder:]):
            return None

        stem_path = [
            (row, stem_left + col)
            for row in range(shoulder)
            for col in (
                range(stem_right - stem_left)
                if row % 2 == 0
                else range(stem_right - stem_left - 1, -1, -1)
            )
        ]
        target_col = stem_path[-1][1]
        body_cycle = cls._rectangle_cycle(
            shoulder,
            layout.rows,
            0,
            layout.cols,
        )
        if body_cycle is None:
            return None

        target = (shoulder, target_col)
        target_index = body_cycle.index(target)
        body_path = body_cycle[target_index:] + body_cycle[:target_index]
        if not cls._are_adjacent(stem_path[-1], body_path[0]):
            return None
        return tuple((*stem_path, *body_path))

    @staticmethod
    def _rectangle_cycle(
        top: int,
        bottom: int,
        left: int,
        right: int,
    ) -> tuple[Cell, ...] | None:
        """返回偶数宽或偶数高矩形的 Hamilton 环（末尾与开头相邻）。"""
        rows = bottom - top
        cols = right - left
        if rows < 2 or cols < 2:
            return None
        if cols % 2:
            if rows % 2:
                return None
            transposed = SerpentineLevelGenerator._rectangle_cycle(
                left,
                right,
                top,
                bottom,
            )
            if transposed is None:
                return None
            return tuple((col, row) for row, col in transposed)

        cycle: list[Cell] = [(top, col) for col in range(left, right)]
        current_at_bottom = False
        cycle.extend((row, right - 1) for row in range(top + 1, bottom))
        current_at_bottom = True
        for col in range(right - 2, left - 1, -1):
            if current_at_bottom:
                cycle.extend((row, col) for row in range(bottom - 1, top, -1))
            else:
                cycle.extend((row, col) for row in range(top + 1, bottom))
            current_at_bottom = not current_at_bottom
        return tuple(cycle)

    @staticmethod
    def _are_adjacent(first: Cell, second: Cell) -> bool:
        return abs(first[0] - second[0]) + abs(first[1] - second[1]) == 1

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
        steps: float,
        randomizer: random.Random,
    ) -> tuple[Cell, ...]:
        """从随机端点执行 backbite 变换，同时保持全覆盖和连续性。

        每次随机选择一个端点，把它接到相邻内部节点并翻转路径片段。双端混合
        避免棋盘远端保留原始蛇形条带；变换不会增删格子或破坏相邻关系。
        """
        mixed = list(path)
        positions = {cell: index for index, cell in enumerate(mixed)}

        for _ in range(round(steps)):
            if randomizer.choice((True, False)):
                mixed.reverse()
                positions = {cell: index for index, cell in enumerate(mixed)}
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

        # 再用局部 2-opt 把相邻的平行边换成垂直边。与只移动端点的
        # backbite 相比，它能直接打断棋盘内部残留的长直线走廊。
        positions = {cell: index for index, cell in enumerate(mixed)}
        for _ in range(round(steps)):
            first_index = randomizer.randrange(len(mixed) - 1)
            first, second = mixed[first_index], mixed[first_index + 1]
            step = second[0] - first[0], second[1] - first[1]
            perpendiculars = ((step[1], -step[0]), (-step[1], step[0]))
            p_row, p_col = randomizer.choice(perpendiculars)
            third = first[0] + p_row, first[1] + p_col
            fourth = second[0] + p_row, second[1] + p_col
            third_index = positions.get(third)
            if (
                third_index is None
                or third_index + 1 >= len(mixed)
                or mixed[third_index + 1] != fourth
                or abs(first_index - third_index) <= 1
            ):
                continue

            left = min(first_index, third_index) + 1
            right = max(first_index, third_index) + 1
            mixed[left:right] = reversed(mixed[left:right])
            for index in range(left, right):
                positions[mixed[index]] = index

        return tuple(mixed)

    @staticmethod
    def _break_long_runs(
        path: tuple[Cell, ...],
        maximum_cells: int,
        randomizer: random.Random,
    ) -> tuple[Cell, ...]:
        """用定向 2-opt 反复打断过长直线，避免之后被切成同向箭头链。"""
        mixed = list(path)
        positions = {cell: index for index, cell in enumerate(mixed)}

        def long_runs() -> list[tuple[int, int]]:
            runs: list[tuple[int, int]] = []
            start = 0
            previous_step: tuple[int, int] | None = None
            for edge_index, (first, second) in enumerate(zip(mixed, mixed[1:])):
                step = second[0] - first[0], second[1] - first[1]
                if previous_step is not None and step != previous_step:
                    if edge_index - start + 1 > maximum_cells:
                        runs.append((start, edge_index - 1))
                    start = edge_index
                previous_step = step
            if len(mixed) - start > maximum_cells:
                runs.append((start, len(mixed) - 2))
            return runs

        for _ in range(len(mixed) * 6):
            runs = long_runs()
            if not runs:
                break
            randomizer.shuffle(runs)
            changed = False
            for run_start, run_end in runs:
                edge_indices = list(range(run_start, run_end + 1))
                randomizer.shuffle(edge_indices)
                for first_index in edge_indices:
                    first, second = mixed[first_index], mixed[first_index + 1]
                    step = second[0] - first[0], second[1] - first[1]
                    perpendiculars = [
                        (step[1], -step[0]),
                        (-step[1], step[0]),
                    ]
                    randomizer.shuffle(perpendiculars)
                    for p_row, p_col in perpendiculars:
                        third = first[0] + p_row, first[1] + p_col
                        fourth = second[0] + p_row, second[1] + p_col
                        third_index = positions.get(third)
                        if (
                            third_index is None
                            or third_index + 1 >= len(mixed)
                            or mixed[third_index + 1] != fourth
                            or abs(first_index - third_index) <= 1
                        ):
                            continue
                        left = min(first_index, third_index) + 1
                        right = max(first_index, third_index) + 1
                        mixed[left:right] = reversed(mixed[left:right])
                        for index in range(left, right):
                            positions[mixed[index]] = index
                        changed = True
                        break
                    if changed:
                        break
                if changed:
                    break
            if not changed:
                break

        return tuple(mixed)

    def _split_path(
        self,
        path: tuple[Cell, ...],
        minimum: int,
        maximum: int,
        layout: BoardLayout,
        boundary_break_chance: float,
        shape_mix: ArrowShapeMix,
        shape_limits: ArrowShapeLimits,
        prefer_turn_cuts: bool,
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

        def axis_span(start: int, end: int) -> int:
            cells = path[start : end + 1]
            rows = [cell[0] for cell in cells]
            cols = [cell[1] for cell in cells]
            return max(max(rows) - min(rows) + 1, max(cols) - min(cols) + 1)

        # 在部分边界转角主动断开依赖链，产生多个同时可飞出的候选箭头。
        boundary_cuts = {
            end
            for end in range(1, count - 1)
            if points_outside(end) and randomizer.random() < boundary_break_chance
        }

        @lru_cache(maxsize=None)
        def partition(start: int) -> tuple[tuple[Cell, ...], ...] | None:
            remaining = count - start
            remaining_shape = turn_category(start, count - 1)
            if (
                minimum <= remaining <= maximum
                and shape_limits.allows(
                    remaining,
                    remaining_shape,
                    axis_span(start, count - 1),
                )
            ):
                return (path[start:],)

            candidates = [
                end
                for end in range(
                    start + minimum - 1,
                    min(start + maximum - 1, count - minimum - 1) + 1,
                )
                if (prefer_turn_cuts or is_straight_cut(end) or end in boundary_cuts)
                and shape_limits.allows(
                    end - start + 1,
                    turn_category(start, end),
                    axis_span(start, end),
                )
            ]
            randomizer.shuffle(candidates)
            desired_shape = shape_mix.choose_turn_category(randomizer)
            # 先匹配本段需要的形状类别；同类别内优先采用选中的边界断点。
            # 若首选形状无法完成后续切分，回溯仍会尝试其他候选。
            candidates.sort(
                key=lambda end: (
                    turn_category(start, end) != desired_shape,
                    is_straight_cut(end) if prefer_turn_cuts else False,
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
