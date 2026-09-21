"""基础模式三关的数据约束与可通关性测试。"""

from __future__ import annotations

import unittest

from arrow_game.core import CoverageMode, Direction, LevelSolver
from arrow_game.data import BASIC_LEVELS


class BasicLevelCatalogTest(unittest.TestCase):
    def test_three_handcrafted_levels_have_expected_names(self) -> None:
        self.assertEqual(
            [level.name for level in BASIC_LEVELS],
            ["四向起步", "交错路口", "中心连锁"],
        )

    def test_every_arrow_occupies_exactly_one_cell(self) -> None:
        for level in BASIC_LEVELS:
            with self.subTest(level=level.name):
                self.assertIs(level.coverage, CoverageMode.ALLOW_EMPTY)
                self.assertTrue(level.create_board().empty_cells)
                self.assertTrue(level.arrows)
                self.assertTrue(
                    all(len(arrow.cells) == 1 for arrow in level.arrows)
                )
                self.assertEqual(
                    {arrow.direction for arrow in level.arrows},
                    set(Direction),
                )

    def test_all_basic_levels_are_solvable(self) -> None:
        solver = LevelSolver()
        for level in BASIC_LEVELS:
            with self.subTest(level=level.name):
                report = solver.solve(level)
                self.assertTrue(report.solved)
                self.assertEqual(report.step_count, len(level.arrows))

    def test_difficulty_grows_by_arrow_count(self) -> None:
        self.assertEqual(
            [len(level.arrows) for level in BASIC_LEVELS],
            [6, 12, 16],
        )


if __name__ == "__main__":
    unittest.main()
