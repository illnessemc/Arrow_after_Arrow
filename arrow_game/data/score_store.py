"""无尽模式最高分的可替换存储接口与本地 JSON 实现。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol


class ScoreStore(Protocol):
    def load_high_score(self) -> int:
        ...

    def save_high_score(self, score: int) -> None:
        ...


class MemoryScoreStore:
    """测试和临时运行使用的内存实现。"""

    def __init__(self, high_score: int = 0) -> None:
        self.high_score = max(0, high_score)

    def load_high_score(self) -> int:
        return self.high_score

    def save_high_score(self, score: int) -> None:
        self.high_score = max(self.high_score, score)


class JsonScoreStore:
    """在用户数据目录原子保存最高分，不向项目仓库写运行数据。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def project_default(cls) -> JsonScoreStore:
        local_data = os.environ.get("LOCALAPPDATA")
        root = Path(local_data) if local_data else Path.home() / ".local" / "share"
        return cls(root / "StarArrow" / "score.json")

    def load_high_score(self) -> int:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            score = int(data.get("endless_high_score", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 0
        return max(0, score)

    def save_high_score(self, score: int) -> None:
        if score < 0:
            raise ValueError("最高分不能为负数")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"endless_high_score": score}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)
