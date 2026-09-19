"""关卡数据与可扩展构建接口。"""

from .builders import LevelBuilder, ManualLevelBuilder
from .generator import (
    GeneratedLevel,
    GeneratedLevelSpec,
    LevelGenerator,
    SerpentineLevelGenerator,
)
from .levels import GENERATED_LEVELS, LEVELS

__all__ = [
    "GENERATED_LEVELS",
    "LEVELS",
    "GeneratedLevel",
    "GeneratedLevelSpec",
    "LevelGenerator",
    "LevelBuilder",
    "ManualLevelBuilder",
    "SerpentineLevelGenerator",
]

