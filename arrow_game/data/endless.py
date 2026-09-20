"""无尽模式关卡工厂。

每次进入下一轮才使用新随机种子在线生成。生成器与固定关卡共用求解器和质量
策略，因此只有完整覆盖、能够通关且依赖关系合格的候选才会交给游戏界面。
"""

from __future__ import annotations

import random

from arrow_game.core import LevelSolver

from .generator import (
    ArrowShapeMix,
    CoveragePattern,
    GeneratedLevel,
    GeneratedLevelSpec,
    SerpentineLevelGenerator,
)


class EndlessLevelFactory:
    """按轮次创建一个经过验证的随机关卡，不保存已经完成的历史关卡。"""

    def __init__(
        self,
        generator: SerpentineLevelGenerator | None = None,
        random_source: random.Random | random.SystemRandom | None = None,
        max_seed_attempts: int = 12,
    ) -> None:
        if max_seed_attempts <= 0:
            raise ValueError("无尽关卡的种子尝试次数必须为正数")
        self.generator = generator or SerpentineLevelGenerator(LevelSolver())
        self.random_source = random_source or random.SystemRandom()
        self.max_seed_attempts = max_seed_attempts
        self._last_seed: int | None = None

    def generate(self, round_number: int) -> GeneratedLevel:
        """随机尝试若干种子，返回首个可解且达到质量门槛的关卡。"""
        if round_number <= 0:
            raise ValueError("无尽模式轮次必须为正数")

        for _ in range(self.max_seed_attempts):
            seed = self.random_source.randrange(1, 2_147_483_647)
            if seed == self._last_seed:
                continue
            spec = self._spec(round_number, seed)
            try:
                generated = self.generator.generate(spec)
            except ValueError:
                # 单个种子未在候选上限内达到质量门槛时换种子，不把失败
                # 状态泄漏给游戏流程，也不会缓存该候选占用内存。
                continue
            self._last_seed = seed
            return generated
        raise RuntimeError(
            f"无尽模式第 {round_number} 关生成失败，请重新尝试"
        )

    @staticmethod
    def _spec(round_number: int, seed: int) -> GeneratedLevelSpec:
        """随轮次缓慢放大棋盘，尺寸封顶以保持启动时间和内存稳定。"""
        rows = min(30, 20 + ((round_number - 1) // 3) * 2)
        cols = min(20, 14 + ((round_number - 1) // 4) * 2)
        multi_turn = min(0.5, 0.3 + ((round_number - 1) % 5) * 0.04)
        straight = max(0.15, 0.3 - ((round_number - 1) % 4) * 0.03)
        single_turn = 1.0 - straight - multi_turn
        return GeneratedLevelSpec(
            name=f"无尽挑战 {round_number}",
            rows=rows,
            cols=cols,
            seed=seed,
            min_arrow_length=2,
            max_arrow_length=16,
            mistake_limit=3,
            boundary_break_chance=0.3,
            path_mix_factor=2.0,
            coverage_pattern=CoveragePattern.GLOBAL_WEAVE,
            shape_mix=ArrowShapeMix(
                straight=straight,
                single_turn=single_turn,
                multi_turn=multi_turn,
            ),
            max_generation_attempts=40,
            time_limit_seconds=min(240.0, 150.0 + (round_number - 1) * 8.0),
        )
