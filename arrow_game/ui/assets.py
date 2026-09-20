"""美术资源访问接口和项目素材目录实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pygame


class AssetProvider(Protocol):
    """按语义名称提供图片资源的最小接口。

    页面素材键包括 ``start_background``、``level_select_background``、
    ``settings_background``、``game_background``、``result_background`` 和
    ``failed_background``、``generating_background``；局部素材包括标题、
    Logo、设置、生命、星星、胜负图和主副按钮。也可用 ``button_<action>``
    覆盖单个动作按钮。实际实现可自行决定文件名、分辨率和缓存策略。
    """

    def image(self, key: str) -> pygame.Surface | None:
        ...

    def clear(self) -> None:
        """释放实现内部缓存，切换资源包或退出时调用。"""
        ...


class EmptyAssetProvider:
    """没有外部素材时使用的空实现，由界面自动回退到文字和图元。"""

    def image(self, key: str) -> pygame.Surface | None:
        del key
        return None

    def clear(self) -> None:
        return None


class DirectoryAssetProvider:
    """从项目素材目录加载并缓存当前主题图片。"""

    FILES = {
        "start_background": "mainpage.png",
        "level_select_background": "mainpage.png",
        "settings_background": "mainpage.png",
        "game_background": "running_page.png",
        "result_background": "running_page.png",
        "failed_background": "running_page.png",
        "generating_background": "mainpage.png",
        "start_title": "title.png",
        "app_logo": "logo.png",
        "icon_settings": "setting.png",
        "life": "hp.png",
        "result_complete_icon": "victory.png",
        "result_failed_icon": "defeat.png",
        "result_star": "star.png",
        "button_primary": "mainbutton.png",
        "button_secondary": "secbutton.png",
    }
    BACKGROUND_KEYS = {
        "start_background",
        "level_select_background",
        "settings_background",
        "game_background",
        "result_background",
        "failed_background",
        "generating_background",
    }

    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[str, pygame.Surface | None] = {}
        self._file_cache: dict[str, pygame.Surface | None] = {}

    @classmethod
    def project_default(cls) -> DirectoryAssetProvider:
        """定位仓库中的 ``resource/image``，避免依赖启动工作目录。"""
        project_root = Path(__file__).resolve().parents[2]
        return cls(project_root / "resource" / "image")

    def image(self, key: str) -> pygame.Surface | None:
        if key in self._cache:
            return self._cache[key]
        filename = self.FILES.get(key)
        if filename is None:
            self._cache[key] = None
            return None
        if filename in self._file_cache:
            image = self._file_cache[filename]
            self._cache[key] = image
            return image
        path = self.root / filename
        if not path.is_file():
            self._file_cache[filename] = None
            self._cache[key] = None
            return None
        try:
            image = pygame.image.load(path).convert_alpha()
        except (OSError, pygame.error):
            self._file_cache[filename] = None
            self._cache[key] = None
            return None

        # 图标、标题和按钮原图带有大块透明画布。裁切后再缩放能够保持
        # 可见内容大小稳定；页面背景必须保留完整构图，因此不参与裁切。
        if key not in self.BACKGROUND_KEYS:
            bounds = image.get_bounding_rect(min_alpha=2)
            if bounds.width and bounds.height:
                image = image.subsurface(bounds).copy()
        self._file_cache[filename] = image
        self._cache[key] = image
        return image

    def clear(self) -> None:
        self._cache.clear()
        self._file_cache.clear()
