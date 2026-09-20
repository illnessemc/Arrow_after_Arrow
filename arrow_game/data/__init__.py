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
from .levels import GENERATED_LEVELS, LEVELS

__all__ = [
    "ArrowShapeLimits",
    "ArrowShapeMix",
    "CoveragePattern",
    "DependencyMetrics",
    "EndlessLevelFactory",
    "GENERATED_LEVELS",
    "LEVELS",
    "GeneratedLevel",
    "GeneratedLevelSpec",
    "LevelGenerator",
    "LevelQualityPolicy",
    "LevelBuilder",
    "ManualLevelBuilder",
    "SerpentineLevelGenerator",
]

