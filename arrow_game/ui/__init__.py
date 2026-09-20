"""界面主题、颜色分配和可替换资源接口。"""

from .assets import AssetProvider, DirectoryAssetProvider, EmptyAssetProvider
from .animation import AnimationKind, AnimationQueue, ArrowAnimation
from .theme import COLLISION_RED, DARK_THEME, GameTheme, assign_arrow_colors

__all__ = [
    "DARK_THEME",
    "COLLISION_RED",
    "AnimationKind",
    "AnimationQueue",
    "ArrowAnimation",
    "AssetProvider",
    "DirectoryAssetProvider",
    "EmptyAssetProvider",
    "GameTheme",
    "assign_arrow_colors",
]
