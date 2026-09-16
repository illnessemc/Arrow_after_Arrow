"""一箭又一箭：程序入口。

入口只负责创建应用，玩法规则和窗口界面分别由 arrow_game 中的模块实现。
"""

from arrow_game.app import ArrowGameApp


if __name__ == "__main__":
    ArrowGameApp().run()
