"""关卡数据与可扩展构建接口。"""

from .basic_levels import BASIC_LEVEL_REPORTS, BASIC_LEVELS
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
from .levels import (
    ADVANCED_LEVEL_REPORTS,
    ADVANCED_LEVELS,
    LEVEL_REPORTS,
    LEVELS,
)
from .manual_levels import (
    HANDCRAFTED_LEVELS,
    HANDCRAFTED_SPECS,
    HandcraftedLevelSpec,
)
from .score_store import JsonScoreStore, MemoryScoreStore, ScoreStore

__all__ = [
    "ADVANCED_LEVEL_REPORTS",
    "ADVANCED_LEVELS",
    "ArrowShapeLimits",
    "ArrowShapeMix",
    "BASIC_LEVEL_REPORTS",
    "BASIC_LEVELS",
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

