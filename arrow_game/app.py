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


@dataclass(slots=True)
class TrailPulse:
    """箭头飞过网格点时短暂放大的光点。"""

    cell: tuple[int, int]
    color: tuple[int, int, int]
    elapsed: float = 0.0
    duration: float = 0.38

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration


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
        self.trail_pulses: list[TrailPulse] = []
        self.pending_state: ScreenState | None = None
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self.cell_size = 0
        self.buttons: list[Button] = []
        self.arrow_colors: dict[str, tuple[int, int, int]] = {}
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
        self.trail_pulses.clear()
        self.arrow_colors.clear()
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
        self.animations.clear()
        self.trail_pulses.clear()
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
            duration = min(0.95, 0.24 + movement_cells * 0.026)
            self.animations.append(
                ArrowAnimation(
                    AnimationKind.FLY,
                    arrow,
                    duration=duration,
                    movement_cells=movement_cells,
                    trail_cells=(*arrow.cells, *edge_cells),
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
            self.trail_pulses.clear()
            self.pending_state = None
        elif action == "quit":
            self.running = False

    def _update(self, dt: float) -> None:
        for pulse in self.trail_pulses:
            pulse.elapsed += dt
        self.trail_pulses = [pulse for pulse in self.trail_pulses if not pulse.done]

        active = self.animations.active
        if active is not None and active.kind is AnimationKind.FLY:
            projected_progress = min((active.elapsed + dt) / active.duration, 1.0)
            passed_steps = int(
                self._ease(projected_progress) * active.movement_cells
            )
            while active.emitted_steps < min(passed_steps, len(active.trail_cells)):
                cell = active.trail_cells[active.emitted_steps]
                self.trail_pulses.append(
                    TrailPulse(cell, self.arrow_colors[active.arrow.arrow_id])
                )
                active.emitted_steps += 1
            # 大棋盘连续操作时也限制瞬时特效数量，已结束的光点会优先丢弃。
            if len(self.trail_pulses) > 512:
                self.trail_pulses = self.trail_pulses[-512:]

        self.animations.update(dt)
        if not self.animations and self.pending_state is not None:
            self.state = self.pending_state
            self.pending_state = None

    def _layout_board(self) -> None:
        level = self.model.level
        available_width = WINDOW_SIZE[0] - 92
        available_height = 745
        self.cell_size = int(min(available_width / level.cols, available_height / level.rows))
        width = self.cell_size * level.cols
        height = self.cell_size * level.rows
        self.board_rect = pygame.Rect(
            (WINDOW_SIZE[0] - width) // 2,
            135 + (available_height - height) // 2,
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
        for row in range(level.rows):
            for col in range(level.cols):
                if not level.layout.contains((row, col)):
                    continue
                pygame.draw.circle(
                    self.screen,
                    GRID,
                    self._cell_center((row, col)),
                    max(2, int(self.cell_size * 0.035)),
                )

        active = self.animations.active
        animated_id = active.arrow.arrow_id if active else None
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

        self._draw_trail_pulses()
        if active is not None:
            self._draw_animation(active)

        pygame.draw.line(self.screen, GRID, (0, 902), (WINDOW_SIZE[0], 902), width=2)
        self._draw_text("提示", self.font_small, INK, (90, 950))
        self._draw_text("缩放  −   ●   +", self.font_small, MUTED, (400, 950))
        self._draw_text("辅助线", self.font_small, INK, (710, 950))

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

        direction = pygame.Vector2(arrow.direction.col_step, arrow.direction.row_step)
        perpendicular = pygame.Vector2(-direction.y, direction.x)
        head = body_points[-1]
        neck = head + direction * self.cell_size * 0.04
        tip = head + direction * self.cell_size * 0.36
        wing = self.cell_size * 0.18
        width = max(4, int(self.cell_size * 0.085))

        if len(body_points) == 1:
            tail = head - direction * self.cell_size * 0.28
            shaft_points = [tail, neck]
        else:
            tail = body_points[0]
            shaft_points = [*body_points, neck]

        # 每段分别绘制并在连接点补圆，比 draw.lines 的尖锐折角更接近原版。
        for start, end in zip(shaft_points, shaft_points[1:]):
            pygame.draw.line(self.screen, color, start, end, width=width)
        for joint in shaft_points:
            pygame.draw.circle(self.screen, color, joint, width // 2)
        points = [tip, neck + perpendicular * wing, neck - perpendicular * wing]
        pygame.draw.polygon(self.screen, color, points)
        pygame.draw.circle(self.screen, color, tail, width // 2)

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
        trajectory = list(arrow.cells)
        cursor = trajectory[-1]

        required_steps = math.ceil(movement) + 1
        for _ in range(required_steps):
            cursor = (cursor[0] + direction[0], cursor[1] + direction[1])
            trajectory.append(cursor)

        step = int(movement)
        fraction = movement - step

        result: list[pygame.Vector2] = []
        for index in range(len(arrow.cells)):
            current = self._cell_center(trajectory[step + index])
            if fraction > 0:
                following = self._cell_center(trajectory[step + index + 1])
                current = current.lerp(following, fraction)
            result.append(current)
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
            self._draw_arrow(animation.arrow, color, points=moving_points)
            return
        else:
            probe = math.sin(progress * math.pi) * animation.movement_cells
            moving_points = self._moved_path_points(animation.arrow, probe)
            shake = math.sin(progress * math.pi * 7) * self.cell_size * 0.025
            perpendicular = pygame.Vector2(-direction.y, direction.x)
            moving_points = [point + perpendicular * shake for point in moving_points]
            self._draw_arrow(animation.arrow, DANGER, points=moving_points)

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
        """首尾速度为零的平滑插值，减少突然启动和停止的生硬感。"""
        return progress * progress * (3.0 - 2.0 * progress)

    def _draw_trail_pulses(self) -> None:
        for pulse in self.trail_pulses:
            progress = min(pulse.elapsed / pulse.duration, 1.0)
            strength = math.sin(progress * math.pi)
            radius = max(2, int(self.cell_size * (0.04 + 0.16 * strength)))
            color = tuple(
                int(GRID[channel] + (pulse.color[channel] - GRID[channel]) * strength)
                for channel in range(3)
            )
            pygame.draw.circle(self.screen, color, self._cell_center(pulse.cell), radius)

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
