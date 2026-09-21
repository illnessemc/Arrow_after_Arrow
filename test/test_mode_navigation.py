"""首页三种模式入口及固定关卡目录切换测试。"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from arrow_game.app import ArrowGameApp, FixedMode, ScreenState
from arrow_game.data import ADVANCED_LEVELS, BASIC_LEVELS
from arrow_game.ui import EmptyAssetProvider


class ModeNavigationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = ArrowGameApp(assets=EmptyAssetProvider())

    def tearDown(self) -> None:
        self.app.close()

    def test_home_exposes_three_modes_and_advanced_is_primary(self) -> None:
        self.app.state = ScreenState.START
        self.app._draw()
        by_action = {button.action: button for button in self.app.buttons}

        self.assertIn("basic_mode", by_action)
        self.assertIn("advanced_mode", by_action)
        self.assertIn("endless", by_action)
        self.assertNotIn("start", by_action)
        self.assertNotIn("level_select", by_action)
        self.assertTrue(by_action["advanced_mode"].primary)
        self.assertFalse(by_action["basic_mode"].primary)
        self.assertFalse(by_action["endless"].primary)

    def test_basic_mode_opens_three_level_catalog(self) -> None:
        self.app._run_action("basic_mode")

        self.assertIs(self.app.state, ScreenState.LEVEL_SELECT)
        self.assertIs(self.app.fixed_mode, FixedMode.BASIC)
        self.app._draw()
        level_actions = {
            button.action
            for button in self.app.buttons
            if button.action.startswith("level:")
        }
        self.assertEqual(level_actions, {"level:0", "level:1", "level:2"})

        self.app._run_action("level:2")
        self.assertIs(self.app.state, ScreenState.PLAYING)
        self.assertIs(self.app.model.level, BASIC_LEVELS[2])

    def test_advanced_mode_opens_original_six_levels(self) -> None:
        self.app._run_action("advanced_mode")

        self.assertIs(self.app.state, ScreenState.LEVEL_SELECT)
        self.assertIs(self.app.fixed_mode, FixedMode.ADVANCED)
        self.app._draw()
        level_actions = {
            button.action
            for button in self.app.buttons
            if button.action.startswith("level:")
        }
        self.assertEqual(
            level_actions,
            {f"level:{index}" for index in range(len(ADVANCED_LEVELS))},
        )

        self.app._run_action("level:0")
        self.assertIs(self.app.model.level, ADVANCED_LEVELS[0])

    def test_next_level_stays_in_selected_fixed_mode(self) -> None:
        self.app._run_action("basic_mode")
        self.app._run_action("level:0")

        self.app._run_action("next")

        self.assertEqual(self.app.level_index, 1)
        self.assertIs(self.app.model.level, BASIC_LEVELS[1])
        self.assertFalse(self.app.endless_mode)


if __name__ == "__main__":
    unittest.main()
