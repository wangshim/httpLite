# -*- coding: utf-8 -*-
"""
HttpLite —— 轻量级 HTTP 接口测试工具（类 Postman）
绿色便携：单文件 exe，免安装、不写注册表，数据保存在 exe 同级目录。
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import parse_qsl

import requests

try:
    import urllib3

    urllib3.disable_warnings()
except Exception:  # pragma: no cover
    pass

from PySide6.QtCore import Qt, QThread, Signal, QRegularExpression, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPixmap,
    QBrush,
    QLinearGradient,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "HttpLite"
APP_TITLE = "HttpLite · 轻量接口测试工具"
METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
VAR_RX = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

STATUS_COLORS = {
    "2": "#3ecf8e",
    "3": "#5aa9f0",
    "4": "#f0a45d",
    "5": "#f05f5f",
}


# --------------------------------------------------------------------------
# 路径与数据持久化（绿色便携：数据写在 exe 同级目录）
# --------------------------------------------------------------------------
def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def data_root() -> str:
    """优先使用 exe 同级目录；不可写时回退到用户 AppData。"""
    preferred = os.path.join(app_dir(), "HttpLite_data")
    try:
        os.makedirs(preferred, exist_ok=True)
        probe = os.path.join(preferred, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return preferred
    except Exception:
        fallback = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")), "HttpLite_data"
        )
        os.makedirs(fallback, exist_ok=True)
        return fallback


DATA_DIR = data_root()
DATA_FILE = os.path.join(DATA_DIR, "workspace.json")


def default_state() -> dict:
    return {
        "history": [],
        "collections": [
            {
                "id": "c1",
                "type": "folder",
                "name": "我的集合",
                "children": [
                    {
                        "id": "r1",
                        "type": "request",
                        "name": "示例：GET 请求",
                        "request": {
                            "method": "GET",
                            "url": "{{base_url}}/get?name=HttpLite",
                            "params": [],
                            "headers": [{"key": "Accept", "value": "application/json", "enabled": True}],
                            "body_type": "none",
                            "body_json": "",
                            "body_form": [],
                        },
                    },
                    {
                        "id": "r2",
                        "type": "request",
                        "name": "示例：POST JSON",
                        "request": {
                            "method": "POST",
                            "url": "{{base_url}}/post",
                            "params": [],
                            "headers": [{"key": "Content-Type", "value": "application/json", "enabled": True}],
                            "body_type": "json",
                            "body_json": '{\n    "name": "HttpLite",\n    "token": "{{token}}"\n}',
                            "body_form": [],
                        },
                    },
                ],
            }
        ],
        "environments": [
            {
                "name": "默认环境",
                "variables": [
                    {"key": "base_url", "value": "https://httpbin.org", "enabled": True},
                    {"key": "token", "value": "", "enabled": True},
                ],
            },
            {
                "name": "本地调试",
                "variables": [
                    {"key": "base_url", "value": "http://127.0.0.1:8000", "enabled": True},
                    {"key": "token", "value": "local-dev-token", "enabled": True},
                ],
            },
        ],
        "active_env": "默认环境",
        "settings": {"timeout": 30, "verify": True, "follow_redirects": True},
    }


def load_state() -> dict:
    if os.path.isfile(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = default_state()
            for k, v in base.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    st = default_state()
    save_state(st)
    return st


def save_state(state: dict) -> None:
    try:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)
    except Exception:
        pass


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------
def fmt_size(n: int) -> str:
    if n is None:
        return "-"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.2f} MB"


def fmt_ms(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"


def substitute(text: str, variables: dict) -> str:
    if not text:
        return text

    def rep(m):
        key = m.group(1)
        if key in variables:
            return variables[key]
        return m.group(0)

    return VAR_RX.sub(rep, text)


def pretty_json(text: str):
    try:
        obj = json.loads(text)
    except Exception:
        return None
    return json.dumps(obj, ensure_ascii=False, indent=4)


def make_app_icon() -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    grad = QLinearGradient(0, 0, 256, 256)
    grad.setColorAt(0.0, QColor("#ff6f3c"))
    grad.setColorAt(1.0, QColor("#ff9e2c"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(8, 8, 240, 240, 52, 52)
    f = QFont("Arial", 130)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#ffffff"))
    p.drawText(pm.rect(), Qt.AlignCenter, "H")
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------
# JSON 语法高亮
# --------------------------------------------------------------------------
class JsonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []

        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor("#7ec8ff"))
        key_fmt.setFontWeight(QFont.Weight.Bold)

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#8ddb8a"))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#f0a45d"))

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#c792ea"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)

        self.rules.append((QRegularExpression(r'"(?:[^"\\]|\\.)*"(?=\s*:)'), key_fmt))
        self.rules.append((QRegularExpression(r'"(?:[^"\\]|\\.)*"'), str_fmt))
        self.rules.append((QRegularExpression(r"\b-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"), num_fmt))
        self.rules.append((QRegularExpression(r"\b(?:true|false|null)\b"), kw_fmt))

    def highlightBlock(self, text: str) -> None:
        for rx, fmt in self.rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# --------------------------------------------------------------------------
# 键值表（Params / Headers / form-data / 环境变量 复用）
# --------------------------------------------------------------------------
class KeyValueTable(QTableWidget):
    def __init__(self, parent=None, key_label="键", value_label="值"):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["启用", key_label, value_label])
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.setColumnWidth(0, 48)
        self.setColumnWidth(1, 220)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.cellChanged.connect(self._on_cell_changed)
        self._loading = False
        self.add_row()

    # -- 行操作 ------------------------------------------------------------
    def add_row(self, key="", value="", enabled=True) -> int:
        self._loading = True
        r = self.rowCount()
        self.insertRow(r)

        it_en = QTableWidgetItem()
        it_en.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        it_en.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        self.setItem(r, 0, it_en)

        self.setItem(r, 1, QTableWidgetItem(str(key or "")))
        self.setItem(r, 2, QTableWidgetItem(str(value or "")))
        self._loading = False
        return r

    def delete_selected(self) -> None:
        rows = sorted({i.row() for i in self.selectedIndexes()}, reverse=True)
        if not rows:
            rows = [self.rowCount() - 1]
        self._loading = True
        for r in rows:
            if 0 <= r < self.rowCount():
                self.removeRow(r)
        self._loading = False
        if self.rowCount() == 0:
            self.add_row()

    def clear_all(self) -> None:
        self._loading = True
        self.setRowCount(0)
        self._loading = False
        self.add_row()

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        act_add = menu.addAction("新增一行")
        act_del = menu.addAction("删除选中行")
        menu.addSeparator()
        act_clear = menu.addAction("清空")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == act_add:
            self.add_row()
        elif chosen == act_del:
            self.delete_selected()
        elif chosen == act_clear:
            self.clear_all()

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._loading:
            return
        last = self.rowCount() - 1
        if row == last:
            k = self.item(row, 1)
            v = self.item(row, 2)
            if (k and k.text().strip()) or (v and v.text().strip()):
                self.add_row()

    # -- 数据 --------------------------------------------------------------
    def pairs(self, with_enabled=False):
        out = []
        for r in range(self.rowCount()):
            en_item = self.item(r, 0)
            enabled = bool(en_item and en_item.checkState() == Qt.Checked)
            k_item = self.item(r, 1)
            v_item = self.item(r, 2)
            key = k_item.text().strip() if k_item else ""
            value = v_item.text() if v_item else ""
            if not key:
                continue
            if with_enabled:
                out.append({"key": key, "value": value, "enabled": enabled})
            elif enabled:
                out.append((key, value))
        return out

    def set_pairs(self, pairs) -> None:
        self._loading = True
        self.setRowCount(0)
        self._loading = False
        self.add_row()
        for p in pairs or []:
            if isinstance(p, dict):
                self.add_row(p.get("key", ""), p.get("value", ""), p.get("enabled", True))
            else:
                self.add_row(p[0], p[1], True)

    def rename_headers(self, k_label: str, v_label: str) -> None:
        self.setHorizontalHeaderLabels(["启用", k_label, v_label])


# --------------------------------------------------------------------------
# 请求线程
# --------------------------------------------------------------------------
class HttpWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self) -> None:  # noqa: C901
        p = self.payload
        try:
            t0 = time.perf_counter()
            kwargs = {
                "method": p["method"],
                "url": p["url"],
                "headers": p.get("headers") or None,
                "params": p.get("params") or None,
                "timeout": p.get("timeout", 30),
                "verify": p.get("verify", True),
                "allow_redirects": p.get("allow_redirects", True),
            }
            if p.get("files") is not None:
                kwargs["files"] = p["files"]
            elif p.get("data") is not None:
                kwargs["data"] = p["data"]
            elif p.get("json") is not None:
                kwargs["json"] = p["json"]

            resp = requests.request(**kwargs)
            elapsed = (time.perf_counter() - t0) * 1000.0
            content = resp.content or b""
            try:
                text = resp.text
            except Exception:
                text = repr(content)

            self.done.emit(
                {
                    "status_code": resp.status_code,
                    "reason": resp.reason or "",
                    "headers": list(resp.headers.items()),
                    "text": text,
                    "elapsed_ms": elapsed,
                    "size": len(content),
                    "final_url": resp.url,
                    "redirects": [
                        {"status": h.status_code, "url": h.url} for h in resp.history
                    ],
                }
            )
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            low = msg.lower()
            if "ssl" in low or "certificate" in low:
                msg += "\n提示：可在工具栏勾选“忽略 SSL 证书”后重试。"
            self.failed.emit(msg)


# --------------------------------------------------------------------------
# 环境管理对话框
# --------------------------------------------------------------------------
class EnvDialog(QDialog):
    def __init__(self, environments: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("环境变量管理")
        self.resize(760, 460)
        self.envs = json.loads(json.dumps(environments or []))
        if not self.envs:
            self.envs = [{"name": "默认环境", "variables": []}]
        self.current = 0

        root = QVBoxLayout(self)
        tip = QLabel("用法：在 URL / Headers / Body 中使用 {{变量名}}，发送时会按当前环境替换。")
        tip.setStyleSheet("color:#9aa0a6;")
        root.addWidget(tip)

        body = QHBoxLayout()
        root.addLayout(body, 1)

        left = QVBoxLayout()
        body.addLayout(left, 0)
        self.list = QListWidget()
        self.list.setFixedWidth(220)
        self.list.currentRowChanged.connect(self._switch_env)
        left.addWidget(self.list, 1)

        btns = QHBoxLayout()
        b_add = QPushButton("新建")
        b_dup = QPushButton("复制")
        b_ren = QPushButton("重命名")
        b_del = QPushButton("删除")
        for b in (b_add, b_dup, b_ren, b_del):
            btns.addWidget(b)
        left.addLayout(btns)
        b_add.clicked.connect(self._new_env)
        b_dup.clicked.connect(self._dup_env)
        b_ren.clicked.connect(self._rename_env)
        b_del.clicked.connect(self._del_env)

        right = QVBoxLayout()
        body.addLayout(right, 1)
        right.addWidget(QLabel("变量列表（可取消勾选临时停用某个变量）"))
        self.table = KeyValueTable()
        right.addWidget(self.table, 1)
        row = QHBoxLayout()
        b_row_add = QPushButton("新增一行")
        b_row_del = QPushButton("删除选中行")
        row.addWidget(b_row_add)
        row.addWidget(b_row_del)
        row.addStretch(1)
        right.addLayout(row)
        b_row_add.clicked.connect(lambda: self.table.add_row())
        b_row_del.clicked.connect(self.table.delete_selected)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._reload_list()

    def _reload_list(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for e in self.envs:
            self.list.addItem(e.get("name", "未命名环境"))
        self.list.blockSignals(False)
        self.current = max(0, min(self.current, len(self.envs) - 1))
        self.list.setCurrentRow(self.current)
        self._load_env(self.current)

    def _sync(self) -> None:
        if 0 <= self.current < len(self.envs):
            self.envs[self.current]["variables"] = self.table.pairs(with_enabled=True)

    def _load_env(self, idx: int) -> None:
        if not (0 <= idx < len(self.envs)):
            return
        self.table.set_pairs(self.envs[idx].get("variables", []))

    def _switch_env(self, idx: int) -> None:
        if idx < 0 or idx == self.current:
            return
        self._sync()
        self.current = idx
        self._load_env(idx)

    def _new_env(self) -> None:
        self._sync()
        self.envs.append({"name": f"环境{len(self.envs) + 1}", "variables": []})
        self.current = len(self.envs) - 1
        self._reload_list()

    def _dup_env(self) -> None:
        self._sync()
        src = self.envs[self.current]
        self.envs.append(
            {
                "name": src.get("name", "环境") + " 副本",
                "variables": json.loads(json.dumps(src.get("variables", []))),
            }
        )
        self.current = len(self.envs) - 1
        self._reload_list()

    def _rename_env(self) -> None:
        name, ok = self._ask("重命名环境", "新的环境名称：", self.envs[self.current].get("name", ""))
        if ok and name.strip():
            self._sync()
            self.envs[self.current]["name"] = name.strip()
            self._reload_list()

    def _del_env(self) -> None:
        if len(self.envs) <= 1:
            QMessageBox.information(self, "提示", "至少需要保留一个环境。")
            return
        if QMessageBox.question(self, "确认", "确定删除当前环境？") != QMessageBox.Yes:
            return
        self.envs.pop(self.current)
        self.current = max(0, self.current - 1)
        self._reload_list()

    def _ask(self, title, label, text):
        return QInputDialog.getText(self, title, label, text=text)

    def _on_ok(self) -> None:
        self._sync()
        for i, e in enumerate(self.envs):
            if not e.get("name", "").strip():
                e["name"] = f"环境{i + 1}"
        self.accept()

    def result_data(self) -> list:
        return self.envs


# --------------------------------------------------------------------------
# 主窗口
# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.state = load_state()
        self.worker = None
        self.last_response = None
        self.current_request_id = None

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(make_app_icon())
        self.resize(1320, 860)
        self.setMinimumSize(1024, 660)

        self._build_ui()
        self._load_settings()
        self._refresh_env_combo()
        self._rebuild_history()
        self._rebuild_collections()
        self.status_msg("就绪。数据目录：" + DATA_DIR)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ---- 顶部：方法 + URL + 发送 ----
        top = QHBoxLayout()
        top.setSpacing(6)
        self.method_combo = QComboBox()
        self.method_combo.addItems(METHODS)
        self.method_combo.setFixedWidth(112)
        self.method_combo.setStyleSheet("font-weight:600;")
        top.addWidget(self.method_combo)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("请输入请求地址，支持 {{变量}}，例如 {{base_url}}/api/login")
        self.url_edit.returnPressed.connect(self.send_request)
        top.addWidget(self.url_edit, 1)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("primary")
        self.send_btn.setFixedWidth(96)
        self.send_btn.clicked.connect(self.send_request)
        top.addWidget(self.send_btn)

        self.save_btn = QPushButton("保存到集合")
        self.save_btn.setFixedWidth(110)
        self.save_btn.clicked.connect(self.save_to_collection)
        top.addWidget(self.save_btn)
        root.addLayout(top)

        # ---- 第二行：环境 / 选项 ----
        opts = QHBoxLayout()
        opts.setSpacing(8)
        opts.addWidget(QLabel("环境："))
        self.env_combo = QComboBox()
        self.env_combo.setMinimumWidth(160)
        self.env_combo.currentIndexChanged.connect(self._on_env_changed)
        opts.addWidget(self.env_combo)
        self.env_btn = QPushButton("管理环境")
        self.env_btn.clicked.connect(self.manage_envs)
        opts.addWidget(self.env_btn)

        opts.addSpacing(12)
        self.verify_chk = QCheckBox("忽略 SSL 证书")
        opts.addWidget(self.verify_chk)
        self.redirect_chk = QCheckBox("跟随重定向")
        opts.addWidget(self.redirect_chk)
        opts.addWidget(QLabel("超时(秒)："))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 600)
        self.timeout_spin.setFixedWidth(72)
        opts.addWidget(self.timeout_spin)
        opts.addStretch(1)
        self.var_hint = QLabel("")
        self.var_hint.setStyleSheet("color:#9aa0a6;")
        opts.addWidget(self.var_hint)
        root.addLayout(opts)

        # ---- 主体：左（历史/集合）右（请求/响应） ----
        main_split = QSplitter(Qt.Horizontal)
        root.addWidget(main_split, 1)

        left = QTabWidget()
        left.setMinimumWidth(240)
        left.setMaximumWidth(460)

        # 历史
        hist_wrap = QWidget()
        hv = QVBoxLayout(hist_wrap)
        hv.setContentsMargins(6, 6, 6, 6)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._load_history_item)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._history_menu)
        hv.addWidget(self.history_list, 1)
        hb = QHBoxLayout()
        h_clear = QPushButton("清空历史")
        h_clear.clicked.connect(self.clear_history)
        hb.addWidget(h_clear)
        hb.addStretch(1)
        hv.addLayout(hb)
        left.addTab(hist_wrap, "历史记录")

        # 集合
        coll_wrap = QWidget()
        cv = QVBoxLayout(coll_wrap)
        cv.setContentsMargins(6, 6, 6, 6)
        self.coll_tree = QTreeWidget()
        self.coll_tree.setHeaderHidden(True)
        self.coll_tree.itemDoubleClicked.connect(self._load_collection_item)
        self.coll_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.coll_tree.customContextMenuRequested.connect(self._collection_menu)
        cv.addWidget(self.coll_tree, 1)
        cb = QHBoxLayout()
        c_add_folder = QPushButton("新建文件夹")
        c_add_folder.clicked.connect(self.new_collection_folder)
        c_save = QPushButton("保存当前请求")
        c_save.clicked.connect(self.save_to_collection)
        cb.addWidget(c_add_folder)
        cb.addWidget(c_save)
        cv.addLayout(cb)
        left.addTab(coll_wrap, "集合")

        main_split.addWidget(left)

        right_split = QSplitter(Qt.Vertical)
        main_split.addWidget(right_split)
        main_split.setSizes([300, 1020])

        # 请求区
        req_tabs = QTabWidget()
        right_split.addWidget(req_tabs)

        # Params
        params_wrap = QWidget()
        pv = QVBoxLayout(params_wrap)
        pv.setContentsMargins(6, 6, 6, 6)
        self.params_table = KeyValueTable()
        pv.addWidget(self.params_table, 1)
        pb = QHBoxLayout()
        p_add = QPushButton("新增一行")
        p_add.clicked.connect(lambda: self.params_table.add_row())
        p_del = QPushButton("删除选中行")
        p_del.clicked.connect(self.params_table.delete_selected)
        p_import = QPushButton("从 URL 导入参数")
        p_import.clicked.connect(self.import_url_params)
        pb.addWidget(p_add)
        pb.addWidget(p_del)
        pb.addWidget(p_import)
        pb.addStretch(1)
        pv.addLayout(pb)
        req_tabs.addTab(params_wrap, "Query 参数")

        # Headers
        head_wrap = QWidget()
        hv2 = QVBoxLayout(head_wrap)
        hv2.setContentsMargins(6, 6, 6, 6)
        self.headers_table = KeyValueTable()
        hv2.addWidget(self.headers_table, 1)
        hb2 = QHBoxLayout()
        h_add = QPushButton("新增一行")
        h_add.clicked.connect(lambda: self.headers_table.add_row())
        h_del = QPushButton("删除选中行")
        h_del.clicked.connect(self.headers_table.delete_selected)
        h_preset = QPushButton("常用 Header")
        h_preset.clicked.connect(self._insert_common_headers)
        hb2.addWidget(h_add)
        hb2.addWidget(h_del)
        hb2.addWidget(h_preset)
        hb2.addStretch(1)
        hv2.addLayout(hb2)
        req_tabs.addTab(head_wrap, "Headers")

        # Body
        body_wrap = QWidget()
        bv = QVBoxLayout(body_wrap)
        bv.setContentsMargins(6, 6, 6, 6)
        bt = QHBoxLayout()
        bt.addWidget(QLabel("Body 类型："))
        self.body_type = QComboBox()
        self.body_type.addItems(["none", "JSON", "form-data", "x-www-form-urlencoded"])
        self.body_type.setFixedWidth(210)
        self.body_type.currentIndexChanged.connect(self._on_body_type_changed)
        bt.addWidget(self.body_type)
        self.fmt_btn = QPushButton("格式化 JSON")
        self.fmt_btn.clicked.connect(self.format_json_body)
        bt.addWidget(self.fmt_btn)
        self.body_hint = QLabel("")
        self.body_hint.setStyleSheet("color:#9aa0a6;")
        bt.addWidget(self.body_hint)
        bt.addStretch(1)
        bv.addLayout(bt)

        self.body_stack = QStackedWidget()
        bv.addWidget(self.body_stack, 1)

        none_page = QLabel("该请求不携带 Body。")
        none_page.setAlignment(Qt.AlignCenter)
        none_page.setStyleSheet("color:#6b7075;")
        self.body_stack.addWidget(none_page)

        self.body_json = QPlainTextEdit()
        self.body_json.setPlaceholderText('{\n    "key": "value"\n}')
        self.body_json.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.json_hl = JsonHighlighter(self.body_json.document())
        self.body_stack.addWidget(self.body_json)

        self.body_form = KeyValueTable(key_label="字段名")
        self.body_stack.addWidget(self.body_form)

        self.body_urlenc = KeyValueTable(key_label="字段名")
        self.body_stack.addWidget(self.body_urlenc)
        req_tabs.addTab(body_wrap, "Body")

        # 响应区
        resp_wrap = QWidget()
        rv = QVBoxLayout(resp_wrap)
        rv.setContentsMargins(6, 6, 6, 6)
        rv.setSpacing(6)

        rbar = QHBoxLayout()
        self.status_label = QLabel("尚未发送请求")
        self.status_label.setObjectName("statusChip")
        self.status_label.setStyleSheet(
            "background:#2b2d31; color:#c8ccd1; padding:4px 12px; border-radius:10px; font-weight:600;"
        )
        rbar.addWidget(self.status_label)
        self.time_label = QLabel("耗时：-")
        self.size_label = QLabel("大小：-")
        rbar.addWidget(self.time_label)
        rbar.addWidget(self.size_label)
        rbar.addStretch(1)
        self.pretty_chk = QCheckBox("美化 JSON")
        self.pretty_chk.setChecked(True)
        self.pretty_chk.stateChanged.connect(self._render_response_body)
        rbar.addWidget(self.pretty_chk)
        self.copy_btn = QPushButton("复制响应")
        self.copy_btn.clicked.connect(self.copy_response)
        rbar.addWidget(self.copy_btn)
        self.save_resp_btn = QPushButton("保存响应")
        self.save_resp_btn.clicked.connect(self.save_response)
        rbar.addWidget(self.save_resp_btn)
        rv.addLayout(rbar)

        self.resp_tabs = QTabWidget()
        self.resp_body = QPlainTextEdit()
        self.resp_body.setReadOnly(True)
        self.resp_body.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.resp_hl = JsonHighlighter(self.resp_body.document())
        self.resp_tabs.addTab(self.resp_body, "响应体")
        self.resp_headers = QTableWidget(0, 2)
        self.resp_headers.setHorizontalHeaderLabels(["响应头", "值"])
        self.resp_headers.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.resp_headers.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.resp_headers.setColumnWidth(0, 260)
        self.resp_headers.verticalHeader().setVisible(False)
        self.resp_headers.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.resp_tabs.addTab(self.resp_headers, "响应头")
        rv.addWidget(self.resp_tabs, 1)
        right_split.addWidget(resp_wrap)
        right_split.setSizes([420, 420])

        self.statusBar().showMessage("就绪")
        self._shortcuts = []
        for seq, slot in (
            ("Ctrl+Return", self.send_request),
            ("Ctrl+Enter", self.send_request),
            ("Ctrl+S", self.save_to_collection),
        ):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(slot)
            self._shortcuts.append(sc)

    # ------------------------------------------------------------------
    # 基础辅助
    # ------------------------------------------------------------------
    def status_msg(self, text: str, ms: int = 4000) -> None:
        self.statusBar().showMessage(text, ms)

    def _settings(self) -> dict:
        return self.state.setdefault("settings", {})

    def _load_settings(self) -> None:
        s = self._settings()
        self.timeout_spin.setValue(int(s.get("timeout", 30)))
        self.verify_chk.setChecked(not bool(s.get("verify", True)))
        self.redirect_chk.setChecked(bool(s.get("follow_redirects", True)))

    def _save_settings(self) -> None:
        s = self._settings()
        s["timeout"] = self.timeout_spin.value()
        s["verify"] = not self.verify_chk.isChecked()
        s["follow_redirects"] = self.redirect_chk.isChecked()

    def _current_env(self) -> dict:
        name = self.state.get("active_env")
        for e in self.state.get("environments", []):
            if e.get("name") == name:
                return e
        envs = self.state.get("environments", [])
        return envs[0] if envs else {"name": "默认环境", "variables": []}

    def variables(self) -> dict:
        env = self._current_env()
        out = {}
        for v in env.get("variables", []):
            if v.get("enabled", True) and v.get("key"):
                out[v["key"]] = v.get("value", "")
        return out

    def _refresh_env_combo(self) -> None:
        self.env_combo.blockSignals(True)
        self.env_combo.clear()
        names = [e.get("name", "") for e in self.state.get("environments", [])]
        self.env_combo.addItems(names)
        active = self.state.get("active_env")
        if active in names:
            self.env_combo.setCurrentIndex(names.index(active))
        self.env_combo.blockSignals(False)
        self._update_var_hint()

    def _on_env_changed(self, idx: int) -> None:
        names = [e.get("name", "") for e in self.state.get("environments", [])]
        if 0 <= idx < len(names):
            self.state["active_env"] = names[idx]
            save_state(self.state)
            self._update_var_hint()

    def _update_var_hint(self) -> None:
        env = self._current_env()
        n = len([v for v in env.get("variables", []) if v.get("enabled", True) and v.get("key")])
        self.var_hint.setText(f"当前环境「{env.get('name', '')}」已加载 {n} 个变量")

    # ------------------------------------------------------------------
    # 环境管理
    # ------------------------------------------------------------------
    def manage_envs(self) -> None:
        dlg = EnvDialog(self.state.get("environments", []), self)
        if dlg.exec() == QDialog.Accepted:
            self.state["environments"] = dlg.result_data()
            names = [e.get("name") for e in self.state["environments"]]
            if self.state.get("active_env") not in names:
                self.state["active_env"] = names[0]
            save_state(self.state)
            self._refresh_env_combo()
            self.status_msg("环境变量已更新")

    # ------------------------------------------------------------------
    # Body 类型切换
    # ------------------------------------------------------------------
    def _on_body_type_changed(self, idx: int) -> None:
        self.body_stack.setCurrentIndex(idx)
        if idx == 1:
            self.body_hint.setText("可使用 {{变量}}；Content-Type 默认 application/json")
        elif idx == 2:
            self.body_hint.setText("multipart/form-data：按字段名提交文本字段")
        elif idx == 3:
            self.body_hint.setText("application/x-www-form-urlencoded")
        else:
            self.body_hint.setText("")

    def format_json_body(self) -> None:
        text = self.body_json.toPlainText().strip()
        if not text:
            return
        pretty = pretty_json(text)
        if pretty is None:
            QMessageBox.warning(self, "JSON 格式错误", "当前内容不是合法 JSON，无法格式化。")
            return
        self.body_json.setPlainText(pretty)

    def _insert_common_headers(self) -> None:
        menu = QMenu(self)
        items = [
            ("Content-Type: application/json", "Content-Type", "application/json"),
            ("Content-Type: application/x-www-form-urlencoded", "Content-Type", "application/x-www-form-urlencoded"),
            ("Accept: application/json", "Accept", "application/json"),
            ("Authorization: Bearer {{token}}", "Authorization", "Bearer {{token}}"),
            ("User-Agent: HttpLite/1.0", "User-Agent", "HttpLite/1.0"),
        ]
        acts = [(menu.addAction(a), k, v) for a, k, v in items]
        chosen = menu.exec(self.cursor().pos())
        for act, k, v in acts:
            if chosen == act:
                self.headers_table.add_row(k, v)
                break

    def import_url_params(self) -> None:
        url = self.url_edit.text().strip()
        if "?" not in url:
            self.status_msg("URL 中没有查询参数")
            return
        base, _, query = url.partition("?")
        self.url_edit.setText(base)
        count = 0
        for k, v in parse_qsl(query, keep_blank_values=True):
            self.params_table.add_row(k, v)
            count += 1
        self.status_msg(f"已从 URL 导入 {count} 个查询参数")

    # ------------------------------------------------------------------
    # 发送请求
    # ------------------------------------------------------------------
    def _collect_request(self) -> dict:
        variables = self.variables()
        method = self.method_combo.currentText()
        raw_url = self.url_edit.text().strip()
        url = substitute(raw_url, variables).strip()

        headers = {}
        for k, v in self.headers_table.pairs():
            headers[substitute(k, variables)] = substitute(v, variables)

        params = []
        for k, v in self.params_table.pairs():
            params.append((substitute(k, variables), substitute(v, variables)))

        btype = self.body_type.currentText()
        payload = {
            "method": method,
            "url": url,
            "headers": headers,
            "params": params or None,
            "timeout": self.timeout_spin.value(),
            "verify": not self.verify_chk.isChecked(),
            "allow_redirects": self.redirect_chk.isChecked(),
            "data": None,
            "files": None,
            "json": None,
        }

        if btype == "JSON":
            body_text = substitute(self.body_json.toPlainText(), variables)
            if body_text.strip():
                try:
                    payload["json"] = json.loads(body_text)
                except Exception:
                    payload["data"] = body_text.encode("utf-8")
                    if not any(k.lower() == "content-type" for k in headers):
                        headers["Content-Type"] = "application/json"
        elif btype == "form-data":
            files = {}
            for k, v in self.body_form.pairs():
                files[substitute(k, variables)] = (None, substitute(v, variables))
            if files:
                payload["files"] = files
                for k in list(headers):
                    if k.lower() == "content-type":
                        headers.pop(k)
        elif btype == "x-www-form-urlencoded":
            data = {}
            for k, v in self.body_urlenc.pairs():
                data[substitute(k, variables)] = substitute(v, variables)
            if data:
                payload["data"] = data
                if not any(k.lower() == "content-type" for k in headers):
                    headers["Content-Type"] = "application/x-www-form-urlencoded"

        payload["_raw_url"] = raw_url
        return payload

    def send_request(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.status_msg("已有请求正在进行中…")
            return
        payload = self._collect_request()
        if not payload["url"]:
            QMessageBox.information(self, "提示", "请先输入请求地址。")
            return
        if "{{" in payload["url"]:
            self.status_msg("警告：URL 中仍存在未解析的变量")

        self.send_btn.setEnabled(False)
        self.send_btn.setText("请求中")
        self.status_label.setText("请求中…")
        self.status_label.setStyleSheet(
            "background:#2b2d31; color:#f0a45d; padding:4px 12px; border-radius:10px; font-weight:600;"
        )
        self._save_settings()
        save_state(self.state)

        self.worker = HttpWorker(payload, self)
        self.worker.done.connect(self._on_response)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_finished(self) -> None:
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")

    def _on_failed(self, message: str) -> None:
        self.last_response = None
        self.status_label.setText("请求失败")
        self.status_label.setStyleSheet(
            "background:#4a2222; color:#f05f5f; padding:4px 12px; border-radius:10px; font-weight:600;"
        )
        self.time_label.setText("耗时：-")
        self.size_label.setText("大小：-")
        self.resp_body.setPlainText(message)
        self.resp_headers.setRowCount(0)
        self._add_history(self._collect_request(), error=message)
        self.status_msg("请求失败：" + message.splitlines()[0])

    def _on_response(self, data: dict) -> None:
        self.last_response = data
        code = data["status_code"]
        color = STATUS_COLORS.get(str(code)[0], "#8d949c")
        self.status_label.setText(f"{code} {data.get('reason', '')}".strip())
        self.status_label.setStyleSheet(
            f"background:{color}22; color:{color}; padding:4px 12px; border-radius:10px; font-weight:700;"
        )
        self.time_label.setText(f"耗时：{fmt_ms(data['elapsed_ms'])}")
        self.size_label.setText(f"大小：{fmt_size(data['size'])}")
        self._render_response_body()

        self.resp_headers.setRowCount(0)
        for i, (k, v) in enumerate(data.get("headers", [])):
            self.resp_headers.insertRow(i)
            self.resp_headers.setItem(i, 0, QTableWidgetItem(str(k)))
            self.resp_headers.setItem(i, 1, QTableWidgetItem(str(v)))

        self._add_history(self._collect_request(), status=code)
        self.status_msg(
            f"请求完成：{code} · {fmt_ms(data['elapsed_ms'])} · {fmt_size(data['size'])}"
        )

    def _render_response_body(self) -> None:
        if not self.last_response:
            return
        text = self.last_response.get("text", "")
        pretty = pretty_json(text)
        if self.pretty_chk.isChecked() and pretty is not None:
            self.resp_body.setPlainText(pretty)
        else:
            self.resp_body.setPlainText(text)
        self.resp_body.moveCursor(QTextCursor.Start)

    def copy_response(self) -> None:
        if not self.last_response:
            self.status_msg("暂无响应内容可复制")
            return
        QApplication.clipboard().setText(self.last_response.get("text", ""))
        self.status_msg("响应内容已复制到剪贴板")

    def save_response(self) -> None:
        if not self.last_response:
            self.status_msg("暂无响应内容可保存")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存响应内容", os.path.join(app_dir(), "response.txt"), "文本文件 (*.txt);;JSON (*.json);;所有文件 (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.last_response.get("text", ""))
            self.status_msg("响应已保存到 " + path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "保存失败", str(e))

    # ------------------------------------------------------------------
    # 历史记录
    # ------------------------------------------------------------------
    def _add_history(self, req: dict, status=None, error=None) -> None:
        entry = {
            "method": req.get("method", "GET"),
            "url": req.get("_raw_url") or req.get("url", ""),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "error": error,
            "request": self._request_snapshot(),
        }
        hist = self.state.setdefault("history", [])
        hist.insert(0, entry)
        del hist[300:]
        save_state(self.state)
        self._rebuild_history()

    def _request_snapshot(self) -> dict:
        return {
            "method": self.method_combo.currentText(),
            "url": self.url_edit.text(),
            "params": self.params_table.pairs(with_enabled=True),
            "headers": self.headers_table.pairs(with_enabled=True),
            "body_type": self.body_type.currentText(),
            "body_json": self.body_json.toPlainText(),
            "body_form": self.body_form.pairs(with_enabled=True),
            "body_urlenc": self.body_urlenc.pairs(with_enabled=True),
        }

    def _rebuild_history(self) -> None:
        self.history_list.clear()
        for idx, h in enumerate(self.state.get("history", [])):
            status = h.get("status")
            tag = f"{status}" if status else ("ERR" if h.get("error") else "-")
            item = QListWidgetItem(f"[{h.get('method')}] {tag}  {h.get('url', '')}")
            item.setToolTip(
                f"时间：{h.get('time')}\n方法：{h.get('method')}\n地址：{h.get('url')}\n状态：{tag}"
            )
            item.setData(Qt.UserRole, idx)
            self.history_list.addItem(item)

    def _load_history_item(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        hist = self.state.get("history", [])
        if not (0 <= idx < len(hist)):
            return
        self._apply_request(hist[idx].get("request", {}))
        self.status_msg("已载入历史请求")

    def _history_menu(self, pos) -> None:
        item = self.history_list.itemAt(pos)
        menu = QMenu(self)
        act_open = menu.addAction("载入到编辑器") if item else None
        act_resend = menu.addAction("载入并重新发送") if item else None
        if item:
            menu.addSeparator()
        act_del = menu.addAction("删除该条记录") if item else None
        act_clear = menu.addAction("清空历史")
        chosen = menu.exec(self.history_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if act_open and chosen == act_open:
            self._load_history_item(item)
        elif act_resend and chosen == act_resend:
            self._load_history_item(item)
            self.send_request()
        elif act_del and chosen == act_del:
            idx = item.data(Qt.UserRole)
            hist = self.state.get("history", [])
            if 0 <= idx < len(hist):
                hist.pop(idx)
                save_state(self.state)
                self._rebuild_history()
        elif chosen == act_clear:
            self.clear_history()

    def clear_history(self) -> None:
        if not self.state.get("history"):
            return
        if QMessageBox.question(self, "确认", "确定清空全部历史记录？") != QMessageBox.Yes:
            return
        self.state["history"] = []
        save_state(self.state)
        self._rebuild_history()
        self.status_msg("历史记录已清空")

    # ------------------------------------------------------------------
    # 集合
    # ------------------------------------------------------------------
    def _rebuild_collections(self) -> None:
        self.coll_tree.clear()

        def walk(nodes, parent):
            for node in nodes:
                item = QTreeWidgetItem([node.get("name", "")])
                item.setData(0, Qt.UserRole, node.get("id"))
                if node.get("type") == "folder":
                    item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                else:
                    item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                    r = node.get("request", {})
                    item.setToolTip(0, f"{r.get('method', 'GET')} {r.get('url', '')}")
                if parent is None:
                    self.coll_tree.addTopLevelItem(item)
                else:
                    parent.addChild(item)
                if node.get("type") == "folder":
                    walk(node.get("children", []), item)

        walk(self.state.get("collections", []), None)
        self.coll_tree.expandAll()

    def _find_node(self, node_id, nodes=None, parent=None):
        if nodes is None:
            nodes = self.state.get("collections", [])
        for n in nodes:
            if n.get("id") == node_id:
                return n, nodes, parent
            if n.get("type") == "folder":
                found = self._find_node(node_id, n.get("children", []), n)
                if found:
                    return found
        return None

    def _selected_node(self):
        items = self.coll_tree.selectedItems()
        if not items:
            return None
        node = self._find_node(items[0].data(0, Qt.UserRole))
        return node

    def new_collection_folder(self) -> None:
        name, ok = self._ask_text("新建文件夹", "文件夹名称：", "新建文件夹")
        if not ok or not name.strip():
            return
        target, nodes, parent = None, None, None
        sel = self._selected_node()
        if sel:
            target, nodes, parent = sel
        new_node = {"id": self._new_id(), "type": "folder", "name": name.strip(), "children": []}
        if target and target.get("type") == "folder":
            target.setdefault("children", []).append(new_node)
        elif target is not None:
            nodes.append(new_node)
        else:
            self.state["collections"].append(new_node)
        save_state(self.state)
        self._rebuild_collections()

    def save_to_collection(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.information(self, "提示", "请先输入请求地址。")
            return
        default_name = f"{self.method_combo.currentText()} {url.split('?')[0].rstrip('/').split('/')[-1] or 'request'}"
        name, ok = self._ask_text("保存到集合", "请求名称：", default_name)
        if not ok or not name.strip():
            return
        sel = self._selected_node()
        node = {
            "id": self._new_id(),
            "type": "request",
            "name": name.strip(),
            "request": self._request_snapshot(),
        }
        if sel:
            target, nodes, parent = sel
            if target.get("type") == "folder":
                target.setdefault("children", []).append(node)
            else:
                nodes.append(node)
        else:
            colls = self.state.setdefault("collections", [])
            folder = None
            for c in colls:
                if c.get("type") == "folder":
                    folder = c
                    break
            if folder is None:
                folder = {"id": self._new_id(), "type": "folder", "name": "我的集合", "children": []}
                colls.append(folder)
            folder["children"].append(node)
        save_state(self.state)
        self._rebuild_collections()
        self.status_msg(f"已保存到集合：{name.strip()}")

    def _load_collection_item(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        node = self._find_node(item.data(0, Qt.UserRole))
        if not node:
            return
        if node.get("type") == "folder":
            item.setExpanded(not item.isExpanded())
            return
        self._apply_request(node.get("request", {}))
        self.status_msg("已载入集合请求：" + node.get("name", ""))

    def _collection_menu(self, pos) -> None:
        item = self.coll_tree.itemAt(pos)
        found = self._find_node(item.data(0, Qt.UserRole)) if item else None
        sel_node = found[0] if found else None
        parent_list = found[1] if found else None

        menu = QMenu(self)
        act_load = menu.addAction("载入到编辑器") if (sel_node and sel_node.get("type") == "request") else None
        act_save = menu.addAction("保存当前请求到此处")
        act_folder = menu.addAction("新建子文件夹")
        act_ren = menu.addAction("重命名") if sel_node else None
        act_del = menu.addAction("删除") if sel_node else None
        chosen = menu.exec(self.coll_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if act_load is not None and chosen == act_load:
            self._apply_request(sel_node.get("request", {}))
        elif chosen == act_save:
            self.save_to_collection()
        elif chosen == act_folder:
            self.new_collection_folder()
        elif act_ren is not None and chosen == act_ren:
            name, ok = self._ask_text("重命名", "新名称：", sel_node.get("name", ""))
            if ok and name.strip():
                sel_node["name"] = name.strip()
                save_state(self.state)
                self._rebuild_collections()
        elif act_del is not None and chosen == act_del:
            if QMessageBox.question(self, "确认", f"确定删除「{sel_node.get('name')}」？") != QMessageBox.Yes:
                return
            if parent_list is not None and sel_node in parent_list:
                parent_list.remove(sel_node)
                save_state(self.state)
                self._rebuild_collections()
                self.status_msg("已删除集合条目")

    def _ask_text(self, title, label, text):
        return QInputDialog.getText(self, title, label, text=text)

    def _new_id(self) -> str:
        return f"n{int(time.time() * 1000)}{os.urandom(2).hex()}"

    # ------------------------------------------------------------------
    # 载入请求到编辑器
    # ------------------------------------------------------------------
    def _apply_request(self, req: dict) -> None:
        if not req:
            return
        method = req.get("method", "GET")
        if method in METHODS:
            self.method_combo.setCurrentText(method)
        self.url_edit.setText(req.get("url", ""))
        self.params_table.set_pairs(req.get("params", []))
        self.headers_table.set_pairs(req.get("headers", []))
        btype = req.get("body_type", "none")
        idx = {"none": 0, "JSON": 1, "form-data": 2, "x-www-form-urlencoded": 3}.get(btype, 0)
        self.body_type.setCurrentIndex(idx)
        self.body_stack.setCurrentIndex(idx)
        self.body_json.setPlainText(req.get("body_json", ""))
        self.body_form.set_pairs(req.get("body_form", []))
        self.body_urlenc.set_pairs(req.get("body_urlenc", []))

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        self._save_settings()
        save_state(self.state)
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(2000)
        super().closeEvent(event)


# --------------------------------------------------------------------------
QSS = """
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
"""


def run_self_test() -> None:
    """`HttpLite.exe --self-test`：在打包环境中验证 HTTP/SSL/JSON 能力并写出结果文件。"""
    lines = []
    ok = False
    try:
        t0 = time.perf_counter()
        r = requests.get("https://www.baidu.com", timeout=20)
        lines.append(
            f"GET https://www.baidu.com -> {r.status_code}, {len(r.content)} bytes, "
            f"{(time.perf_counter() - t0) * 1000:.0f} ms"
        )
        ok = r.status_code == 200
    except Exception as e:  # noqa: BLE001
        lines.append("http error: " + repr(e))
    try:
        lines.append("json pretty ok: " + str(pretty_json('{"a":1}') is not None))
    except Exception as e:  # noqa: BLE001
        lines.append("json error: " + repr(e))
    lines.append("frozen: " + str(getattr(sys, "frozen", False)))
    lines.append("data_dir: " + DATA_DIR)
    lines.append("requests: " + getattr(requests, "__version__", "?"))
    out = os.path.join(app_dir(), "HttpLite_selftest.txt")
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass
    sys.exit(0 if ok else 2)


def main() -> None:
    if "--self-test" in sys.argv:
        run_self_test()
        return
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setStyleSheet(QSS)
    app.setWindowIcon(make_app_icon())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
