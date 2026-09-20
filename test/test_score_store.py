"""最高分存储的持久化与容错测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arrow_game.data import JsonScoreStore


class JsonScoreStoreTest(unittest.TestCase):
    def test_round_trip_high_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scores" / "score.json"
            store = JsonScoreStore(path)

            self.assertEqual(store.load_high_score(), 0)
            store.save_high_score(4321)

            self.assertEqual(JsonScoreStore(path).load_high_score(), 4321)

    def test_broken_file_falls_back_to_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "score.json"
            path.write_text("not-json", encoding="utf-8")

            self.assertEqual(JsonScoreStore(path).load_high_score(), 0)


if __name__ == "__main__":
    unittest.main()
