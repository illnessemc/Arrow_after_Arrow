"""倒计时和无尽累计分接入游戏流程的集成测试。"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from arrow_game.app import ArrowGameApp, ScreenState
from arrow_game.core import (
    Arrow,
    BoardLayout,
    CoverageMode,
    Direction,
    Level,
    LevelRole,
)
from arrow_game.data import MemoryScoreStore
from arrow_game.ui import EmptyAssetProvider


def one_arrow_level(time_limit_seconds: float) -> Level:
    return Level(
        name="计时测试关",
        layout=BoardLayout.rectangle(1, 1),
        arrows=(Arrow.single("only", 0, 0, Direction.UP),),
        role=LevelRole.TEST,
        coverage=CoverageMode.REQUIRE_FULL,
        time_limit_seconds=time_limit_seconds,
    )


class TimedGameFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryScoreStore()
        self.app = ArrowGameApp(
            assets=EmptyAssetProvider(),
            score_store=self.store,
        )

    def tearDown(self) -> None:
        self.app.close()

    def click_only_arrow(self) -> None:
        self.app._layout_board()
        self.app.buttons = []
        center = self.app._cell_center((0, 0))
        self.app._handle_click((round(center.x), round(center.y)))

    def test_timeout_fails_level_and_restart_resets_timer(self) -> None:
        level = one_arrow_level(5.0)
        self.app._load_level(level, color_seed=1)

        self.app._update(6.0)

        self.assertIs(self.app.state, ScreenState.FAILED)
        self.assertEqual(self.app.notice, "时间耗尽")
        self.app._run_action("restart")
        self.assertIs(self.app.state, ScreenState.PLAYING)
        self.assertEqual(self.app.round_scoring.remaining_seconds, 5.0)

    def test_endless_completion_accumulates_and_saves_high_score(self) -> None:
        level = one_arrow_level(60.0)
        self.app.endless_mode = True
        self.app.endless_round = 1
        self.app._load_level(level, color_seed=1)
        self.app._update(10.0)

        self.click_only_arrow()

        self.assertIsNotNone(self.app.last_round_score)
        assert self.app.last_round_score is not None
        self.assertEqual(
            self.app.endless_scores.current_score,
            self.app.last_round_score.score,
        )
        self.assertEqual(
            self.app.endless_scores.high_score,
            self.app.last_round_score.score,
        )
        self.assertEqual(
            self.store.load_high_score(),
            self.app.last_round_score.score,
        )

    def test_debug_mode_freezes_countdown_and_does_not_record_score(self) -> None:
        level = one_arrow_level(20.0)
        self.app.debug_enabled = True
        self.app.debug_mode = True
        self.app.endless_mode = True
        self.app._load_level(level, color_seed=1)

        self.app._update(10.0)
        self.click_only_arrow()

        self.assertEqual(self.app.round_scoring.elapsed_seconds, 0.0)
        self.assertEqual(self.app.endless_scores.current_score, 0)


if __name__ == "__main__":
    unittest.main()
