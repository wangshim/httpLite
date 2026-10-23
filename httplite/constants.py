# -*- coding: utf-8 -*-
"""HttpLite 常量与主题定义。"""
from __future__ import annotations
import re
APP_NAME = "HttpLite"
APP_TITLE = "HttpLite · 轻量接口测试工具"
CURRENT_VERSION = "1.6.0"
GITHUB_REPO = "wangshim/httpLite"
GITHUB_REPO_URL = "https://github.com/" + GITHUB_REPO
GITHUB_RELEASES_API = "https://api.github.com/repos/" + GITHUB_REPO + "/releases/latest"
METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
VAR_RX = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
STATUS_COLORS = {
    "2": "#3ecf8e",
    "3": "#5aa9f0",
    "4": "#f0a45d",
    "5": "#f05f5f",
}
AUTH_TYPE_LABELS = [
    "无认证",
    "Bearer Token",
    "Basic Auth",
    "Digest Auth",
    "API Key",
    "AWS Signature v4",
    "JWT",
    "OAuth 2.0",
]
AUTH_TYPE_KEYS = ["noauth", "bearer", "basic", "digest", "apikey", "awsv4", "jwt", "oauth2"]
JWT_ALGORITHMS = ["HS256", "HS384", "HS512", "none"]
OAUTH2_GRANTS = [
    ("client_credentials", "Client Credentials（客户端凭证）"),
    ("password", "Password（密码模式）"),
    ("authorization_code", "Authorization Code（授权码模式）"),
]
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
POSTMAN_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
ASSERT_TYPES = [
    ("status_eq", "状态码等于"),
    ("status_range", "状态码范围"),
    ("time_lt", "耗时小于(ms)"),
    ("body_contains", "响应体包含"),
    ("json_exists", "JSON 字段存在"),
    ("json_eq", "JSON 字段值等于"),
]
EXTRACT_TYPES = [
    ("jsonpath", "JSON 路径"),
    ("regex", "正则"),
]
THEME_COLORS = {
    "dark": {
        "hint": "#9aa0a6",
        "muted": "#6b7075",
        "preview": "#7ec8ff",
        "chip_default_bg": "#2b2d31",
        "chip_default_fg": "#c8ccd1",
        "chip_busy_bg": "#2b2d31",
        "chip_busy_fg": "#f0a45d",
        "chip_err_bg": "#4a2222",
        "chip_err_fg": "#f05f5f",
    },
    "light": {
        "hint": "#5f6368",
        "muted": "#80868b",
        "preview": "#1a73e8",
        "chip_default_bg": "#f1f3f4",
        "chip_default_fg": "#5f6368",
        "chip_busy_bg": "#fef7e8",
        "chip_busy_fg": "#b06000",
        "chip_err_bg": "#fdecea",
        "chip_err_fg": "#d93025",
    },
}
THEMES = {
    "dark": """
QWidget { font-family: "Microsoft YaHei UI","Segoe UI",sans-serif; font-size: 12px; }
QMainWindow, QDialog { background: #1b1c1f; }
QWidget { color: #d7dae0; }
QLineEdit, QPlainTextEdit, QTableWidget, QListWidget, QTreeWidget, QComboBox, QSpinBox {
    background: #24262a; border: 1px solid #34373d; border-radius: 6px;
    selection-background-color: #3a6ea5; selection-color: #ffffff;
}
QLineEdit { padding: 6px 8px; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #ff8b3d; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView { background: #24262a; border: 1px solid #34373d; }
QPlainTextEdit { padding: 6px; }
QPushButton {
    background: #2d3035; border: 1px solid #3a3e44; border-radius: 6px;
    padding: 6px 12px; color: #dfe2e6;
}
QPushButton:hover { background: #363a41; border-color: #4a4f57; }
QPushButton:pressed { background: #24262a; }
QPushButton#primary { background: #ff6f3c; border: none; color: #ffffff; font-weight: 700; }
QPushButton#primary:hover { background: #ff8253; }
QPushButton#primary:disabled { background: #5a4034; color: #b9a79f; }
QTabWidget::pane { border: 1px solid #2c2f34; border-radius: 8px; top: -1px; }
QTabBar::tab {
    background: transparent; color: #9aa0a6; padding: 7px 14px;
    border: 1px solid transparent; border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #24262a; color: #ffffff; border-color: #2c2f34; }
QTabBar::tab:hover { color: #e6e8ea; }
QHeaderView::section {
    background: #24262a; color: #9aa0a6; padding: 5px 6px; border: none;
    border-right: 1px solid #2c2f34; border-bottom: 1px solid #2c2f34;
}
QTableWidget { gridline-color: #2c2f34; }
QListWidget::item, QTreeWidget::item { padding: 4px 6px; border-radius: 4px; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #3a6ea5; color: #ffffff; }
QSplitter::handle { background: #2c2f34; }
QSplitter::handle:horizontal { width: 4px; }
QSplitter::handle:vertical { height: 4px; }
QCheckBox { spacing: 6px; }
QStatusBar { color: #8d949c; }
QScrollBar:vertical { background: #1b1c1f; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #3a3e44; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4a4f57; }
QScrollBar:horizontal { background: #1b1c1f; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #3a3e44; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QMenu { background: #24262a; border: 1px solid #34373d; padding: 4px; }
QMenu::item { padding: 6px 20px; border-radius: 4px; }
QMenu::item:selected { background: #3a6ea5; }
""",
    "light": """
QWidget { font-family: "Microsoft YaHei UI","Segoe UI",sans-serif; font-size: 12px; }
QMainWindow, QDialog { background: #f7f8fa; }
QWidget { color: #202124; }
QLineEdit, QPlainTextEdit, QTableWidget, QListWidget, QTreeWidget, QComboBox, QSpinBox {
    background: #ffffff; border: 1px solid #dadce0; border-radius: 6px;
    selection-background-color: #1a73e8; selection-color: #ffffff;
}
QLineEdit { padding: 6px 8px; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #ff8b3d; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #dadce0; }
QPlainTextEdit { padding: 6px; }
QPushButton {
    background: #ffffff; border: 1px solid #dadce0; border-radius: 6px;
    padding: 6px 12px; color: #202124;
}
QPushButton:hover { background: #f1f3f4; border-color: #c6c9cd; }
QPushButton:pressed { background: #e8eaed; }
QPushButton#primary { background: #ff6f3c; border: none; color: #ffffff; font-weight: 700; }
QPushButton#primary:hover { background: #ff8253; }
QPushButton#primary:disabled { background: #e8c9ba; color: #ffffff; }
QTabWidget::pane { border: 1px solid #dadce0; border-radius: 8px; top: -1px; }
QTabBar::tab {
    background: transparent; color: #5f6368; padding: 7px 14px;
    border: 1px solid transparent; border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #ffffff; color: #202124; border-color: #dadce0; }
QTabBar::tab:hover { color: #202124; }
QHeaderView::section {
    background: #f1f3f4; color: #5f6368; padding: 5px 6px; border: none;
    border-right: 1px solid #dadce0; border-bottom: 1px solid #dadce0;
}
QTableWidget { gridline-color: #e8eaed; }
QListWidget::item, QTreeWidget::item { padding: 4px 6px; border-radius: 4px; }
QListWidget::item:selected, QTreeWidget::item:selected { background: #1a73e8; color: #ffffff; }
QSplitter::handle { background: #dadce0; }
QSplitter::handle:horizontal { width: 4px; }
QSplitter::handle:vertical { height: 4px; }
QCheckBox { spacing: 6px; }
QStatusBar { color: #5f6368; }
QScrollBar:vertical { background: #f7f8fa; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #c6c9cd; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #aeb2b8; }
QScrollBar:horizontal { background: #f7f8fa; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #c6c9cd; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QMenu { background: #ffffff; border: 1px solid #dadce0; padding: 4px; }
QMenu::item { padding: 6px 20px; border-radius: 4px; }
QMenu::item:selected { background: #1a73e8; }
""",
}
