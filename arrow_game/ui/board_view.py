"""棋盘坐标、圆角箭头和棋盘内动画绘制。"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pygame

from arrow_game.core import Arrow, GameBoard, Level

from .animation import AnimationKind, AnimationQueue, ArrowAnimation
from .theme import COLLISION_RED, DARK_THEME

ARROW_RENDER_SCALE = 5
GRID = DARK_THEME.grid
SUCCESS = DARK_THEME.success


class BoardView:
    """持有棋盘的像素布局和静态箭头渲染缓存。"""

    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.cell_size = 0
        self._arrow_cache: dict[str, tuple[pygame.Surface, tuple[int, int]]] = {}

    def clear(self) -> None:
        self._arrow_cache.clear()

    def layout(self, level: Level) -> None:
        available_width = self.surface.get_width() - 92
        available_height = 850
        self.cell_size = min(
            46,
            int(min(available_width / level.cols, available_height / level.rows)),
        )
        width = self.cell_size * level.cols
        height = self.cell_size * level.rows
        self.rect = pygame.Rect(
            (self.surface.get_width() - width) // 2,
            125 + (available_height - height) // 2,
            width,
            height,
        )

    def cell_center(self, cell: tuple[int, int]) -> pygame.Vector2:
        row, col = cell
        return pygame.Vector2(
            self.rect.x + (col + 0.5) * self.cell_size,
            self.rect.y + (row + 0.5) * self.cell_size,
        )

    def arrow_at_pixel(
        self,
        pos: tuple[int, int],
        board: GameBoard,
    ) -> Arrow | None:
        if not self.rect.collidepoint(pos):
            return None
        col = (pos[0] - self.rect.x) // self.cell_size
        row = (pos[1] - self.rect.y) // self.cell_size
        return board.arrow_at((row, col))

    def draw_board_dots(
        self,
        board: GameBoard,
        animations: AnimationQueue,
    ) -> None:
        """只在视觉上未被箭头覆盖的可玩格中心绘制棋盘点。"""
        visually_occupied = set(board.occupied_cells)
        for animation in animations:
            if animation.kind is AnimationKind.FLY:
                visually_occupied.update(animation.arrow.cells)

        radius = max(1, round(self.cell_size * 0.055))
        for cell in board.layout.playable_cells:
            if cell not in visually_occupied:
                pygame.draw.circle(self.surface, GRID, self.cell_center(cell), radius)

    def draw_fly_trail(
        self,
        animation: ArrowAnimation,
        board: GameBoard,
    ) -> None:
        """让箭尾经过的棋盘点短暂放大，再平滑恢复。"""
        movement = self.ease(animation.progress) * animation.movement_cells
        path_cells = [
            *animation.arrow.cells,
            *board.cells_to_edge(
                animation.arrow.head,
                animation.arrow.direction,
            ),
        ]
        base_radius = max(1, round(self.cell_size * 0.055))
        pulse_radius = max(base_radius + 2, round(self.cell_size * 0.16))
        pulse_duration = 1.8
        for index, cell in enumerate(path_cells):
            age = movement - (index + 0.35)
            if age < 0 or not board.layout.contains(cell):
                continue
            if age < pulse_duration:
                phase = age / pulse_duration
                strength = math.sin(math.pi * phase) ** 2
                radius = round(
                    base_radius + (pulse_radius - base_radius) * strength
                )
            else:
                radius = base_radius
            pygame.draw.circle(self.surface, GRID, self.cell_center(cell), radius)

    def draw_arrow(
        self,
        arrow: Arrow,
        color: tuple[int, int, int],
        offset: pygame.Vector2 | None = None,
        points: Sequence[pygame.Vector2] | None = None,
        points_are_smoothed: bool = False,
    ) -> None:
        body_points = (
            [point.copy() for point in points]
            if points is not None
            else [self.cell_center(cell) for cell in arrow.cells]
        )
        if offset is not None:
            body_points = [point + offset for point in body_points]
        render_points = (
            body_points
            if points_are_smoothed
            else self._rounded_polyline(body_points)
        )

        direction = pygame.Vector2(arrow.direction.col_step, arrow.direction.row_step)
        perpendicular = pygame.Vector2(-direction.y, direction.x)
        head = render_points[-1]
        neck = head + direction * self.cell_size * 0.04
        tip = head + direction * self.cell_size * 0.36
        wing = self.cell_size * 0.15
        width = max(4, round(self.cell_size * 0.16))
        if len(body_points) == 1:
            tail = head - direction * self.cell_size * 0.28
            shaft_points = [tail, neck]
        else:
            tail = render_points[0]
            shaft_points = [*render_points, neck]

        head_points = [tip, neck + perpendicular * wing, neck - perpendicular * wing]
        cacheable = points is None and offset is None
        cached = self._arrow_cache.get(arrow.arrow_id) if cacheable else None
        if cached is None:
            rendered = self._render_arrow_surface(
                shaft_points,
                head_points,
                tail,
                color,
                width,
            )
            if cacheable:
                self._arrow_cache[arrow.arrow_id] = rendered
        else:
            rendered = cached
        self.surface.blit(rendered[0], rendered[1])

    @staticmethod
    def _render_arrow_surface(
        shaft_points: Sequence[pygame.Vector2],
        head_points: Sequence[pygame.Vector2],
        tail: pygame.Vector2,
        color: tuple[int, int, int],
        width: int,
    ) -> tuple[pygame.Surface, tuple[int, int]]:
        geometry = [*shaft_points, *head_points]
        tail_radius = max(width // 2 + 2, 4)
        margin = tail_radius + 3
        left = math.floor(min(point.x for point in geometry) - margin)
        top = math.floor(min(point.y for point in geometry) - margin)
        right = math.ceil(max(point.x for point in geometry) + margin)
        bottom = math.ceil(max(point.y for point in geometry) + margin)
        target_size = (max(1, right - left), max(1, bottom - top))
        high_size = (
            target_size[0] * ARROW_RENDER_SCALE,
            target_size[1] * ARROW_RENDER_SCALE,
        )
        layer = pygame.Surface(high_size, pygame.SRCALPHA)

        def scaled(point: pygame.Vector2) -> tuple[int, int]:
            return (
                round((point.x - left) * ARROW_RENDER_SCALE),
                round((point.y - top) * ARROW_RENDER_SCALE),
            )

        high_width = width * ARROW_RENDER_SCALE
        high_shaft = [scaled(point) for point in shaft_points]
        pygame.draw.lines(layer, color, False, high_shaft, width=high_width)
        cap_radius = max(1, high_width // 2)
        pygame.draw.circle(layer, color, high_shaft[0], cap_radius)
        pygame.draw.circle(layer, color, high_shaft[-1], cap_radius)
        high_head = [scaled(point) for point in head_points]
        pygame.draw.polygon(layer, color, high_head)
        pygame.draw.aalines(layer, color, True, high_head)
        pygame.draw.circle(
            layer,
            color,
            scaled(tail),
            tail_radius * ARROW_RENDER_SCALE,
        )
        return pygame.transform.smoothscale(layer, target_size), (left, top)

    @staticmethod
    def _simplify_polyline(
        points: Sequence[pygame.Vector2],
    ) -> list[pygame.Vector2]:
        if len(points) <= 2:
            return [point.copy() for point in points]
        simplified = [points[0].copy()]
        for previous, current, following in zip(points, points[1:], points[2:]):
            before = current - previous
            after = following - current
            if abs(before.cross(after)) > 0.01 or before.dot(after) <= 0:
                simplified.append(current.copy())
        simplified.append(points[-1].copy())
        return simplified

    def _rounded_polyline(
        self,
        points: Sequence[pygame.Vector2],
    ) -> list[pygame.Vector2]:
        nodes = self._simplify_polyline(points)
        if len(nodes) <= 2:
            return nodes
        result = [nodes[0].copy()]
        preferred_radius = self.cell_size * 0.3
        for previous, corner, following in zip(nodes, nodes[1:], nodes[2:]):
            incoming = corner - previous
            outgoing = following - corner
            radius = min(
                preferred_radius,
                incoming.length() * 0.45,
                outgoing.length() * 0.45,
            )
            if radius <= 0:
                result.append(corner.copy())
                continue
            entry = corner - incoming.normalize() * radius
            exit_point = corner + outgoing.normalize() * radius
            result.append(entry)
            kappa = 0.5522847498
            control_in = entry + incoming.normalize() * radius * kappa
            control_out = exit_point - outgoing.normalize() * radius * kappa
            for step in range(1, 21):
                t = step / 20
                result.append(
                    entry * (1 - t) ** 3
                    + control_in * 3 * (1 - t) ** 2 * t
                    + control_out * 3 * (1 - t) * t**2
                    + exit_point * t**3
                )
        result.append(nodes[-1].copy())
        return result

    def _moved_path_points(
        self,
        arrow: Arrow,
        movement: float,
    ) -> list[pygame.Vector2]:
        direction = (arrow.direction.row_step, arrow.direction.col_step)
        trajectory_cells = list(arrow.cells)
        cursor = trajectory_cells[-1]
        for _ in range(math.ceil(movement) + 1):
            cursor = (cursor[0] + direction[0], cursor[1] + direction[1])
            trajectory_cells.append(cursor)

        body_curve = self._rounded_polyline(
            [self.cell_center(cell) for cell in arrow.cells]
        )
        trajectory_curve = self._rounded_polyline(
            [self.cell_center(cell) for cell in trajectory_cells]
        )
        body_length = self._polyline_length(body_curve)
        start_distance = movement * self.cell_size
        return self._slice_polyline(
            trajectory_curve,
            start_distance,
            start_distance + body_length,
        )

    @staticmethod
    def _polyline_length(points: Sequence[pygame.Vector2]) -> float:
        return sum(
            start.distance_to(end) for start, end in zip(points, points[1:])
        )

    @staticmethod
    def _slice_polyline(
        points: Sequence[pygame.Vector2],
        start_distance: float,
        end_distance: float,
    ) -> list[pygame.Vector2]:
        if len(points) < 2:
            return [point.copy() for point in points]
        lengths = [
            start.distance_to(end) for start, end in zip(points, points[1:])
        ]
        total = sum(lengths)
        start_distance = max(0.0, min(start_distance, total))
        end_distance = max(start_distance, min(end_distance, total))

        def point_at(distance: float) -> pygame.Vector2:
            walked = 0.0
            for index, length in enumerate(lengths):
                if walked + length >= distance and length > 0:
                    ratio = (distance - walked) / length
                    return points[index].lerp(points[index + 1], ratio)
                walked += length
            return points[-1].copy()

        result = [point_at(start_distance)]
        walked = 0.0
        for index, length in enumerate(lengths):
            walked += length
            if start_distance < walked < end_distance:
                result.append(points[index + 1].copy())
        end_point = point_at(end_distance)
        if not result[-1].distance_to(end_point) < 0.01:
            result.append(end_point)
        return result

    def draw_animation(
        self,
        animation: ArrowAnimation,
        arrow_colors: dict[str, tuple[int, int, int]],
    ) -> None:
        progress = self.ease(animation.progress)
        direction = pygame.Vector2(
            animation.arrow.direction.col_step,
            animation.arrow.direction.row_step,
        )
        if animation.kind is AnimationKind.FLY:
            moving_points = self._moved_path_points(
                animation.arrow,
                progress * animation.movement_cells,
            )
            color = (
                SUCCESS
                if progress < 0.18
                else arrow_colors[animation.arrow.arrow_id]
            )
            self.draw_arrow(
                animation.arrow,
                color,
                points=moving_points,
                points_are_smoothed=True,
            )
            return

        self_collision = (
            animation.collision_target is not None
            and animation.collision_target.arrow_id == animation.arrow.arrow_id
        )
        probe = math.sin(progress * math.pi) * animation.movement_cells
        moving_points = self._moved_path_points(animation.arrow, probe)
        perpendicular = pygame.Vector2(-direction.y, direction.x)
        clicked_shake = math.sin(progress * math.pi * 7) * self.cell_size * 0.018
        moving_points = [
            point + perpendicular * clicked_shake for point in moving_points
        ]
        self.draw_arrow(
            animation.arrow,
            (
                COLLISION_RED
                if self_collision
                else arrow_colors[animation.arrow.arrow_id]
            ),
            points=moving_points,
            points_are_smoothed=True,
        )
        if animation.collision_target is not None and not self_collision:
            target_shake = (
                math.sin(progress * math.pi * 12)
                * math.sin(progress * math.pi)
                * self.cell_size
                * 0.11
            )
            self.draw_arrow(
                animation.collision_target,
                COLLISION_RED,
                offset=perpendicular * target_shake,
            )

    @staticmethod
    def blocked_probe_distance(arrow: Arrow, board: GameBoard) -> float:
        empty_distance = 0
        for cell in board.cells_to_edge(arrow.head, arrow.direction):
            if board.arrow_at(cell) is not None:
                break
            empty_distance += 1
        return empty_distance + 0.18

    @staticmethod
    def ease(progress: float) -> float:
        return progress**3 * (progress * (progress * 6.0 - 15.0) + 10.0)
