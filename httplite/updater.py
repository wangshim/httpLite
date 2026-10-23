# -*- coding: utf-8 -*-
"""内置更新检查：版本比较与 GitHub Releases 查询。"""
from __future__ import annotations
import json
import re
import time
import requests
from httplite.constants import APP_NAME, CURRENT_VERSION, GITHUB_RELEASES_API, GITHUB_REPO_URL
def version_tuple(v) -> tuple:
    nums = re.findall(r"\d+", str(v))
    tup = tuple(int(x) for x in nums[:4])
    return tup + (0,) * (4 - len(tup))
def version_compare(a, b) -> int:
    """a < b → -1；a == b → 0；a > b → 1。支持 v 前缀与多段数字。"""
    ta, tb = version_tuple(a), version_tuple(b)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0
def check_for_update(timeout: float = 8.0, verify: bool = True) -> dict:
    """请求 GitHub Releases API，返回最新版本与下载地址。网络失败时 ok=False。"""
    try:
        r = requests.get(
            GITHUB_RELEASES_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": APP_NAME + "/" + CURRENT_VERSION,
            },
            timeout=timeout,
            verify=verify,
        )
        if r.status_code != 200:
            return {"ok": False, "error": "GitHub API 返回 HTTP %d" % r.status_code, "current": CURRENT_VERSION}
        data = r.json()
        if not isinstance(data, dict):
            return {"ok": False, "error": "GitHub API 返回格式异常", "current": CURRENT_VERSION}
        latest = str(data.get("tag_name") or data.get("name") or "").lstrip("vV")
        return {
            "ok": True,
            "available": version_compare(latest, CURRENT_VERSION) > 0,
            "latest": latest,
            "current": CURRENT_VERSION,
            "url": data.get("html_url") or GITHUB_REPO_URL,
            "name": data.get("name") or "",
            "body": (data.get("body") or "").strip()[:500],
            "published_at": data.get("published_at") or "",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "current": CURRENT_VERSION}
