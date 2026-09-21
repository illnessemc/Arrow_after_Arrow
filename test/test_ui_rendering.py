"""页面模块拆分后的无窗口渲染冒烟测试。"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from arrow_game.app import ArrowGameApp, ScreenState
from arrow_game.ui import EmptyAssetProvider


class UiRenderingSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = ArrowGameApp(
            assets=EmptyAssetProvider(),
            debug_enabled=True,
        )
        # 按真实流程装载关卡，初始化配色、计时和棋盘视图所需状态。
        self.app._start_level(0)

    def tearDown(self) -> None:
        self.app.close()

    def test_all_screen_states_render_without_error(self) -> None:
        states = (
            ScreenState.START,
            ScreenState.LEVEL_SELECT,
            ScreenState.PLAYING,
            ScreenState.LEVEL_COMPLETE,
            ScreenState.FAILED,
            ScreenState.GAME_COMPLETE,
        )
        for state in states:
            with self.subTest(state=state):
                self.app.state = state
                self.app._draw()
                self.assertTrue(self.app.buttons)

        self.app.settings_return_state = ScreenState.PLAYING
        self.app.state = ScreenState.SETTINGS
        self.app._draw()
        self.assertTrue(self.app.buttons)


if __name__ == "__main__":
    unittest.main()
