"""界面主题、颜色分配和可替换资源接口。"""

from .assets import AssetProvider, DirectoryAssetProvider, EmptyAssetProvider
from .animation import AnimationKind, AnimationQueue, ArrowAnimation
from .board_view import BoardView
from .pages import PageRenderer
from .theme import COLLISION_RED, DARK_THEME, GameTheme, assign_arrow_colors
from .widgets import (
    Button,
    FontSet,
    draw_asset,
    draw_button,
    draw_gear_button,
    draw_lives,
    draw_text,
    format_time,
)

__all__ = [
    "DARK_THEME",
    "COLLISION_RED",
    "AnimationKind",
    "AnimationQueue",
    "ArrowAnimation",
    "AssetProvider",
    "BoardView",
    "Button",
    "DirectoryAssetProvider",
    "EmptyAssetProvider",
    "FontSet",
    "GameTheme",
    "PageRenderer",
    "assign_arrow_colors",
    "draw_asset",
    "draw_button",
    "draw_gear_button",
    "draw_lives",
    "draw_text",
    "format_time",
]
