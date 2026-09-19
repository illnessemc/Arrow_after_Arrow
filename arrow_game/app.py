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

WINDOW_SIZE = (920, 760)
FPS = 60

BACKGROUND = (247, 244, 237)
PANEL = (253, 251, 246)
INK = (35, 39, 42)
MUTED = (111, 108, 101)
GRID = (207, 202, 191)
PRIMARY = (66, 92, 78)
PRIMARY_DARK = (47, 72, 59)
ARROW_COLOR = (40, 43, 45)
SUCCESS = (28, 174, 119)
DANGER = (232, 73, 91)


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

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        if self.primary:
            color = PRIMARY_DARK if hovered else PRIMARY
            text_color = (255, 255, 255)
        else:
            color = (226, 234, 245) if hovered else (237, 242, 249)
            text_color = INK
        pygame.draw.rect(surface, color, self.rect, border_radius=14)
        label = font.render(self.text, True, text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))


@dataclass(slots=True)
class Animation:
    kind: str
    arrow: Arrow
    elapsed: float = 0.0
    duration: float = 0.48

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration


class ArrowGameApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("一箭又一箭")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.font_small = self._font(22)
        self.font_body = self._font(28)
        self.font_button = self._font(26, bold=True)
        self.font_title = self._font(64, bold=True)
        self.font_subtitle = self._font(32, bold=True)

        self.state = ScreenState.START
        self.level_index = 0
        self.model = GameSession(LEVELS[0])
        self.animation: Animation | None = None
        self.pending_state: ScreenState | None = None
        self.toast = ""
        self.toast_timer = 0.0
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self.cell_size = 0
        self.buttons: list[Button] = []
        self.running = True

    @staticmethod
    def _font(size: int, bold: bool = False) -> pygame.font.Font:
        return pygame.font.SysFont(
            ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"],
            size,
            bold=bold,
        )

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _start_level(self, index: int) -> None:
        self.level_index = index
        self.model = GameSession(LEVELS[index])
        self.animation = None
        self.pending_state = None
        self.toast = self.model.level.intro
        self.toast_timer = 3.2
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

        if self.state != ScreenState.PLAYING or self.animation is not None:
            return
        arrow = self._arrow_at_pixel(pos)
        if arrow is None:
            return

        # UI 只把点击的网格交给规则层，不在这里重复编写路径判断。
        result, _ = self.model.click_cell(arrow.head)
        if result == ClickResult.REMOVED:
            # 箭头越长、距离边界越远，完整抽出需要的动画时间也略长。
            travel_cells = len(tuple(self.model.board.cells_to_edge(arrow.head, arrow.direction)))
            duration = min(1.5, 0.35 + (travel_cells + len(arrow.cells)) * 0.08)
            self.animation = Animation("fly", arrow, duration=duration)
            self.toast = "漂亮！箭头成功飞出"
            self.toast_timer = 1.2
            if self.model.is_cleared:
                self.pending_state = (
                    ScreenState.GAME_COMPLETE
                    if self.level_index == len(LEVELS) - 1
                    else ScreenState.LEVEL_COMPLETE
                )
        elif result == ClickResult.BLOCKED:
            self.animation = Animation("blocked", arrow, duration=0.42)
            self.toast = f"前方有阻挡，剩余 {self.model.mistakes_left} 次机会"
            self.toast_timer = 1.5
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
            self.animation = None
            self.pending_state = None
        elif action == "quit":
            self.running = False

    def _update(self, dt: float) -> None:
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)
        if self.animation is not None:
            self.animation.elapsed += dt
            if self.animation.done:
                self.animation = None
                if self.pending_state is not None:
                    self.state = self.pending_state
                    self.pending_state = None

    def _layout_board(self) -> None:
        level = self.model.level
        available_width = WINDOW_SIZE[0] - 150
        available_height = WINDOW_SIZE[1] - 245
        self.cell_size = int(min(available_width / level.cols, available_height / level.rows))
        width = self.cell_size * level.cols
        height = self.cell_size * level.rows
        self.board_rect = pygame.Rect(
            (WINDOW_SIZE[0] - width) // 2,
            155 + (available_height - height) // 2,
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
        self.screen.fill(BACKGROUND)
        self.buttons = []
        if self.state == ScreenState.START:
            self._draw_start()
        elif self.state == ScreenState.PLAYING:
            self._draw_game()
        else:
            self._draw_result()

    def _draw_start(self) -> None:
        pygame.draw.circle(self.screen, (229, 225, 214), (120, 100), 150)
        pygame.draw.circle(self.screen, (224, 234, 226), (825, 680), 180)
        self._draw_text("一箭又一箭", self.font_title, INK, (460, 190))
        self._draw_text("点击折线 · 看清箭头 · 逐步解锁", self.font_body, MUTED, (460, 265))

        card = pygame.Rect(185, 320, 550, 155)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=22)
        pygame.draw.rect(self.screen, GRID, card, width=2, border_radius=22)
        instructions = (
            "前方没有箭头：飞出棋盘",
            "前方存在箭头：碰撞并消耗机会",
            "清空所有箭头即可过关",
        )
        for index, line in enumerate(instructions):
            self._draw_text(line, self.font_small, INK, (460, 352 + index * 45))

        button = Button(pygame.Rect(335, 535, 250, 62), "开始游戏", "start")
        button.draw(self.screen, self.font_button)
        self.buttons.append(button)
        self._draw_text("ESC 退出游戏", self.font_small, MUTED, (460, 650))

    def _draw_game(self) -> None:
        self._layout_board()
        level = self.model.level

        self._draw_text(
            f"第 {self.level_index + 1} 关  ·  {level.role.label}  ·  {level.name}",
            self.font_subtitle,
            INK,
            (250, 55),
        )
        self._draw_text(
            f"剩余箭头  {self.model.remaining_arrows}", self.font_small, MUTED, (560, 48)
        )
        self._draw_text(
            f"失误机会  {self.model.mistakes_left}",
            self.font_small,
            DANGER if self.model.mistakes_left == 1 else MUTED,
            (560, 82),
        )

        restart = Button(pygame.Rect(740, 34, 135, 52), "重新开始", "restart", False)
        restart.draw(self.screen, self.font_small)
        self.buttons.append(restart)

        shadow = self.board_rect.inflate(24, 24).move(0, 6)
        pygame.draw.rect(self.screen, (218, 213, 203), shadow, border_radius=24)
        pygame.draw.rect(self.screen, PANEL, self.board_rect.inflate(18, 18), border_radius=24)
        pygame.draw.rect(
            self.screen,
            (225, 220, 210),
            self.board_rect.inflate(18, 18),
            width=1,
            border_radius=24,
        )
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

        animated_id = self.animation.arrow.arrow_id if self.animation else None
        for arrow in self.model.board.arrows:
            if arrow.arrow_id != animated_id:
                self._draw_arrow(arrow, ARROW_COLOR)

        if self.animation is not None:
            self._draw_animation(self.animation)

        if self.toast_timer > 0 and self.toast:
            # 关卡介绍比普通反馈更长，使用接近棋盘宽度的提示框防止文字溢出。
            toast_rect = pygame.Rect(80, 688, 760, 45)
            pygame.draw.rect(self.screen, INK, toast_rect, border_radius=14)
            self._draw_text(self.toast, self.font_small, (255, 255, 255), toast_rect.center)

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

        pygame.draw.circle(self.screen, (*accent[:3],), (460, 205), 72)
        self._draw_text(icon, self.font_title, (255, 255, 255), (460, 195))
        self._draw_text(heading, self.font_title, INK, (460, 330))
        self._draw_text(detail, self.font_body, MUTED, (460, 400))

        if is_failure:
            primary = Button(pygame.Rect(335, 485, 250, 62), "重试本关", "restart")
        elif is_final:
            primary = Button(pygame.Rect(335, 485, 250, 62), "再玩一次", "start")
        else:
            primary = Button(pygame.Rect(335, 485, 250, 62), "下一关", "next")
        primary.draw(self.screen, self.font_button)
        self.buttons.append(primary)

        home = Button(pygame.Rect(335, 570, 250, 56), "返回首页", "home", False)
        home.draw(self.screen, self.font_small)
        self.buttons.append(home)

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

        pygame.draw.lines(self.screen, color, False, shaft_points, width=width)
        for joint in shaft_points[:-1]:
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

    def _draw_animation(self, animation: Animation) -> None:
        progress = min(animation.elapsed / animation.duration, 1.0)
        d_row = animation.arrow.direction.row_step
        d_col = animation.arrow.direction.col_step
        direction = pygame.Vector2(d_col, d_row)

        if animation.kind == "fly":
            exit_distance = len(
                tuple(
                    self.model.board.cells_to_edge(
                        animation.arrow.head,
                        animation.arrow.direction,
                    )
                )
            )
            total_movement = exit_distance + len(animation.arrow.cells)
            moving_points = self._moved_path_points(
                animation.arrow,
                progress * total_movement,
            )
            color = SUCCESS if progress < 0.18 else ARROW_COLOR
            self._draw_arrow(animation.arrow, color, points=moving_points)
            return
        else:
            empty_distance = 0
            for cell in self.model.board.cells_to_edge(
                animation.arrow.head,
                animation.arrow.direction,
            ):
                occupant = self.model.board.arrow_at(cell)
                if occupant is not None and occupant.arrow_id != animation.arrow.arrow_id:
                    break
                empty_distance += 1
            probe = math.sin(progress * math.pi) * (empty_distance + 0.18)
            moving_points = self._moved_path_points(animation.arrow, probe)
            shake = math.sin(progress * math.pi * 7) * self.cell_size * 0.025
            perpendicular = pygame.Vector2(-direction.y, direction.x)
            moving_points = [point + perpendicular * shake for point in moving_points]
            self._draw_arrow(animation.arrow, DANGER, points=moving_points)

    def _draw_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        center: tuple[int, int],
    ) -> None:
        image = font.render(text, True, color)
        self.screen.blit(image, image.get_rect(center=center))
