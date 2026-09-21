"""“星箭迷途”的 Pygame 应用协调器。

本模块协调输入、页面状态、关卡流程和计分；阻挡判定等规则由 core 包负责，
普通页面和棋盘绘制分别交给 PageRenderer 与 BoardView。
"""

from __future__ import annotations

from enum import Enum, auto

import pygame

from .core import (
    Arrow,
    ClickResult,
    GameSession,
    Level,
    RoundScore,
    ScoreLedger,
    TimedScoreSession,
)
from .data import (
    LEVELS,
    EndlessLevelFactory,
    JsonScoreStore,
    ScoreStore,
)
from .ui import (
    DARK_THEME,
    AnimationKind,
    AnimationQueue,
    ArrowAnimation,
    AssetProvider,
    BoardView,
    Button,
    DirectoryAssetProvider,
    FontSet,
    PageRenderer,
    assign_arrow_colors,
    draw_button,
    draw_gear_button,
    draw_lives,
    draw_text,
    format_time,
)

WINDOW_SIZE = (800, 1000)
FPS = 60
GAME_VERSION = "v1.0"

BACKGROUND = DARK_THEME.background
INK = DARK_THEME.ink
MUTED = DARK_THEME.muted
GRID = DARK_THEME.grid
PRIMARY = DARK_THEME.accent
DANGER = DARK_THEME.danger


class ScreenState(Enum):
    START = auto()
    LEVEL_SELECT = auto()
    SETTINGS = auto()
    PLAYING = auto()
    LEVEL_COMPLETE = auto()
    FAILED = auto()
    GAME_COMPLETE = auto()


