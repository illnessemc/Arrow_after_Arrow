"""倒计时、计分、星级和无尽累计分的单元测试。"""

from __future__ import annotations

import unittest

from arrow_game.core import ScoreLedger, ScoreRules, TimedScoreSession


class TimedScoringTest(unittest.TestCase):
    def test_countdown_clamps_at_zero(self) -> None:
        session = TimedScoreSession(30.0, arrow_count=10)
        session.update(45.0)

        self.assertEqual(session.remaining_seconds, 0.0)
        self.assertTrue(session.is_expired)
        self.assertFalse(session.is_active)

    def test_faster_completion_scores_higher(self) -> None:
        rules = ScoreRules()
        fast = rules.calculate(
            time_limit_seconds=100.0,
            elapsed_seconds=20.0,
            arrow_count=20,
        )
        slow = rules.calculate(
            time_limit_seconds=100.0,
            elapsed_seconds=90.0,
            arrow_count=20,
        )
        medium = rules.calculate(
            time_limit_seconds=100.0,
            elapsed_seconds=50.0,
            arrow_count=20,
        )

        self.assertGreater(fast.score, slow.score)
        self.assertGreater(fast.stars, slow.stars)
        self.assertEqual((fast.stars, medium.stars, slow.stars), (3, 2, 1))

    def test_complete_is_idempotent(self) -> None:
        session = TimedScoreSession(60.0, arrow_count=12)
        session.update(15.0)

        first = session.complete()
        second = session.complete()

        self.assertIs(first, second)
        self.assertFalse(session.is_active)

    def test_expired_round_cannot_award_score(self) -> None:
        session = TimedScoreSession(10.0, arrow_count=2)
        session.update(10.0)

        with self.assertRaises(RuntimeError):
            session.complete()

    def test_endless_ledger_accumulates_and_keeps_high_score(self) -> None:
        rules = ScoreRules()
        first = rules.calculate(
            time_limit_seconds=100.0,
            elapsed_seconds=30.0,
            arrow_count=20,
        )
        second = rules.calculate(
            time_limit_seconds=100.0,
            elapsed_seconds=50.0,
            arrow_count=20,
        )
        ledger = ScoreLedger()

        ledger.add_round(first)
        ledger.add_round(second)
        completed_run = ledger.current_score
        ledger.start_new_run()

        self.assertEqual(ledger.current_score, 0)
        self.assertEqual(ledger.high_score, completed_run)


if __name__ == "__main__":
    unittest.main()
