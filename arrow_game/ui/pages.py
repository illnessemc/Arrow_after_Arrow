"""开始、选关、设置和结算页面的绘制。"""

from __future__ import annotations

import pygame

from arrow_game.core import RoundScore

from .assets import AssetProvider
from .theme import DARK_THEME
from .widgets import (
    Button,
    FontSet,
    draw_asset,
    draw_button,
    draw_gear_button,
    draw_text,
)

INK = DARK_THEME.ink
MUTED = DARK_THEME.muted
DANGER = DARK_THEME.danger


class PageRenderer:
    """绘制非游戏棋盘页面，并返回本帧可点击按钮。"""

    def __init__(
        self,
        surface: pygame.Surface,
        assets: AssetProvider,
        fonts: FontSet,
    ) -> None:
        self.surface = surface
        self.assets = assets
        self.fonts = fonts

    def draw_start(self, notice: str | None, version: str) -> list[Button]:
        draw_asset(self.surface, self.assets, "app_logo", (400, 105), (112, 112))
        if not draw_asset(
            self.surface,
            self.assets,
            "start_title",
            (400, 255),
            (610, 190),
        ):
            draw_text(self.surface, "星箭迷途", self.fonts.title, INK, (400, 255))

        buttons = [
            Button(
                pygame.Rect(255, 440, 290, 68),
                "基础模式",
                "basic_mode",
                False,
            ),
            Button(
                pygame.Rect(245, 535, 310, 76),
                "进阶模式",
                "advanced_mode",
            ),
            Button(
                pygame.Rect(255, 640, 290, 68),
                "无尽模式",
                "endless",
                False,
            ),
            Button(
                pygame.Rect(255, 735, 290, 68),
                "退出游戏",
                "quit",
                False,
            ),
        ]
        for button in buttons:
            draw_button(self.surface, self.assets, button, self.fonts.button)
        buttons.append(
            draw_gear_button(
                self.surface,
                self.assets,
                pygame.Rect(28, 910, 58, 58),
            )
        )
        if notice:
            draw_text(self.surface, notice, self.fonts.small, DANGER, (400, 850))
        version_image = self.fonts.small.render(version, True, MUTED)
        self.surface.blit(
            version_image,
            version_image.get_rect(bottomright=(776, 976)),
        )
        return buttons

    def draw_level_select(
        self,
        level_count: int,
        mode_label: str,
    ) -> list[Button]:
        draw_text(
            self.surface,
            mode_label,
            self.fonts.title,
            INK,
            (400, 150),
        )
        draw_text(
            self.surface,
            "选择关卡",
            self.fonts.body,
            MUTED,
            (400, 220),
        )
        buttons: list[Button] = []
        button_width = 230
        button_height = 72
        gap_x = 32
        start_x = (self.surface.get_width() - button_width * 2 - gap_x) // 2
        for index in range(level_count):
            row, col = divmod(index, 2)
            button = Button(
                pygame.Rect(
                    start_x + col * (button_width + gap_x),
                    300 + row * 98,
                    button_width,
                    button_height,
                ),
                f"第 {index + 1} 关",
                f"level:{index}",
                False,
            )
            draw_button(self.surface, self.assets, button, self.fonts.button)
            buttons.append(button)

        back = Button(pygame.Rect(285, 760, 230, 58), "返回", "home", False)
        draw_button(self.surface, self.assets, back, self.fonts.button)
        buttons.append(back)
        return buttons

    def draw_settings(
        self,
        *,
        debug_enabled: bool,
        debug_mode: bool,
        from_playing: bool,
        endless_mode: bool,
        level_index: int,
        level_count: int,
    ) -> list[Button]:
        draw_asset(
            self.surface,
            self.assets,
            "icon_settings",
            (400, 118),
            (104, 104),
        )
        draw_text(self.surface, "设置", self.fonts.subtitle, INK, (400, 205))
        buttons: list[Button] = []
        if debug_enabled:
            debug = Button(
                pygame.Rect(255, 260, 290, 64),
                f"调试模式：{'开' if debug_mode else '关'}",
                "toggle_debug",
            )
            buttons.append(debug)
            draw_text(
                self.surface,
                "开启后点击任意箭头都可强制飞出",
                self.fonts.small,
                MUTED,
                (400, 350),
            )

        if from_playing:
            if debug_enabled and debug_mode and not endless_mode:
                if level_index > 0:
                    buttons.append(
                        Button(
                            pygame.Rect(150, 425, 235, 58),
                            "上一关",
                            "debug_previous",
                            False,
                        )
                    )
                if level_index < level_count - 1:
                    buttons.append(
                        Button(
                            pygame.Rect(415, 425, 235, 58),
                            "下一关",
                            "debug_next",
                            False,
                        )
                    )
            elif debug_enabled and debug_mode and endless_mode:
                buttons.append(
                    Button(
                        pygame.Rect(282, 425, 235, 58),
                        "跳过本关",
                        "debug_endless_next",
                        False,
                    )
                )

            buttons.extend(
                (
                    Button(
                        pygame.Rect(255, 530, 290, 60),
                        "重新开始本关",
                        "restart",
                        False,
                    ),
                    Button(
                        pygame.Rect(255, 615, 290, 60),
                        "返回主界面",
                        "home",
                        False,
                    ),
                    Button(
                        pygame.Rect(255, 700, 290, 64),
                        "继续游戏",
                        "settings_back",
                    ),
                )
            )
        else:
            buttons.append(
                Button(
                    pygame.Rect(255, 455, 290, 60),
                    "返回",
                    "settings_back",
                    False,
                )
            )

        for button in buttons:
            draw_button(self.surface, self.assets, button, self.fonts.button)
        return buttons

    def draw_result(
        self,
        *,
        is_failure: bool,
        is_final: bool,
        is_endless_complete: bool,
        endless_mode: bool,
        last_round_score: RoundScore | None,
        current_score: int,
        high_score: int,
        notice: str | None,
    ) -> list[Button]:
        heading = "失败" if is_failure else "胜利"
        icon_key = "result_failed_icon" if is_failure else "result_complete_icon"
        if not draw_asset(
            self.surface,
            self.assets,
            icon_key,
            (400, 245),
            (540, 270),
        ):
            draw_text(self.surface, heading, self.fonts.title, INK, (400, 245))

        if is_failure:
            draw_text(
                self.surface,
                "可惜了，在观察一下吧",
                self.fonts.body,
                INK,
                (400, 430),
            )
        else:
            self._draw_result_stars(
                last_round_score.stars if last_round_score else 1
            )
            if last_round_score is not None:
                score_text = (
                    f"本关 {last_round_score.score}  "
                    f"累计 {current_score}  最高 {high_score}"
                    if endless_mode
                    else f"本关得分 {last_round_score.score}"
                )
                draw_text(
                    self.surface,
                    score_text,
                    self.fonts.small,
                    INK,
                    (400, 535),
                )
        if notice:
            draw_text(
                self.surface,
                notice,
                self.fonts.small,
                DANGER,
                (400, 500 if is_failure else 560),
            )
        if is_failure and endless_mode:
            draw_text(
                self.surface,
                f"累计 {current_score}  最高 {high_score}",
                self.fonts.small,
                MUTED,
                (400, 535),
            )

        if is_failure:
            primary = Button(
                pygame.Rect(245, 585, 310, 72),
                "重试本关",
                "restart",
            )
        elif is_endless_complete:
            primary = Button(
                pygame.Rect(255, 585, 290, 68),
                "继续挑战",
                "endless_next",
            )
        elif is_final:
            primary = Button(
                pygame.Rect(255, 585, 290, 68),
                "重新选择关卡",
                "mode_levels",
            )
        else:
            primary = Button(
                pygame.Rect(255, 585, 290, 68),
                "下一关",
                "next",
            )
        home = Button(
            pygame.Rect(255, 680, 290, 64),
            "返回首页",
            "home",
            False,
        )
        draw_button(self.surface, self.assets, primary, self.fonts.button)
        draw_button(self.surface, self.assets, home, self.fonts.small)
        return [primary, home]

    def _draw_result_stars(self, stars: int) -> None:
        stars = max(1, min(stars, 3))
        active_indexes = {1: {1}, 2: {0, 2}, 3: {0, 1, 2}}[stars]
        placements = (
            ((300, 455), (78, 78), 12),
            ((400, 435), (112, 112), 0),
            ((500, 455), (78, 78), -12),
        )
        for index, (center, size, angle) in enumerate(placements):
            active = index in active_indexes
            if draw_asset(
                self.surface,
                self.assets,
                "result_star",
                center,
                size,
                angle=angle,
                alpha=255 if active else 45,
            ):
                continue
            draw_text(
                self.surface,
                "★" if active else "☆",
                self.fonts.title,
                (255, 215, 76) if active else MUTED,
                center,
            )
