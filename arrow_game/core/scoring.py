"""与界面无关的倒计时、单关计分和无尽累计分模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoundScore:
    """一关完成后不可变的成绩快照。"""

    score: int
    max_score: int
    stars: int
    elapsed_seconds: float
    remaining_seconds: float


@dataclass(frozen=True, slots=True)
class ScoreRules:
    """集中保存计分公式和星级阈值，方便独立调整与测试。"""

    clear_bonus: int = 1000
    points_per_arrow: int = 10
    max_time_bonus: int = 2000
    two_star_bonus_ratio: float = 0.30
    three_star_bonus_ratio: float = 0.65

    def __post_init__(self) -> None:
        if min(self.clear_bonus, self.points_per_arrow, self.max_time_bonus) < 0:
            raise ValueError("计分项不能为负数")
        if not (
            0
            < self.two_star_bonus_ratio
            < self.three_star_bonus_ratio
            <= 1
        ):
            raise ValueError("星级阈值必须递增且位于 0～1")

    def calculate(
        self,
        *,
        time_limit_seconds: float,
        elapsed_seconds: float,
        arrow_count: int,
    ) -> RoundScore:
        """按剩余时间计算成绩；通关越快，时间奖励和星级越高。"""
        if time_limit_seconds <= 0:
            raise ValueError("时限必须大于 0")
        if arrow_count <= 0:
            raise ValueError("计分关卡至少需要一支箭头")

        elapsed = min(max(elapsed_seconds, 0.0), time_limit_seconds)
        remaining = time_limit_seconds - elapsed
        remaining_ratio = remaining / time_limit_seconds
        base_score = self.clear_bonus + arrow_count * self.points_per_arrow
        time_bonus = round(self.max_time_bonus * remaining_ratio)
        score = base_score + time_bonus
        max_score = base_score + self.max_time_bonus
        three_star_score = base_score + round(
            self.max_time_bonus * self.three_star_bonus_ratio
        )
        two_star_score = base_score + round(
            self.max_time_bonus * self.two_star_bonus_ratio
        )
        if score >= three_star_score:
            stars = 3
        elif score >= two_star_score:
            stars = 2
        else:
            stars = 1
        return RoundScore(score, max_score, stars, elapsed, remaining)


class TimedScoreSession:
    """管理一关的倒计时，并在通关时生成一次成绩快照。"""

    def __init__(
        self,
        time_limit_seconds: float,
        arrow_count: int,
        rules: ScoreRules | None = None,
    ) -> None:
        if time_limit_seconds <= 0:
            raise ValueError("时限必须大于 0")
        if arrow_count <= 0:
            raise ValueError("计分关卡至少需要一支箭头")
        self.time_limit_seconds = float(time_limit_seconds)
        self.arrow_count = arrow_count
        self.rules = rules or ScoreRules()
        self.elapsed_seconds = 0.0
        self._active = True
        self._result: RoundScore | None = None

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.time_limit_seconds - self.elapsed_seconds)

    @property
    def is_expired(self) -> bool:
        return self._result is None and self.remaining_seconds <= 0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def result(self) -> RoundScore | None:
        return self._result

    def update(self, dt: float) -> None:
        """推进倒计时；暂停页面不调用此方法即可自然暂停。"""
        if dt < 0:
            raise ValueError("时间增量不能为负数")
        if not self._active:
            return
        self.elapsed_seconds = min(
            self.time_limit_seconds,
            self.elapsed_seconds + dt,
        )
        if self.remaining_seconds <= 0:
            self._active = False

    def complete(self) -> RoundScore:
        """结束计时并返回成绩；重复调用会返回同一个结果。"""
        if self._result is not None:
            return self._result
        if self.is_expired:
            raise RuntimeError("倒计时结束后不能记录通关成绩")
        self._active = False
        self._result = self.rules.calculate(
            time_limit_seconds=self.time_limit_seconds,
            elapsed_seconds=self.elapsed_seconds,
            arrow_count=self.arrow_count,
        )
        return self._result

    def fail(self) -> None:
        """因失误或其他规则失败时停止计时，但不生成通关成绩。"""
        self._active = False


class ScoreLedger:
    """累计一次无尽挑战的分数，并保留应用生命周期内的最高分。"""

    def __init__(self, high_score: int = 0) -> None:
        if high_score < 0:
            raise ValueError("最高分不能为负数")
        self.current_score = 0
        self.high_score = high_score

    def add_round(self, result: RoundScore) -> int:
        self.current_score += result.score
        self.high_score = max(self.high_score, self.current_score)
        return self.current_score

    def start_new_run(self) -> None:
        """开始新的无尽挑战；历史最高分仍然保留。"""
        self.current_score = 0
