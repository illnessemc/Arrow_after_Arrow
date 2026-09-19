"""关卡流程求解与质量分析。

当前直线出界规则是单调的：移除箭头只会减少阻挡，不会产生新阻挡。因此
每一步选择任意可飞出的箭头都不会破坏可解性，可以用贪心流程快速验证。
如果后续机关会改变棋盘状态，可在相同接口下增加回溯求解器。
"""

from __future__ import annotations

from dataclasses import dataclass

from .game import ClickResult, GameSession
from .level import Level
from .rules import ExitRule


@dataclass(frozen=True, slots=True)
class SolveReport:
    """一次完整流程验证的结果。"""

    solved: bool
    solution: tuple[str, ...]
    choice_counts: tuple[int, ...]
    remaining_arrow_ids: tuple[str, ...] = ()

    @property
    def step_count(self) -> int:
        return len(self.solution)

    @property
    def max_choices(self) -> int:
        return max(self.choice_counts, default=0)

    @property
    def average_choices(self) -> float:
        if not self.choice_counts:
            return 0.0
        return sum(self.choice_counts) / len(self.choice_counts)

    @property
    def difficulty_score(self) -> int:
        """给关卡一个可解释的粗略难度分，供后续排序继续扩展。"""
        if not self.solved:
            return 100
        # 可选箭头越少、总步骤越多，观察依赖关系的压力越大。
        forced_steps = sum(count == 1 for count in self.choice_counts)
        return self.step_count + forced_steps * 2


class LevelSolver:
    """验证关卡能否按当前规则清空，并记录一条通关流程。"""

    def __init__(self, rule: ExitRule | None = None) -> None:
        self.rule = rule

    def solve(self, level: Level) -> SolveReport:
        session = GameSession(level, self.rule)
        solution: list[str] = []
        choice_counts: list[int] = []

        while not session.is_cleared:
            safe_arrows = [
                arrow for arrow in session.board.arrows if session.can_exit(arrow)
            ]
            choice_counts.append(len(safe_arrows))
            if not safe_arrows:
                return SolveReport(
                    solved=False,
                    solution=tuple(solution),
                    choice_counts=tuple(choice_counts),
                    remaining_arrow_ids=tuple(
                        arrow.arrow_id for arrow in session.board.arrows
                    ),
                )

            chosen = safe_arrows[0]
            result, _ = session.click_cell(chosen.head)
            if result is not ClickResult.REMOVED:
                raise RuntimeError("求解器与游戏规则状态不一致")
            solution.append(chosen.arrow_id)

        return SolveReport(
            solved=True,
            solution=tuple(solution),
            choice_counts=tuple(choice_counts),
        )

    def require_solvable(self, level: Level) -> SolveReport:
        """验证关卡；出现死锁时直接拒绝加载。"""
        report = self.solve(level)
        if not report.solved:
            raise ValueError(
                f"关卡 {level.name} 无解，剩余箭头：{report.remaining_arrow_ids}"
            )
        return report
