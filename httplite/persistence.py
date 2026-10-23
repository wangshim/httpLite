# -*- coding: utf-8 -*-
"""数据目录定位与 workspace.json 持久化。"""
from __future__ import annotations
import json
import os
import sys
from httplite.auth import bearer_auth, default_auth
from httplite.constants import APP_NAME
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
                            "body_urlenc": [],
                            "auth": default_auth(),
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
                            "body_type": "JSON",
                            "body_json": '{\n    "name": "HttpLite",\n    "token": "{{token}}"\n}',
                            "body_form": [],
                            "body_urlenc": [],
                            "auth": bearer_auth("{{token}}"),
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
        "settings": {
            "timeout": 30,
            "verify": True,
            "follow_redirects": True,
            "theme": "dark",
            "check_update_on_start": True,
        },
    }
def load_state() -> dict:
    if os.path.isfile(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
        if isinstance(data, dict):
            base = default_state()
            for k, v in base.items():
                data.setdefault(k, v)
            return data
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
