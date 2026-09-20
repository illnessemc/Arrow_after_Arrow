"""关卡数据与可扩展构建接口。"""

from .builders import LevelBuilder, ManualLevelBuilder
from .generator import (
    ArrowShapeMix,
    CoveragePattern,
    GeneratedLevel,
    GeneratedLevelSpec,
    LevelGenerator,
    LevelQualityPolicy,
    SerpentineLevelGenerator,
)
from .levels import GENERATED_LEVELS, LEVELS

__all__ = [
    "ArrowShapeMix",
    "CoveragePattern",
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

