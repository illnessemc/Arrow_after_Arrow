"""作业要求 T01～T06 的规则与流程回归测试。

测试使用标准库 ``unittest``，不额外增加运行依赖。界面流程在 SDL 的虚拟
显示驱动中执行，因此无需打开游戏窗口，也能验证动画队列和页面状态。
"""

from __future__ import annotations

import os
import unittest

# 必须在导入 Pygame 界面前设置，保证测试在无显示器环境中也可运行。
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from arrow_game.app import ArrowGameApp, ScreenState
from arrow_game.core import (
    Arrow,
    BoardLayout,
    ClickResult,
    CoverageMode,
    Direction,
    GameSession,
    Level,
    LevelRole,
)
from arrow_game.ui import (
    COLLISION_RED,
    DARK_THEME,
    AnimationKind,
    EmptyAssetProvider,
)


def make_level(
    arrows: tuple[Arrow, ...],
    *,
    rows: int = 3,
    cols: int = 3,
    mistake_limit: int = 3,
) -> Level:
    """构造允许空格的小型测试关，避免测试依赖正式关卡生成细节。"""
    return Level(
        name="自动化测试关",
        layout=BoardLayout.rectangle(rows, cols),
        arrows=arrows,
        mistake_limit=mistake_limit,
        role=LevelRole.TEST,
        intro="",
        coverage=CoverageMode.ALLOW_EMPTY,
    )


class GameplayRequirementsTest(unittest.TestCase):
    """逐项对应作业测试表中的 T01～T06。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = ArrowGameApp(assets=EmptyAssetProvider())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.app.close()

    def load_app_level(self, level: Level) -> None:
        """把独立测试关载入界面，并清掉上一个用例的按钮命中区域。"""
        self.app.level_index = 0
        self.app.endless_mode = False
        self.app._load_level(level, color_seed=1)
        self.app._layout_board()
        self.app.buttons = []

    def click_arrow(self, arrow: Arrow) -> None:
        center = self.app._cell_center(arrow.head)
        self.app._handle_click((round(center.x), round(center.y)))

    def finish_animation(self) -> None:
        self.app._update(10.0)

    def test_t01_click_unblocked_arrow_removes_it(self) -> None:
        arrow = Arrow.single("free", 1, 1, Direction.RIGHT)
        session = GameSession(make_level((arrow,)))

        result, clicked = session.click_cell(arrow.head)

        self.assertIs(result, ClickResult.REMOVED)
        self.assertEqual(clicked, arrow)
        self.assertIsNone(session.board.get_arrow(arrow.arrow_id))

    def test_t02_click_blocked_arrow_keeps_it_and_loses_one_chance(self) -> None:
        source = Arrow.single("source", 1, 0, Direction.RIGHT)
        blocker = Arrow.single("first-blocker", 1, 1, Direction.UP)
        farther = Arrow.single("farther-blocker", 1, 2, Direction.DOWN)
        level = make_level((source, blocker, farther))
        self.load_app_level(level)

        self.click_arrow(source)

        active = self.app.animations.active
        self.assertIsNotNone(active)
        assert active is not None
        self.assertIs(active.kind, AnimationKind.BLOCKED)
        self.assertEqual(active.collision_target, blocker)
        self.assertNotEqual(active.collision_target, farther)
        self.assertIsNotNone(self.app.model.board.get_arrow(source.arrow_id))
        self.assertIsNotNone(self.app.model.board.get_arrow(blocker.arrow_id))
        self.assertEqual(self.app.model.mistakes_left, level.mistake_limit - 1)
        self.assertNotIn(COLLISION_RED, DARK_THEME.arrow_palette)

    def test_t03_boundary_arrow_exits_without_error(self) -> None:
        arrow = Arrow.single("edge", 0, 0, Direction.UP)
        session = GameSession(make_level((arrow,)))

        result, _ = session.click_cell(arrow.head)

        self.assertIs(result, ClickResult.REMOVED)
        self.assertTrue(session.is_cleared)

    def test_t04_clear_level_shows_victory_and_enters_next_level(self) -> None:
        arrow = Arrow.single("last", 0, 0, Direction.UP)
        self.load_app_level(make_level((arrow,), rows=1, cols=1))

        self.click_arrow(arrow)
        self.finish_animation()

        self.assertIs(self.app.state, ScreenState.LEVEL_COMPLETE)
        self.app._run_action("next")
        self.assertIs(self.app.state, ScreenState.PLAYING)
        self.assertEqual(self.app.level_index, 1)

    def test_t05_exhausted_chances_shows_failure_and_allows_restart(self) -> None:
        left = Arrow.single("left", 0, 0, Direction.RIGHT)
        right = Arrow.single("right", 0, 1, Direction.LEFT)
        level = make_level(
            (left, right), rows=1, cols=2, mistake_limit=2
        )
        self.load_app_level(level)

        for _ in range(level.mistake_limit):
            self.click_arrow(left)
            self.finish_animation()

        self.assertIs(self.app.state, ScreenState.FAILED)
        self.app._run_action("restart")
        self.assertIs(self.app.state, ScreenState.PLAYING)
        self.assertEqual(self.app.model.mistakes_left, level.mistake_limit)
        self.assertEqual(self.app.model.remaining_arrows, 2)

    def test_t06_restart_restores_layout_and_chances(self) -> None:
        blocked = Arrow.single("blocked", 1, 0, Direction.RIGHT)
        blocker = Arrow.single("blocker", 1, 2, Direction.UP)
        removable = Arrow.single("removable", 0, 0, Direction.UP)
        level = make_level((blocked, blocker, removable))
        session = GameSession(level)

        session.click_cell(blocked.head)
        session.click_cell(removable.head)
        self.assertNotEqual(session.remaining_arrows, len(level.arrows))
        self.assertNotEqual(session.mistakes_left, level.mistake_limit)

        session.restart()

        self.assertEqual(session.mistakes_left, level.mistake_limit)
        self.assertEqual(session.remaining_arrows, len(level.arrows))
        self.assertEqual(
            {arrow.arrow_id: arrow.cells for arrow in session.board.arrows},
            {arrow.arrow_id: arrow.cells for arrow in level.arrows},
        )


if __name__ == "__main__":
    unittest.main()
