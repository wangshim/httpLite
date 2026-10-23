# -*- coding: utf-8 -*-
"""通用工具函数。"""
from __future__ import annotations
import base64
import json
import re
from httplite.constants import VAR_RX
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
def mask_secret(text: str, keep: int = 6) -> str:
    if not text:
        return "(空)"
    if len(text) <= keep + 4:
        return "*" * 8
    return text[:keep] + "…" + "*" * 4
def set_header(headers: dict, key: str, value: str) -> None:
    """大小写不敏感地写入/覆盖一个请求头。"""
    for k in list(headers):
        if k.lower() == key.lower():
            del headers[k]
    headers[key] = value
def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
def _enabled_pairs(rows) -> list:
    """把 KeyValueTable 行 / 快照中的 params 转成 (key, value) 列表，过滤未启用与空 key。"""
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        if r.get("enabled") is False:
            continue
        k = str(r.get("key", "") or "")
        if k:
            out.append((k, r.get("value", "")))
    return out
def _js_str(text: str) -> str:
    return json.dumps(str(text), ensure_ascii=False)
def _quote_shell(text: str) -> str:
    return "'" + str(text).replace("'", "'\\''") + "'"
def _quote_py(text: str) -> str:
    return repr(str(text))
def _pretty_py_dict(d: dict) -> str:
    """headers 用多行 repr，便于阅读。"""
    if not d:
        return "{}"
    return "{\n    " + ",\n    ".join(repr(k) + ": " + repr(v) for k, v in d.items()) + ",\n}"
