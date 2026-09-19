"""界面主题、颜色分配和可替换资源接口。"""

from .assets import AssetProvider, EmptyAssetProvider
from .theme import DARK_THEME, GameTheme, assign_arrow_colors

__all__ = [
    "DARK_THEME",
    "AssetProvider",
    "EmptyAssetProvider",
    "GameTheme",
    "assign_arrow_colors",
]
