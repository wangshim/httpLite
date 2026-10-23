# -*- coding: utf-8 -*-
"""HttpLite 入口文件（结构化包 httplite 的启动入口）。

保留单文件入口语义：python app.py [--self-test] [--ui-shot <dir> [dark|light]]
实际逻辑拆分在 httplite 包内（界面 / 请求 / 认证 / 持久化 / 自检等模块）。
"""
from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from httplite.constants import APP_NAME, APP_TITLE, THEMES
from httplite.persistence import app_dir
from httplite.selftest import run_self_test, run_ui_shot
from httplite.ui import MainWindow, make_app_icon


def main() -> None:
    if "--self-test" in sys.argv:
        run_self_test()
        return
    if "--ui-shot" in sys.argv:
        pos = sys.argv.index("--ui-shot")
        target = sys.argv[pos + 1] if len(sys.argv) > pos + 1 else app_dir()
        theme = None
        if len(sys.argv) > pos + 2 and sys.argv[pos + 2] in ("dark", "light"):
            theme = sys.argv[pos + 2]
        run_ui_shot(target, theme)
        return
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setStyleSheet(THEMES["dark"])
    app.setWindowIcon(make_app_icon())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
