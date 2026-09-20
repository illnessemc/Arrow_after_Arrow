"""星箭迷途：命令行入口。"""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """解析启动参数；普通版本不会暴露任何调试能力。"""
    parser = argparse.ArgumentParser(description="启动《星箭迷途》")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式，可强制移除箭头并切换关卡",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    # 延迟导入使 ``--help`` 不必初始化 Pygame 或生成固定关卡。
    from arrow_game.app import ArrowGameApp

    ArrowGameApp(debug_enabled=args.debug).run()


if __name__ == "__main__":
    main()
