"""Pygame 图形界面、输入处理与基础动画。

本模块只协调输入、页面状态和显示效果；阻挡判定、格子占用、失误等规则
均由 core 包负责。当前阶段只用 Pygame 图元绘制，不引入额外美术素材。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Sequence

import pygame

from .core import Arrow, ClickResult, GameSession
from .data import LEVELS
from .ui import (
    DARK_THEME,
    AnimationKind,
    AnimationQueue,
    ArrowAnimation,
    AssetProvider,
    EmptyAssetProvider,
    assign_arrow_colors,
)

WINDOW_SIZE = (800, 1000)
FPS = 60
ARROW_RENDER_SCALE = 3

BACKGROUND = DARK_THEME.background
PANEL = DARK_THEME.panel
PANEL_LIGHT = DARK_THEME.panel_light
INK = DARK_THEME.ink
MUTED = DARK_THEME.muted
GRID = DARK_THEME.grid
PRIMARY = DARK_THEME.accent
PRIMARY_DARK = (39, 174, 163)
SUCCESS = DARK_THEME.success
DANGER = DARK_THEME.danger


class ScreenState(Enum):
    START = auto()
    PLAYING = auto()
    LEVEL_COMPLETE = auto()
    FAILED = auto()
    GAME_COMPLETE = auto()


@dataclass(slots=True)
class Button:
    rect: pygame.Rect
    text: str
    action: str
    primary: bool = True

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        background_image: pygame.Surface | None = None,
    ) -> None:
        hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        if background_image is not None:
            image = pygame.transform.smoothscale(background_image, self.rect.size)
            surface.blit(image, self.rect)
            text_color = INK
        else:
            if self.primary:
                color = PRIMARY_DARK if hovered else PRIMARY
                text_color = INK
            else:
                color = PANEL_LIGHT if hovered else PANEL
                text_color = INK
            pygame.draw.rect(surface, color, self.rect, border_radius=14)
        label = font.render(self.text, True, text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))


class ArrowGameApp:
    def __init__(self, assets: AssetProvider | None = None) -> None:
        pygame.init()
        pygame.display.set_caption("一箭又一箭")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.font_small = self._font(22)
        self.font_body = self._font(28)
        self.font_button = self._font(26, bold=True)
        self.font_title = self._font(58, bold=True)
        self.font_subtitle = self._font(32, bold=True)
        self.assets = assets or EmptyAssetProvider()

        self.state = ScreenState.START
        self.level_index = 0
        self.model = GameSession(LEVELS[0])
        self.animations = AnimationQueue()
        self.pending_state: ScreenState | None = None
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self.cell_size = 0
        self.buttons: list[Button] = []
        self.arrow_colors: dict[str, tuple[int, int, int]] = {}
        # 静态箭头使用抗锯齿缓存；切关时统一释放，避免反复创建 Surface。
        self._arrow_render_cache: dict[
            str, tuple[pygame.Surface, tuple[int, int]]
        ] = {}
        self.running = True
        self._closed = False

    @staticmethod
    def _font(size: int, bold: bool = False) -> pygame.font.Font:
        return pygame.font.SysFont(
            ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"],
            size,
            bold=bold,
        )

    def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                self._handle_events()
                self._update(dt)
                self._draw()
                pygame.display.flip()
        finally:
            self.close()

    def close(self) -> None:
        """幂等释放运行期引用、素材缓存和 Pygame 子系统。"""
        if self._closed:
            return
        self._closed = True
        self.animations.clear()
        self.arrow_colors.clear()
        self._arrow_render_cache.clear()
        self.buttons.clear()
        self.assets.clear()
        if pygame.get_init():
            pygame.quit()

    def _start_level(self, index: int) -> None:
        self.level_index = index
        self.model = GameSession(LEVELS[index])
        self.arrow_colors = assign_arrow_colors(
            self.model.level,
            DARK_THEME.arrow_palette,
            seed=20260920 + index,
        )
        self._arrow_render_cache.clear()
        self.animations.clear()
        self.pending_state = None
        self.state = ScreenState.PLAYING

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for button in self.buttons:
            if button.rect.collidepoint(pos):
                self._run_action(button.action)
                return

        if self.state != ScreenState.PLAYING or self.model.is_over:
            return
        arrow = self._arrow_at_pixel(pos)
        if arrow is None or self.animations.contains(arrow.arrow_id):
            return

        # UI 只把点击的网格交给规则层，不在这里重复编写路径判断。
        result, _ = self.model.click_cell(arrow.head)
        if result == ClickResult.REMOVED:
            # 箭头越长、距离边界越远，完整抽出需要的动画时间也略长。
            edge_cells = tuple(
                self.model.board.cells_to_edge(arrow.head, arrow.direction)
            )
            movement_cells = len(edge_cells) + len(arrow.cells)
            duration = min(1.55, 0.36 + movement_cells * 0.045)
            self.animations.append(
                ArrowAnimation(
                    AnimationKind.FLY,
                    arrow,
                    duration=duration,
                    movement_cells=movement_cells,
                )
            )
            if self.model.is_cleared:
                self.pending_state = (
                    ScreenState.GAME_COMPLETE
                    if self.level_index == len(LEVELS) - 1
                    else ScreenState.LEVEL_COMPLETE
                )
        elif result == ClickResult.BLOCKED:
            self.animations.append(
                ArrowAnimation(
                    AnimationKind.BLOCKED,
                    arrow,
                    duration=0.34,
                    movement_cells=self._blocked_probe_distance(arrow),
                )
            )
            if self.model.is_failed:
                self.pending_state = ScreenState.FAILED

    def _run_action(self, action: str) -> None:
        if action == "start":
            self._start_level(0)
        elif action == "restart":
            self._start_level(self.level_index)
        elif action == "next":
            self._start_level(self.level_index + 1)
        elif action == "home":
            self.state = ScreenState.START
            self.animations.clear()
            self.pending_state = None
        elif action == "quit":
            self.running = False

    def _update(self, dt: float) -> None:
        self.animations.update(dt)
        if not self.animations and self.pending_state is not None:
            self.state = self.pending_state
            self.pending_state = None

    def _layout_board(self) -> None:
        level = self.model.level
        available_width = WINDOW_SIZE[0] - 92
        available_height = 850
        self.cell_size = min(
            46,
            int(min(available_width / level.cols, available_height / level.rows)),
        )
        width = self.cell_size * level.cols
        height = self.cell_size * level.rows
        self.board_rect = pygame.Rect(
            (WINDOW_SIZE[0] - width) // 2,
            125 + (available_height - height) // 2,
            width,
            height,
        )

    def _arrow_at_pixel(self, pos: tuple[int, int]) -> Arrow | None:
        if not self.board_rect.collidepoint(pos):
            return None
        col = (pos[0] - self.board_rect.x) // self.cell_size
        row = (pos[1] - self.board_rect.y) // self.cell_size
        return self.model.board.arrow_at((row, col))

    def _draw(self) -> None:
        background_key = "start_background" if self.state == ScreenState.START else "game_background"
        background = self.assets.image(background_key)
        if background is None:
            self.screen.fill(BACKGROUND)
        else:
            self.screen.blit(pygame.transform.smoothscale(background, WINDOW_SIZE), (0, 0))
        self.buttons = []
        if self.state == ScreenState.START:
            self._draw_start()
        elif self.state == ScreenState.PLAYING:
            self._draw_game()
        else:
            self._draw_result()

    def _draw_start(self) -> None:
        pygame.draw.circle(self.screen, PANEL_LIGHT, (75, 90), 125)
        pygame.draw.circle(self.screen, PANEL, (745, 905), 155)
        title_image = self.assets.image("start_title")
        if title_image is None:
            self._draw_text("一箭又一箭", self.font_title, INK, (400, 225))
        else:
            self.screen.blit(title_image, title_image.get_rect(center=(400, 225)))
        self._draw_text("观察路径，依次送走每一支箭", self.font_body, MUTED, (400, 300))

        card = pygame.Rect(110, 375, 580, 185)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=22)
        pygame.draw.rect(self.screen, PANEL_LIGHT, card, width=2, border_radius=22)
        instructions = (
            "前方没有箭头：飞出棋盘",
            "前方存在箭头：碰撞并消耗机会",
            "清空所有箭头即可过关",
        )
        for index, line in enumerate(instructions):
            self._draw_text(line, self.font_small, INK, (400, 415 + index * 52))

        button = Button(pygame.Rect(275, 640, 250, 68), "开始游戏", "start")
        self._draw_button(button, self.font_button)
        self.buttons.append(button)
        self._draw_text("ESC 退出游戏", self.font_small, MUTED, (400, 790))

    def _draw_game(self) -> None:
        self._layout_board()
        level = self.model.level

        self._draw_text(f"第 {self.level_index + 1} 关", self.font_subtitle, INK, (400, 42))
        self._draw_text(
            f"剩余 {self.model.remaining_arrows}", self.font_small, MUTED, (675, 44)
        )
        self._draw_lives((400, 84), self.model.mistakes_left, level.mistake_limit)

        restart = Button(pygame.Rect(24, 27, 112, 48), "重新开始", "restart", False)
        self._draw_button(restart, self.font_small)
        self.buttons.append(restart)

        pygame.draw.line(self.screen, GRID, (0, 112), (WINDOW_SIZE[0], 112), width=2)
        active = self.animations.active
        animated_id = active.arrow.arrow_id if active else None
        self._draw_board_dots()
        for arrow in self.model.board.arrows:
            if arrow.arrow_id != animated_id:
                self._draw_arrow(arrow, self.arrow_colors[arrow.arrow_id])

        # 已从逻辑棋盘移除、但还在等待播放的箭头继续静态显示。
        queued = tuple(self.animations)
        for animation in queued[1:]:
            if animation.kind is AnimationKind.FLY:
                self._draw_arrow(
                    animation.arrow,
                    self.arrow_colors[animation.arrow.arrow_id],
                )

        if active is not None:
            self._draw_animation(active)

    def _draw_board_dots(self) -> None:
        """只在画面上没有箭头覆盖的可玩格中心绘制棋盘点。

        飞出箭头会在点击时先从逻辑棋盘移除，但它可能仍在动画队列中等待。
        这些格子要等对应动画真正播放完毕后再显出点，避免点透过箭身出现。
        """
        visually_occupied = set(self.model.board.occupied_cells)
        for animation in self.animations:
            if animation.kind is AnimationKind.FLY:
                visually_occupied.update(animation.arrow.cells)

        radius = max(1, round(self.cell_size * 0.055))
        for cell in self.model.board.layout.playable_cells:
            if cell not in visually_occupied:
                pygame.draw.circle(self.screen, GRID, self._cell_center(cell), radius)


    def _draw_result(self) -> None:
        is_failure = self.state == ScreenState.FAILED
        is_final = self.state == ScreenState.GAME_COMPLETE
        accent = DANGER if is_failure else SUCCESS
        icon = "×" if is_failure else "✓"
        heading = "本关失败" if is_failure else ("全部通关！" if is_final else "顺利过关！")
        detail = (
            "失误机会已经用完，再观察一下箭头方向吧"
            if is_failure
            else ("全部关卡已完成，你已经掌握核心玩法" if is_final else "所有箭头都飞出了棋盘")
        )

        pygame.draw.circle(self.screen, accent, (400, 245), 72)
        self._draw_text(icon, self.font_title, INK, (400, 235))
        self._draw_text(heading, self.font_title, INK, (400, 380))
        self._draw_text(detail, self.font_body, MUTED, (400, 450))

        if is_failure:
            primary = Button(pygame.Rect(275, 550, 250, 62), "重试本关", "restart")
        elif is_final:
            primary = Button(pygame.Rect(275, 550, 250, 62), "再玩一次", "start")
        else:
            primary = Button(pygame.Rect(275, 550, 250, 62), "下一关", "next")
        self._draw_button(primary, self.font_button)
        self.buttons.append(primary)

        home = Button(pygame.Rect(275, 635, 250, 56), "返回首页", "home", False)
        self._draw_button(home, self.font_small)
        self.buttons.append(home)

    def _draw_button(self, button: Button, font: pygame.font.Font) -> None:
        """优先使用 ``button_<action>`` 素材，没有时回退到 Pygame 图元。"""
        button.draw(
            self.screen,
            font,
            background_image=self.assets.image(f"button_{button.action}"),
        )

    def _cell_center(self, cell: tuple[int, int]) -> pygame.Vector2:
        row, col = cell
        return pygame.Vector2(
            self.board_rect.x + (col + 0.5) * self.cell_size,
            self.board_rect.y + (row + 0.5) * self.cell_size,
        )

    def _draw_arrow(
        self,
        arrow: Arrow,
        color: tuple[int, int, int],
        offset: pygame.Vector2 | None = None,
        points: Sequence[pygame.Vector2] | None = None,
        points_are_smoothed: bool = False,
    ) -> None:
        """绘制整支箭头的折线路径和头部。

        ``points`` 用于飞出动画传入已经移动过的身体节点；普通绘制则直接
        使用 Arrow.cells。所有转角都用圆形连接，避免粗线拐弯时出现缝隙。
        """
        body_points = (
            [point.copy() for point in points]
            if points is not None
            else [self._cell_center(cell) for cell in arrow.cells]
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
        cached = self._arrow_render_cache.get(arrow.arrow_id) if cacheable else None
        if cached is None:
            rendered = self._render_arrow_surface(
                shaft_points,
                head_points,
                tail,
                color,
                width,
            )
            if cacheable:
                self._arrow_render_cache[arrow.arrow_id] = rendered
        else:
            rendered = cached
        self.screen.blit(rendered[0], rendered[1])

    @staticmethod
    def _render_arrow_surface(
        shaft_points: Sequence[pygame.Vector2],
        head_points: Sequence[pygame.Vector2],
        tail: pygame.Vector2,
        color: tuple[int, int, int],
        width: int,
    ) -> tuple[pygame.Surface, tuple[int, int]]:
        """在局部高分辨率画布绘制箭头，再平滑缩小实现抗锯齿。"""
        geometry = [*shaft_points, *head_points]
        tail_radius = max(width // 2 + 2, 4)
        margin = tail_radius + 3
        left = math.floor(min(point.x for point in geometry) - margin)
        top = math.floor(min(point.y for point in geometry) - margin)
        right = math.ceil(max(point.x for point in geometry) + margin)
        bottom = math.ceil(max(point.y for point in geometry) + margin)
        target_size = (max(1, right - left), max(1, bottom - top))
        scale = ARROW_RENDER_SCALE
        high_size = (target_size[0] * scale, target_size[1] * scale)
        layer = pygame.Surface(high_size, pygame.SRCALPHA)

        def scaled(point: pygame.Vector2) -> tuple[int, int]:
            return (
                round((point.x - left) * scale),
                round((point.y - top) * scale),
            )

        high_width = width * scale
        high_shaft = [scaled(point) for point in shaft_points]
        for start, end in zip(high_shaft, high_shaft[1:]):
            pygame.draw.line(layer, color, start, end, width=high_width)
        for joint in high_shaft:
            pygame.draw.circle(layer, color, joint, high_width // 2 + scale)
        pygame.draw.polygon(layer, color, [scaled(point) for point in head_points])
        pygame.draw.circle(layer, color, scaled(tail), tail_radius * scale)

        return pygame.transform.smoothscale(layer, target_size), (left, top)

    @staticmethod
    def _simplify_polyline(
        points: Sequence[pygame.Vector2],
    ) -> list[pygame.Vector2]:
        """只保留首尾与转角点，使长直线保持完全平滑。"""
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
        """把正交折线的直角替换为采样后的二次圆滑曲线。"""
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
            # 二次 Bézier 曲线提供稳定圆角；采样数固定，避免随帧产生抖动。
            for step in range(1, 7):
                t = step / 6
                curve = (
                    entry * (1 - t) ** 2
                    + corner * 2 * (1 - t) * t
                    + exit_point * t**2
                )
                result.append(curve)
        result.append(nodes[-1].copy())
        return result

    def _moved_path_points(
        self,
        arrow: Arrow,
        movement: float,
    ) -> list[pygame.Vector2]:
        """计算折线箭头沿自身轨迹前进指定格数后的身体位置。

        将原路径和头部前方的延长线拼成一条轨迹，再让一个与箭头等长的
        窗口沿轨迹滑动。头部先前进，身体逐段跟随，转角会自然被拉直。
        """
        direction = (arrow.direction.row_step, arrow.direction.col_step)
        trajectory_cells = list(arrow.cells)
        cursor = trajectory_cells[-1]

        required_steps = math.ceil(movement) + 1
        for _ in range(required_steps):
            cursor = (cursor[0] + direction[0], cursor[1] + direction[1])
            trajectory_cells.append(cursor)

        body_curve = self._rounded_polyline(
            [self._cell_center(cell) for cell in arrow.cells]
        )
        trajectory_curve = self._rounded_polyline(
            [self._cell_center(cell) for cell in trajectory_cells]
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
        return sum(start.distance_to(end) for start, end in zip(points, points[1:]))

    @staticmethod
    def _slice_polyline(
        points: Sequence[pygame.Vector2],
        start_distance: float,
        end_distance: float,
    ) -> list[pygame.Vector2]:
        """按弧长截取连续曲线，用于让整支箭头沿圆角轨迹滑动。"""
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

    def _draw_animation(self, animation: ArrowAnimation) -> None:
        progress = self._ease(animation.progress)
        d_row = animation.arrow.direction.row_step
        d_col = animation.arrow.direction.col_step
        direction = pygame.Vector2(d_col, d_row)

        if animation.kind is AnimationKind.FLY:
            moving_points = self._moved_path_points(
                animation.arrow,
                progress * animation.movement_cells,
            )
            color = (
                SUCCESS
                if progress < 0.18
                else self.arrow_colors[animation.arrow.arrow_id]
            )
            self._draw_arrow(
                animation.arrow,
                color,
                points=moving_points,
                points_are_smoothed=True,
            )
            return
        else:
            probe = math.sin(progress * math.pi) * animation.movement_cells
            moving_points = self._moved_path_points(animation.arrow, probe)
            shake = math.sin(progress * math.pi * 7) * self.cell_size * 0.025
            perpendicular = pygame.Vector2(-direction.y, direction.x)
            moving_points = [point + perpendicular * shake for point in moving_points]
            self._draw_arrow(
                animation.arrow,
                DANGER,
                points=moving_points,
                points_are_smoothed=True,
            )

    def _blocked_probe_distance(self, arrow: Arrow) -> float:
        """在点击瞬间记录碰撞前可前进的距离，避免排队期间状态变化。"""
        empty_distance = 0
        for cell in self.model.board.cells_to_edge(arrow.head, arrow.direction):
            occupant = self.model.board.arrow_at(cell)
            if occupant is not None and occupant.arrow_id != arrow.arrow_id:
                break
            empty_distance += 1
        return empty_distance + 0.18

    @staticmethod
    def _ease(progress: float) -> float:
        """五次平滑插值，让箭头像滑动一样柔和启动和停止。"""
        return progress**3 * (progress * (progress * 6.0 - 15.0) + 10.0)

    def _draw_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        center: tuple[int, int],
    ) -> None:
        image = font.render(text, True, color)
        self.screen.blit(image, image.get_rect(center=center))

    def _draw_lives(
        self,
        center: tuple[int, int],
        remaining: int,
        total: int,
    ) -> None:
        """用 Pygame 图元绘制生命心形，避免依赖字体是否包含心形字符。"""
        spacing = 31
        start_x = center[0] - (total - 1) * spacing / 2
        for index in range(total):
            x = int(start_x + index * spacing)
            y = center[1]
            color = DANGER if index < remaining else PANEL_LIGHT
            pygame.draw.circle(self.screen, color, (x - 6, y - 5), 7)
            pygame.draw.circle(self.screen, color, (x + 6, y - 5), 7)
            pygame.draw.polygon(
                self.screen,
                color,
                ((x - 13, y - 3), (x + 13, y - 3), (x, y + 14)),
            )
