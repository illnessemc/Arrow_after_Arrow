"""美术资源访问接口。

当前版本仍使用 Pygame 图元和文字。后续导入背景、标题或按钮图片时，只需
实现 ``AssetProvider``，应用层无需知道图片来自目录、压缩包还是其他位置。
"""

from __future__ import annotations

from typing import Protocol

import pygame


class AssetProvider(Protocol):
    """按语义名称提供图片资源的最小接口。

    页面素材键包括 ``start_background``、``level_select_background``、
    ``settings_background``、``game_background``、``result_background`` 和
    ``failed_background``、``generating_background``；局部素材包括
    ``start_title``、``icon_settings``、``result_complete_icon``、
    ``result_failed_icon`` 与 ``button_<action>``。实际实现可自行决定文件名、
    分辨率和缓存策略。
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
