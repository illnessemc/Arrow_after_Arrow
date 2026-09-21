"""Pygame 通用控件和基础绘制函数。"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from .assets import AssetProvider
from .theme import DARK_THEME

INK = DARK_THEME.ink
PANEL = DARK_THEME.panel
PANEL_LIGHT = DARK_THEME.panel_light
PRIMARY = DARK_THEME.accent
PRIMARY_DARK = (39, 174, 163)
DANGER = DARK_THEME.danger


@dataclass(frozen=True, slots=True)
class FontSet:
    """集中保存页面使用的字号，避免每个页面重复创建字体对象。"""

    small: pygame.font.Font
    body: pygame.font.Font
    button: pygame.font.Font
    title: pygame.font.Font
    subtitle: pygame.font.Font

    @classmethod
    def create_default(cls) -> FontSet:
        def create(size: int) -> pygame.font.Font:
            return pygame.font.SysFont(
                ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"],
                size,
                bold=True,
            )

        return cls(
            small=create(22),
            body=create(28),
            button=create(26),
            title=create(58),
            subtitle=create(32),
        )


@dataclass(slots=True)
class Button:
    """按钮的命中区域、显示文字和动作标识。"""

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
            else:
                color = PANEL_LIGHT if hovered else PANEL
            text_color = INK
            pygame.draw.rect(surface, color, self.rect, border_radius=14)
        label = font.render(self.text, True, text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))


def draw_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center: tuple[int, int],
) -> None:
    image = font.render(text, True, color)
    surface.blit(image, image.get_rect(center=center))


def draw_asset(
    surface: pygame.Surface,
    assets: AssetProvider,
    key: str,
    center: tuple[int, int],
    maximum_size: tuple[int, int],
    *,
    angle: float = 0.0,
    alpha: int = 255,
) -> bool:
    """保持比例绘制素材，并可围绕中心旋转。"""
    image = assets.image(key)
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
    if alpha < 255:
        rendered.set_alpha(max(0, alpha))
    surface.blit(rendered, rendered.get_rect(center=center))
    return True


def draw_button(
    surface: pygame.Surface,
    assets: AssetProvider,
    button: Button,
    font: pygame.font.Font,
) -> None:
    """进阶模式和主要确认动作使用主按钮，其余动作使用副按钮。"""
    use_primary = button.action in {"advanced_mode", "restart"}
    button.primary = use_primary
    background = assets.image(f"button_{button.action}")
    if background is None:
        background = assets.image(
            "button_primary" if use_primary else "button_secondary"
        )
    button.draw(surface, font, background_image=background)


def draw_gear_button(
    surface: pygame.Surface,
    assets: AssetProvider,
    rect: pygame.Rect,
) -> Button:
    """绘制设置按钮并返回它，调用者负责加入命中列表。"""
    button = Button(rect, "", "settings", False)
    if draw_asset(surface, assets, "icon_settings", rect.center, rect.size):
        return button
    pygame.draw.rect(surface, PANEL, rect, border_radius=14)
    center = pygame.Vector2(rect.center)
    for index in range(8):
        angle = index * math.pi / 4
        direction = pygame.Vector2(math.cos(angle), math.sin(angle))
        pygame.draw.line(
            surface,
            INK,
            center + direction * 12,
            center + direction * 18,
            width=6,
        )
    pygame.draw.circle(surface, INK, rect.center, 13)
    pygame.draw.circle(surface, PANEL, rect.center, 6)
    return button


def draw_lives(
    surface: pygame.Surface,
    assets: AssetProvider,
    center: tuple[int, int],
    remaining: int,
    total: int,
) -> None:
    """优先使用生命素材；已消耗的生命以半透明状态保留位置。"""
    heart = assets.image("life")
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
            surface.blit(image, rect)
        return

    for index in range(total):
        x = int(start_x + index * spacing)
        y = center[1]
        color = DANGER if index < remaining else PANEL_LIGHT
        pygame.draw.circle(surface, color, (x - 6, y - 5), 7)
        pygame.draw.circle(surface, color, (x + 6, y - 5), 7)
        pygame.draw.polygon(
            surface,
            color,
            ((x - 13, y - 3), (x + 13, y - 3), (x, y + 14)),
        )


def format_time(seconds: float) -> str:
    """向上取整倒计时，避免尚有小数时间时提前显示 00:00。"""
    total_seconds = max(0, math.ceil(seconds))
    minutes, seconds_part = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds_part:02d}"
