"""“星箭迷途”的 Pygame 图形界面、输入处理与基础动画。

本模块只协调输入、页面状态和显示效果；阻挡判定、格子占用、失误等规则
均由 core 包负责。页面优先使用 ``resource/image`` 素材，缺失时回退到图元。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Sequence

import pygame

from .core import Arrow, ClickResult, GameSession, Level
from .data import LEVELS, EndlessLevelFactory
from .ui import (
    COLLISION_RED,
    DARK_THEME,
    AnimationKind,
    AnimationQueue,
    ArrowAnimation,
    AssetProvider,
    DirectoryAssetProvider,
    assign_arrow_colors,
)

WINDOW_SIZE = (800, 1000)
FPS = 60
ARROW_RENDER_SCALE = 5
GAME_VERSION = "v1.0"

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
    LEVEL_SELECT = auto()
    SETTINGS = auto()
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
    def __init__(
        self,
        assets: AssetProvider | None = None,
        *,
        debug_enabled: bool = False,
        endless_factory: EndlessLevelFactory | None = None,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("星箭迷途")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.font_small = self._font(22, bold=True)
        self.font_body = self._font(28, bold=True)
        self.font_button = self._font(26, bold=True)
        self.font_title = self._font(58, bold=True)
        self.font_subtitle = self._font(32, bold=True)
        self.assets = assets or DirectoryAssetProvider.project_default()
        logo = self.assets.image("app_logo")
        if logo is not None:
            pygame.display.set_icon(
                pygame.transform.smoothscale(logo, (64, 64))
            )
        self.endless_factory = endless_factory or EndlessLevelFactory()

        self.state = ScreenState.START
        self.settings_return_state = ScreenState.START
        # 调试能力只能由命令行显式开启；普通版本既不显示入口，也不能调用。
        self.debug_enabled = debug_enabled
        self.debug_mode = debug_enabled
        self.level_index = 0
        self.model = GameSession(LEVELS[0])
        self.endless_mode = False
        self.endless_round = 0
        self.endless_seed: int | None = None
        self.notice: str | None = None
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
        """进入固定关卡，同时退出无尽模式。"""
        self.endless_mode = False
        self.endless_round = 0
        self.endless_seed = None
        self.level_index = index
        self.notice = None
        self._load_level(LEVELS[index], color_seed=20260920 + index)

    def _load_level(self, level: Level, *, color_seed: int) -> None:
        """装载任意来源的关卡，并统一清空上一局的表现状态。"""
        self.model = GameSession(level)
        self.arrow_colors = assign_arrow_colors(
            level,
            DARK_THEME.arrow_palette,
            seed=color_seed,
        )
        self._arrow_render_cache.clear()
        self.animations.clear()
        self.pending_state = None
        self.state = ScreenState.PLAYING

    def _start_endless_level(self, round_number: int) -> bool:
        """在线生成并进入一关；失败时保留可恢复的界面而不是退出程序。"""
        self._show_generation_screen(round_number)
        try:
            generated = self.endless_factory.generate(round_number)
        except RuntimeError as error:
            self.notice = str(error)
            self.state = (
                ScreenState.START
                if round_number == 1
                else ScreenState.LEVEL_COMPLETE
            )
            return False

        self.endless_mode = True
        self.endless_round = round_number
        self.endless_seed = generated.seed
        self.notice = None
        self._load_level(generated.level, color_seed=generated.seed)
        return True

    def _show_generation_screen(self, round_number: int) -> None:
        """在同步生成期间给出明确反馈；后续可替换为完整加载页素材。"""
        background = self.assets.image("generating_background")
        if background is None:
            self.screen.fill(BACKGROUND)
        else:
            self.screen.blit(
                pygame.transform.smoothscale(background, WINDOW_SIZE),
                (0, 0),
            )
        self._draw_text("正在生成无尽关卡", self.font_subtitle, INK, (400, 430))
        self._draw_text(
            f"第 {round_number} 关 · 正在验证可通关性",
            self.font_small,
            MUTED,
            (400, 490),
        )
        pygame.display.flip()
        pygame.event.pump()

    def _restart_current_level(self) -> None:
        """使用当前模板重开；无尽模式不会因为重开而更换随机地图。"""
        level = self.model.level
        color_seed = self.endless_seed or (20260920 + self.level_index)
        self._load_level(level, color_seed=color_seed)

    def _return_home(self) -> None:
        """退出当前流程并释放动态关卡与表现缓存。"""
        self.state = ScreenState.START
        self.level_index = 0
        self.endless_mode = False
        self.endless_round = 0
        self.endless_seed = None
        self.model = GameSession(LEVELS[0])
        self.animations.clear()
        self.arrow_colors.clear()
        self._arrow_render_cache.clear()
        self.pending_state = None
        self.notice = None

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._handle_escape()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_escape(self) -> None:
        """在游戏内切出设置；在子页面返回；首页按 Esc 才退出。"""
        if self.state is ScreenState.PLAYING:
            self._open_settings()
        elif self.state is ScreenState.SETTINGS:
            self._return_home()
        elif self.state is ScreenState.LEVEL_SELECT:
            self._return_home()
        elif self.state is ScreenState.START:
            self._open_settings()
        else:
            self._return_home()

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for button in self.buttons:
            if button.rect.collidepoint(pos):
                self._run_action(button.action)
                return

        if self.state != ScreenState.PLAYING:
            return
        if self.model.is_cleared or (self.model.is_failed and not self.debug_mode):
            return
        arrow = self._arrow_at_pixel(pos)
        if arrow is None or self.animations.contains(arrow.arrow_id):
            return

        # 调试入口与正式规则完全分开；关闭调试后仍由核心规则判断阻挡。
        blocker = None
        if self.debug_enabled and self.debug_mode:
            result, _ = self.model.remove_cell_for_debug(arrow.head)
        else:
            # 在规则改变棋盘前记录第一个阻挡者，供表现层精确高亮。
            blocker = self.model.blocker_of(arrow)
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
                if self.endless_mode:
                    self.pending_state = ScreenState.LEVEL_COMPLETE
                else:
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
                    collision_target=blocker,
                )
            )
            if self.model.is_failed:
                self.pending_state = ScreenState.FAILED

    def _run_action(self, action: str) -> None:
        if action == "start":
            self._start_level(0)
        elif action == "endless":
            self._start_endless_level(1)
        elif action == "endless_next":
            self._start_endless_level(self.endless_round + 1)
        elif action == "level_select":
            self.state = ScreenState.LEVEL_SELECT
        elif action.startswith("level:"):
            self._start_level(int(action.split(":", 1)[1]))
        elif action == "settings":
            self._open_settings()
        elif action == "settings_back":
            self.state = self.settings_return_state
        elif action == "toggle_debug":
            if self.debug_enabled:
                self.debug_mode = not self.debug_mode
                if self.debug_mode and self.pending_state is ScreenState.FAILED:
                    self.pending_state = None
        elif action == "debug_previous":
            if self.debug_enabled and self.debug_mode:
                self._start_level(max(0, self.level_index - 1))
        elif action == "debug_next":
            if self.debug_enabled and self.debug_mode:
                self._start_level(min(len(LEVELS) - 1, self.level_index + 1))
        elif action == "debug_endless_next":
            if self.debug_enabled and self.debug_mode and self.endless_mode:
                self._start_endless_level(self.endless_round + 1)
        elif action == "restart":
            self._restart_current_level()
        elif action == "next":
            self._start_level(self.level_index + 1)
        elif action == "home":
            self._return_home()
        elif action == "quit":
            self.running = False

    def _open_settings(self) -> None:
        """保存来源页面，设置关闭后能够回到原位置。"""
        if self.state is ScreenState.SETTINGS:
            return
        self.settings_return_state = self.state
        self.state = ScreenState.SETTINGS

    def _update(self, dt: float) -> None:
        if self.state is not ScreenState.PLAYING:
            return
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
        background_keys = {
            ScreenState.START: "start_background",
            ScreenState.LEVEL_SELECT: "level_select_background",
            ScreenState.SETTINGS: "settings_background",
            ScreenState.PLAYING: "game_background",
            ScreenState.LEVEL_COMPLETE: "result_background",
            ScreenState.FAILED: "failed_background",
            ScreenState.GAME_COMPLETE: "result_background",
        }
        background_key = background_keys[self.state]
        background = self.assets.image(background_key)
        if background is None and self.state in {
            ScreenState.LEVEL_SELECT,
            ScreenState.SETTINGS,
        }:
            background = self.assets.image("start_background")
        if background is None:
            self.screen.fill(BACKGROUND)
        else:
            self.screen.blit(pygame.transform.smoothscale(background, WINDOW_SIZE), (0, 0))
        self.buttons = []
        if self.state == ScreenState.START:
            self._draw_start()
        elif self.state == ScreenState.LEVEL_SELECT:
            self._draw_level_select()
        elif self.state == ScreenState.SETTINGS:
            self._draw_settings()
        elif self.state == ScreenState.PLAYING:
            self._draw_game()
        else:
            self._draw_result()

    def _draw_start(self) -> None:
        self._draw_asset("app_logo", (400, 105), (112, 112))
        if not self._draw_asset("start_title", (400, 255), (610, 190)):
            self._draw_text("星箭迷途", self.font_title, INK, (400, 255))

        button = Button(pygame.Rect(245, 440, 310, 76), "开始游戏", "start")
        self._draw_button(button, self.font_button)
        self.buttons.append(button)

        select = Button(
            pygame.Rect(255, 545, 290, 68), "选择关卡", "level_select", False
        )
        self._draw_button(select, self.font_button)
        self.buttons.append(select)
        endless = Button(
            pygame.Rect(255, 640, 290, 68), "无尽模式", "endless", False
        )
        self._draw_button(endless, self.font_button)
        self.buttons.append(endless)
        quit_button = Button(
            pygame.Rect(255, 735, 290, 68), "退出游戏", "quit", False
        )
        self._draw_button(quit_button, self.font_button)
        self.buttons.append(quit_button)
        self._draw_gear_button(pygame.Rect(28, 910, 58, 58))
        if self.notice:
            self._draw_text(self.notice, self.font_small, DANGER, (400, 850))
        version = self.font_small.render(GAME_VERSION, True, MUTED)
        self.screen.blit(version, version.get_rect(bottomright=(776, 976)))

    def _draw_level_select(self) -> None:
        """绘制独立关卡选择页，所有已配置关卡都可直接进入。"""
        self._draw_text("选择关卡", self.font_title, INK, (400, 150))
        self._draw_text("选择要测试或游玩的棋盘", self.font_body, MUTED, (400, 220))

        button_width = 230
        button_height = 72
        gap_x = 32
        start_x = (WINDOW_SIZE[0] - button_width * 2 - gap_x) // 2
        for index, _level in enumerate(LEVELS):
            row, col = divmod(index, 2)
            rect = pygame.Rect(
                start_x + col * (button_width + gap_x),
                300 + row * 98,
                button_width,
                button_height,
            )
            button = Button(rect, f"第 {index + 1} 关", f"level:{index}", False)
            self._draw_button(button, self.font_button)
            self.buttons.append(button)

        back = Button(pygame.Rect(285, 760, 230, 58), "返回", "home", False)
        self._draw_button(back, self.font_button)
        self.buttons.append(back)

    def _draw_settings(self) -> None:
        """绘制全局设置；游戏内打开时额外提供本关控制。"""
        self._draw_asset("icon_settings", (400, 118), (104, 104))
        self._draw_text("设置", self.font_subtitle, INK, (400, 205))
        if self.debug_enabled:
            debug_text = f"调试模式：{'开' if self.debug_mode else '关'}"
            debug = Button(
                pygame.Rect(255, 260, 290, 64), debug_text, "toggle_debug"
            )
            self._draw_button(debug, self.font_button)
            self.buttons.append(debug)
            self._draw_text(
                "开启后点击任意箭头都可强制飞出",
                self.font_small,
                MUTED,
                (400, 350),
            )
        if self.settings_return_state is ScreenState.PLAYING:
            if self.debug_enabled and self.debug_mode and not self.endless_mode:
                if self.level_index > 0:
                    previous = Button(
                        pygame.Rect(150, 425, 235, 58),
                        "上一关",
                        "debug_previous",
                        False,
                    )
                    self._draw_button(previous, self.font_button)
                    self.buttons.append(previous)
                if self.level_index < len(LEVELS) - 1:
                    following = Button(
                        pygame.Rect(415, 425, 235, 58),
                        "下一关",
                        "debug_next",
                        False,
                    )
                    self._draw_button(following, self.font_button)
                    self.buttons.append(following)
            elif self.debug_enabled and self.debug_mode and self.endless_mode:
                following = Button(
                    pygame.Rect(282, 425, 235, 58),
                    "跳过本关",
                    "debug_endless_next",
                    False,
                )
                self._draw_button(following, self.font_button)
                self.buttons.append(following)

            restart = Button(
                pygame.Rect(255, 530, 290, 60), "重新开始本关", "restart", False
            )
            home = Button(
                pygame.Rect(255, 615, 290, 60), "返回主界面", "home", False
            )
            resume = Button(
                pygame.Rect(255, 700, 290, 64), "继续游戏", "settings_back"
            )
            for button in (restart, home, resume):
                self._draw_button(button, self.font_button)
                self.buttons.append(button)
        else:
            back = Button(
                pygame.Rect(255, 455, 290, 60), "返回", "settings_back", False
            )
            self._draw_button(back, self.font_button)
            self.buttons.append(back)

    def _draw_game(self) -> None:
        self._layout_board()
        level = self.model.level

        level_title = (
            f"无尽 {self.endless_round}"
            if self.endless_mode
            else f"第 {self.level_index + 1} 关"
        )
        self._draw_text(level_title, self.font_subtitle, INK, (400, 42))
        self._draw_lives((400, 84), self.model.mistakes_left, level.mistake_limit)

        self._draw_gear_button(pygame.Rect(24, 27, 54, 54))
        restart = Button(
            pygame.Rect(88, 27, 112, 54),
            "重新开始",
            "restart",
            False,
        )
        self._draw_button(restart, self.font_small)
        self.buttons.append(restart)
        if self.debug_enabled and self.debug_mode:
            self._draw_text("DEBUG", self.font_small, PRIMARY, (245, 53))

        pygame.draw.line(self.screen, GRID, (0, 112), (WINDOW_SIZE[0], 112), width=2)
        active = self.animations.active
        animated_id = active.arrow.arrow_id if active else None
        collision_target_id = (
            active.collision_target.arrow_id
            if active is not None
            and active.kind is AnimationKind.BLOCKED
            and active.collision_target is not None
            else None
        )
        self._draw_board_dots()
        if active is not None and active.kind is AnimationKind.FLY:
            self._draw_fly_trail(active)
        for arrow in self.model.board.arrows:
            if arrow.arrow_id not in {animated_id, collision_target_id}:
                self._draw_arrow(arrow, self.arrow_colors[arrow.arrow_id])

        # 已从逻辑棋盘移除、但还在等待播放的箭头继续静态显示。
        queued = tuple(self.animations)
        for animation in queued[1:]:
            if (
                animation.kind is AnimationKind.FLY
                and animation.arrow.arrow_id != collision_target_id
            ):
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

    def _draw_fly_trail(self, animation: ArrowAnimation) -> None:
        """让箭尾经过的棋盘点短暂放大，再平滑恢复为普通大小。

        特效只使用棋盘点本身的低对比度颜色，不绘制彩色残影。脉冲完全由
        当前动画进度推导，不额外保存粒子对象，因此切关和重开时没有残留。
        """
        movement = self._ease(animation.progress) * animation.movement_cells
        path_cells = [
            *animation.arrow.cells,
            *self.model.board.cells_to_edge(
                animation.arrow.head,
                animation.arrow.direction,
            ),
        ]
        base_radius = max(1, round(self.cell_size * 0.055))
        pulse_radius = max(base_radius + 2, round(self.cell_size * 0.16))
        pulse_duration = 1.8

        for index, cell in enumerate(path_cells):
            age = movement - (index + 0.35)
            if age < 0 or not self.model.board.layout.contains(cell):
                continue
            if age < pulse_duration:
                phase = age / pulse_duration
                strength = math.sin(math.pi * phase) ** 2
                radius = round(base_radius + (pulse_radius - base_radius) * strength)
            else:
                radius = base_radius
            pygame.draw.circle(self.screen, GRID, self._cell_center(cell), radius)


    def _draw_result(self) -> None:
        is_failure = self.state == ScreenState.FAILED
        is_final = self.state == ScreenState.GAME_COMPLETE
        is_endless_complete = (
            self.endless_mode and self.state == ScreenState.LEVEL_COMPLETE
        )
        heading = "失败" if is_failure else "胜利"
        result_icon_key = "result_failed_icon" if is_failure else "result_complete_icon"
        if not self._draw_asset(result_icon_key, (400, 245), (540, 270)):
            self._draw_text(heading, self.font_title, INK, (400, 245))

        if is_failure:
            self._draw_text(
                "可惜了，在观察一下吧",
                self.font_body,
                INK,
                (400, 430),
            )
        else:
            # 三颗星以中间最大、两侧等距且相反角度的方式对称排列。
            self._draw_asset("result_star", (300, 455), (78, 78), angle=12)
            self._draw_asset("result_star", (400, 435), (112, 112))
            self._draw_asset("result_star", (500, 455), (78, 78), angle=-12)
        if self.notice:
            self._draw_text(self.notice, self.font_small, DANGER, (400, 535))

        if is_failure:
            primary = Button(pygame.Rect(245, 585, 310, 72), "重试本关", "restart")
        elif is_endless_complete:
            primary = Button(
                pygame.Rect(255, 585, 290, 68), "继续挑战", "endless_next"
            )
        elif is_final:
            primary = Button(
                pygame.Rect(255, 585, 290, 68), "进入无尽模式", "endless"
            )
        else:
            primary = Button(pygame.Rect(255, 585, 290, 68), "下一关", "next")
        self._draw_button(primary, self.font_button)
        self.buttons.append(primary)

        home = Button(pygame.Rect(255, 680, 290, 64), "返回首页", "home", False)
        self._draw_button(home, self.font_small)
        self.buttons.append(home)

    def _draw_button(self, button: Button, font: pygame.font.Font) -> None:
        """开始/重试使用主按钮，其余文字按钮使用副按钮。"""
        use_primary = button.action in {"start", "restart"}
        button.primary = use_primary
        background = self.assets.image(f"button_{button.action}")
        if background is None:
            background = self.assets.image(
                "button_primary" if use_primary else "button_secondary"
            )
        button.draw(
            self.screen,
            font,
            background_image=background,
        )

    def _draw_gear_button(self, rect: pygame.Rect) -> None:
        """优先绘制设置图标素材；缺省时使用 Pygame 图元齿轮。"""
        button = Button(rect, "", "settings", False)
        if self._draw_asset("icon_settings", rect.center, rect.size):
            self.buttons.append(button)
            return
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=14)
        center = pygame.Vector2(rect.center)
        for index in range(8):
            angle = index * math.pi / 4
            direction = pygame.Vector2(math.cos(angle), math.sin(angle))
            start = center + direction * 12
            end = center + direction * 18
            pygame.draw.line(self.screen, INK, start, end, width=6)
        pygame.draw.circle(self.screen, INK, rect.center, 13)
        pygame.draw.circle(self.screen, PANEL, rect.center, 6)
        self.buttons.append(button)

    def _draw_asset(
        self,
        key: str,
        center: tuple[int, int],
        maximum_size: tuple[int, int],
        *,
        angle: float = 0.0,
    ) -> bool:
        """保持比例绘制素材，并可围绕中心轻微旋转。"""
        image = self.assets.image(key)
        if image is None:
            return False
        ratio = min(
            maximum_size[0] / image.get_width(),
            maximum_size[1] / image.get_height(),
        )
        size = (
            max(1, round(image.get_width() * ratio)),
            max(1, round(image.get_height() * ratio)),
        )
        rendered = pygame.transform.smoothscale(image, size)
        if angle:
            rendered = pygame.transform.rotozoom(rendered, angle, 1.0)
        self.screen.blit(rendered, rendered.get_rect(center=center))
        return True

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
        # 整条轴线一次描边，避免旧方案在每个曲线采样点叠圆产生波浪状边缘。
        pygame.draw.lines(layer, color, False, high_shaft, width=high_width)
        cap_radius = max(1, high_width // 2)
        pygame.draw.circle(layer, color, high_shaft[0], cap_radius)
        pygame.draw.circle(layer, color, high_shaft[-1], cap_radius)
        high_head = [scaled(point) for point in head_points]
        pygame.draw.polygon(layer, color, high_head)
        pygame.draw.aalines(layer, color, True, high_head)
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
        """把正交折线的直角替换为接近四分之一圆的三次曲线。

        三次 Bezier 的控制点沿两条直线切向布置，直线与圆角的一阶导数
        连续，因此不会在接缝处出现肉眼可见的折痕。
        """
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
            # kappa 可用三次 Bezier 近似四分之一圆；提高采样密度后，再配合
            # 高分辨率缩放可显著减轻小尺寸箭头边缘的毛刺。
            kappa = 0.5522847498
            incoming_unit = incoming.normalize()
            outgoing_unit = outgoing.normalize()
            control_in = entry + incoming_unit * radius * kappa
            control_out = exit_point - outgoing_unit * radius * kappa
            for step in range(1, 21):
                t = step / 20
                curve = (
                    entry * (1 - t) ** 3
                    + control_in * 3 * (1 - t) ** 2 * t
                    + control_out * 3 * (1 - t) * t**2
                    + exit_point * t**3
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
            # 被点击箭头保持原色，先向前试探再退回；真正挡路的第一支箭头
            # 使用调色板中不存在的醒目红色并横向震动，直接说明“谁挡住了谁”。
            probe = math.sin(progress * math.pi) * animation.movement_cells
            moving_points = self._moved_path_points(animation.arrow, probe)
            clicked_shake = (
                math.sin(progress * math.pi * 7) * self.cell_size * 0.018
            )
            perpendicular = pygame.Vector2(-direction.y, direction.x)
            moving_points = [
                point + perpendicular * clicked_shake for point in moving_points
            ]
            self._draw_arrow(
                animation.arrow,
                self.arrow_colors[animation.arrow.arrow_id],
                points=moving_points,
                points_are_smoothed=True,
            )

            if animation.collision_target is not None:
                target_shake = (
                    math.sin(progress * math.pi * 12)
                    * math.sin(progress * math.pi)
                    * self.cell_size
                    * 0.11
                )
                self._draw_arrow(
                    animation.collision_target,
                    COLLISION_RED,
                    offset=perpendicular * target_shake,
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
        """优先使用生命素材；已消耗的生命以半透明状态保留位置。"""
        heart = self.assets.image("life")
        spacing = 35
        start_x = center[0] - (total - 1) * spacing / 2
        if heart is not None:
            size = (32, 28)
            full_heart = pygame.transform.smoothscale(heart, size)
            spent_heart = full_heart.copy()
            spent_heart.set_alpha(55)
            for index in range(total):
                image = full_heart if index < remaining else spent_heart
                rect = image.get_rect(
                    center=(round(start_x + index * spacing), center[1])
                )
                self.screen.blit(image, rect)
            return

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