class ArrowGameApp:
    def __init__(
        self,
        assets: AssetProvider | None = None,
        *,
        debug_enabled: bool = False,
        endless_factory: EndlessLevelFactory | None = None,
        score_store: ScoreStore | None = None,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("星箭迷途")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.fonts = FontSet.create_default()
        self.font_small = self.fonts.small
        self.font_body = self.fonts.body
        self.font_button = self.fonts.button
        self.font_title = self.fonts.title
        self.font_subtitle = self.fonts.subtitle
        self.assets = assets or DirectoryAssetProvider.project_default()
        logo = self.assets.image("app_logo")
        if logo is not None:
            pygame.display.set_icon(
                pygame.transform.smoothscale(logo, (64, 64))
            )
        self.endless_factory = endless_factory or EndlessLevelFactory()
        self.score_store = score_store or JsonScoreStore.project_default()
        self.pages = PageRenderer(self.screen, self.assets, self.fonts)
        self.board_view = BoardView(self.screen)

        self.state = ScreenState.START
        self.settings_return_state = ScreenState.START
        # 调试能力只能由命令行显式开启；普通版本既不显示入口，也不能调用。
        self.debug_enabled = debug_enabled
        self.debug_mode = debug_enabled
        self.level_index = 0
        self.model = GameSession(LEVELS[0])
        self.round_scoring = TimedScoreSession(
            LEVELS[0].time_limit_seconds,
            len(LEVELS[0].arrows),
        )
        self.last_round_score: RoundScore | None = None
        self.endless_scores = ScoreLedger(self.score_store.load_high_score())
        self.endless_mode = False
        self.endless_round = 0
        self.endless_seed: int | None = None
        self.notice: str | None = None
        self.animations = AnimationQueue()
        self.pending_state: ScreenState | None = None
        self.buttons: list[Button] = []
        self.arrow_colors: dict[str, tuple[int, int, int]] = {}
        self.running = True
        self._closed = False

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
        self.board_view.clear()
        self.buttons.clear()
        self.assets.clear()
        if pygame.get_init():
            pygame.quit()

    def _start_level(self, index: int) -> None:
        """进入固定关卡，同时退出无尽模式。"""
        self.endless_scores.start_new_run()
        self.endless_mode = False
        self.endless_round = 0
        self.endless_seed = None
        self.level_index = index
        self.notice = None
        self._load_level(LEVELS[index], color_seed=20260920 + index)

    def _load_level(self, level: Level, *, color_seed: int) -> None:
        """装载任意来源的关卡，并统一清空上一局的表现状态。"""
        self.notice = None
        self.model = GameSession(level)
        self.round_scoring = TimedScoreSession(
            level.time_limit_seconds,
            len(level.arrows),
        )
        self.last_round_score = None
        self.arrow_colors = assign_arrow_colors(
            level,
            DARK_THEME.arrow_palette,
            seed=color_seed,
        )
        self.board_view.clear()
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
        draw_text(
            self.screen,
            "正在生成无尽关卡",
            self.font_subtitle,
            INK,
            (400, 430),
        )
        draw_text(
            self.screen,
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
        self.round_scoring = TimedScoreSession(
            LEVELS[0].time_limit_seconds,
            len(LEVELS[0].arrows),
        )
        self.last_round_score = None
        self.endless_scores.start_new_run()
        self.animations.clear()
        self.arrow_colors.clear()
        self.board_view.clear()
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
                self._complete_current_round()
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
                    movement_cells=self.board_view.blocked_probe_distance(
                        arrow,
                        self.model.board,
                    ),
                    collision_target=blocker,
                )
            )
            if self.model.is_failed:
                self.round_scoring.fail()
                self.pending_state = ScreenState.FAILED

    def _run_action(self, action: str) -> None:
        if action == "start":
            self._start_level(0)
        elif action == "endless":
            self.endless_scores.start_new_run()
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
        # 设置页天然暂停；调试模式也冻结计时，避免检查关卡时产生失败或成绩。
        if not self.debug_mode:
            self.round_scoring.update(dt)
            if self.round_scoring.is_expired and not self.model.is_cleared:
                self.animations.clear()
                self.pending_state = None
                self.notice = "时间耗尽"
                self.state = ScreenState.FAILED
                return
        self.animations.update(dt)
        if not self.animations and self.pending_state is not None:
            self.state = self.pending_state
            self.pending_state = None

    def _complete_current_round(self) -> None:
        """结算当前关；无尽模式再把单关成绩加入累计分。"""
        self.last_round_score = self.round_scoring.complete()
        if not self.endless_mode or self.debug_mode:
            return
        previous_high = self.endless_scores.high_score
        self.endless_scores.add_round(self.last_round_score)
        if self.endless_scores.high_score == previous_high:
            return
        try:
            self.score_store.save_high_score(self.endless_scores.high_score)
        except OSError:
            # 存档失败不影响本局流程；内存中的累计分和最高分仍然有效。
            pass

    def _layout_board(self) -> None:
        self.board_view.layout(self.model.level)

    def _arrow_at_pixel(self, pos: tuple[int, int]) -> Arrow | None:
        return self.board_view.arrow_at_pixel(pos, self.model.board)

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
        self.buttons = self.pages.draw_start(self.notice, GAME_VERSION)

    def _draw_level_select(self) -> None:
        self.buttons = self.pages.draw_level_select(len(LEVELS))

    def _draw_settings(self) -> None:
        self.buttons = self.pages.draw_settings(
            debug_enabled=self.debug_enabled,
            debug_mode=self.debug_mode,
            from_playing=self.settings_return_state is ScreenState.PLAYING,
            endless_mode=self.endless_mode,
            level_index=self.level_index,
            level_count=len(LEVELS),
        )

    def _draw_game(self) -> None:
        self._layout_board()
        level = self.model.level

        level_title = (
            f"无尽 {self.endless_round}"
            if self.endless_mode
            else f"第 {self.level_index + 1} 关"
        )
        title_center = (330, 42) if self.endless_mode else (400, 42)
        draw_text(self.screen, level_title, self.font_subtitle, INK, title_center)
        if self.endless_mode:
            draw_text(
                self.screen,
                f"分数 {self.endless_scores.current_score}",
                self.font_small,
                INK,
                (600, 31),
            )
            draw_text(
                self.screen,
                f"最高 {self.endless_scores.high_score}",
                self.font_small,
                MUTED,
                (600, 58),
            )
        draw_lives(
            self.screen,
            self.assets,
            (400, 84),
            self.model.mistakes_left,
            level.mistake_limit,
        )
        time_color = (
            DANGER if self.round_scoring.remaining_seconds <= 10 else INK
        )
        draw_text(
            self.screen,
            f"时间 {format_time(self.round_scoring.remaining_seconds)}",
            self.font_small,
            time_color,
            (535, 84),
        )

        self.buttons.append(
            draw_gear_button(
                self.screen,
                self.assets,
                pygame.Rect(24, 27, 54, 54),
            )
        )
        restart = Button(
            pygame.Rect(88, 27, 112, 54),
            "重新开始",
            "restart",
            False,
        )
        draw_button(self.screen, self.assets, restart, self.font_small)
        self.buttons.append(restart)
        if self.debug_enabled and self.debug_mode:
            draw_text(self.screen, "DEBUG", self.font_small, PRIMARY, (245, 53))

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
        self.board_view.draw_board_dots(self.model.board, self.animations)
        if active is not None and active.kind is AnimationKind.FLY:
            self.board_view.draw_fly_trail(active, self.model.board)
        for arrow in self.model.board.arrows:
            if arrow.arrow_id not in {animated_id, collision_target_id}:
                self.board_view.draw_arrow(
                    arrow,
                    self.arrow_colors[arrow.arrow_id],
                )

        # 已从逻辑棋盘移除、但还在等待播放的箭头继续静态显示。
        queued = tuple(self.animations)
        for animation in queued[1:]:
            if (
                animation.kind is AnimationKind.FLY
                and animation.arrow.arrow_id != collision_target_id
            ):
                self.board_view.draw_arrow(
                    animation.arrow,
                    self.arrow_colors[animation.arrow.arrow_id],
                )

        if active is not None:
            self.board_view.draw_animation(active, self.arrow_colors)

    def _draw_result(self) -> None:
        is_failure = self.state == ScreenState.FAILED
        is_final = self.state == ScreenState.GAME_COMPLETE
        is_endless_complete = (
            self.endless_mode and self.state == ScreenState.LEVEL_COMPLETE
        )
        self.buttons = self.pages.draw_result(
            is_failure=is_failure,
            is_final=is_final,
            is_endless_complete=is_endless_complete,
            endless_mode=self.endless_mode,
            last_round_score=self.last_round_score,
            current_score=self.endless_scores.current_score,
            high_score=self.endless_scores.high_score,
            notice=self.notice,
        )

    def _cell_center(self, cell: tuple[int, int]) -> pygame.Vector2:
        """兼容测试和输入换算，实际坐标由 BoardView 维护。"""
        return self.board_view.cell_center(cell)
