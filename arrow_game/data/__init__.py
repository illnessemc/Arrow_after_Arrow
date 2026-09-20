"""关卡数据与可扩展构建接口。"""

from .builders import LevelBuilder, ManualLevelBuilder
from .endless import EndlessLevelFactory
from .generator import (
    ArrowShapeLimits,
    ArrowShapeMix,
    CoveragePattern,
    DependencyMetrics,
    GeneratedLevel,
    GeneratedLevelSpec,
    LevelGenerator,
    LevelQualityPolicy,
    SerpentineLevelGenerator,
)
from .levels import LEVELS, LEVEL_REPORTS
from .manual_levels import (
    HANDCRAFTED_LEVELS,
    HANDCRAFTED_SPECS,
    HandcraftedLevelSpec,
)
from .score_store import JsonScoreStore, MemoryScoreStore, ScoreStore

__all__ = [
    "ArrowShapeLimits",
    "ArrowShapeMix",
    "CoveragePattern",
    "DependencyMetrics",
    "EndlessLevelFactory",
    "HANDCRAFTED_LEVELS",
    "HANDCRAFTED_SPECS",
    "LEVELS",
    "LEVEL_REPORTS",
    "GeneratedLevel",
    "GeneratedLevelSpec",
    "HandcraftedLevelSpec",
    "LevelGenerator",
    "LevelQualityPolicy",
    "LevelBuilder",
    "ManualLevelBuilder",
    "JsonScoreStore",
    "MemoryScoreStore",
    "ScoreStore",
    "SerpentineLevelGenerator",
]

