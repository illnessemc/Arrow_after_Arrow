"""固定主题关与无尽生成职责边界的回归测试。"""

from __future__ import annotations

import unittest

from arrow_game.core import CoverageMode, Direction, LevelSolver
from arrow_game.data import (
    HANDCRAFTED_LEVELS,
    HANDCRAFTED_SPECS,
    LEVELS,
    EndlessLevelFactory,
    LevelQualityPolicy,
    SerpentineLevelGenerator,
)


class FixedLevelCatalogTest(unittest.TestCase):
    def test_six_fixed_levels_have_expected_themes(self) -> None:
        self.assertEqual(
            [level.name for level in LEVELS],
            [
                "方向入门",
                "潮汐回廊",
                "四向机关",
                "同心星环",
                "虹桥织网",
                "星门终阵",
            ],
        )
        self.assertEqual(tuple(LEVELS[1:]), HANDCRAFTED_LEVELS)

    def test_formal_levels_use_fixed_paths_and_full_coverage(self) -> None:
        for spec, level in zip(HANDCRAFTED_SPECS, HANDCRAFTED_LEVELS):
            with self.subTest(level=level.name):
                self.assertIs(level.coverage, CoverageMode.REQUIRE_FULL)
                self.assertFalse(level.create_board().empty_cells)
                self.assertEqual(
                    tuple(arrow.cells for arrow in level.arrows),
                    spec.paths,
                )

    def test_all_fixed_levels_are_solvable(self) -> None:
        solver = LevelSolver()
        for level in LEVELS:
            with self.subTest(level=level.name):
                report = solver.solve(level)
                self.assertTrue(report.solved)
                self.assertEqual(report.step_count, len(level.arrows))

    def test_each_theme_mixes_shapes_directions_and_dependencies(self) -> None:
        for level in HANDCRAFTED_LEVELS:
            with self.subTest(level=level.name):
                directions = {arrow.direction for arrow in level.arrows}
                turn_counts = [
                    LevelQualityPolicy._turn_count(arrow.cells)
                    for arrow in level.arrows
                ]
                dependencies = LevelQualityPolicy.dependency_metrics(level)

                self.assertEqual(directions, set(Direction))
                self.assertTrue(any(turns == 0 for turns in turn_counts))
                self.assertTrue(any(turns > 0 for turns in turn_counts))
                self.assertGreaterEqual(
                    dependencies.cross_direction_ratio,
                    0.7,
                )
                self.assertGreaterEqual(
                    dependencies.largest_component_ratio,
                    0.95,
                )

    def test_only_endless_mode_owns_an_automatic_generator(self) -> None:
        factory = EndlessLevelFactory()
        self.assertIsInstance(factory.generator, SerpentineLevelGenerator)


if __name__ == "__main__":
    unittest.main()
