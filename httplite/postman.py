# -*- coding: utf-8 -*-
"""Postman Collection v2.1 导入 / 导出。"""
from __future__ import annotations
import json
import os
import re
import time
from urllib.parse import parse_qsl, quote, urlencode
from httplite.constants import (
    AUTH_TYPE_KEYS,
    AUTH_TYPE_LABELS,
    JWT_ALGORITHMS,
    OAUTH2_GRANTS,
    POSTMAN_SCHEMA,
)
from httplite.auth import auth_label, auth_tag_of, bearer_auth, default_auth, merge_auth
from httplite.utils import pretty_json, substitute
def _postman_url_parts(url) -> tuple:
    """把 Postman url（字符串或对象）拆成 (raw_url, params)。

    params 为 HttpLite 参数列表（query 数组映射而来）。若 raw 已含 query
    且 Postman 同时给了 query 数组，则剥掉 raw 里的 query，避免发送时重复。
    """
    if isinstance(url, str):
        return url, []
    if not isinstance(url, dict):
        return "", []
    raw = url.get("raw", "") or ""
    host = url.get("host", [])
    path = url.get("path", [])
    query = url.get("query", []) or []
    params = []
    for q in query:
        if isinstance(q, dict) and not q.get("disabled", False):
            params.append(
                {"key": str(q.get("key", "")), "value": str(q.get("value", "")), "enabled": True}
            )
    if raw:
        if params and "?" in raw:
            return raw.split("?", 1)[0], params
        return raw, params
    host_s = ".".join(str(x) for x in host) if isinstance(host, list) else ""
    path_s = "/".join(str(x) for x in path) if isinstance(path, list) else ""
    result = host_s
    if path_s:
        result = (result + "/" if result else "") + path_s
    if params:
        result += "?" + "&".join(f"{p['key']}={p['value']}" for p in params)
    return result, params
def _postman_auth_to_internal(auth) -> dict:
    """把 Postman 认证对象映射为 HttpLite auth 结构。"""
    if not isinstance(auth, dict):
        return default_auth()

    def pick(items, key):
        if not isinstance(items, list):
            return ""
        for it in items:
            if isinstance(it, dict) and it.get("key") == key:
                return str(it.get("value", ""))
        return ""

    atype = auth.get("type", "noauth")
    if atype == "bearer":
        return bearer_auth(pick(auth.get("bearer", []), "token"))
    if atype == "basic":
        return {
            "type": "basic",
            "basic": {
                "username": pick(auth.get("basic", []), "username"),
                "password": pick(auth.get("basic", []), "password"),
            },
        }
    if atype == "apikey":
        return {
            "type": "apikey",
            "apikey": {
                "key": pick(auth.get("apikey", []), "key"),
                "value": pick(auth.get("apikey", []), "value"),
                "in": pick(auth.get("apikey", []), "in") or "header",
            },
        }
    return default_auth()
def _postman_body_to_internal(body) -> dict:
    """把 Postman body 对象映射为 HttpLite 请求体结构。"""
    out = {"body_type": "none", "body_json": "", "body_form": [], "body_urlenc": []}
    if not isinstance(body, dict):
        return out
    mode = body.get("mode", "")
    if mode == "raw":
        raw = body.get("raw", "") or ""
        stripped = raw.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(stripped)
                out["body_type"] = "JSON"
                out["body_json"] = pretty_json(stripped) or stripped
                return out
            except Exception:
                pass
        out["body_type"] = "raw"
        out["body_json"] = raw
        return out
    if mode == "urlencoded":
        items = []
        for kv in body.get("urlencoded", []) or []:
            if isinstance(kv, dict):
                items.append(
                    {
                        "key": str(kv.get("key", "")),
                        "value": str(kv.get("value", "")),
                        "enabled": not kv.get("disabled", False),
                    }
                )
        out["body_type"] = "x-www-form-urlencoded"
        out["body_urlenc"] = items
        return out
    if mode == "formdata":
        items = []
        for kv in body.get("formdata", []) or []:
            if isinstance(kv, dict):
                items.append(
                    {
                        "key": str(kv.get("key", "")),
                        "value": str(kv.get("value", "")),
                        "enabled": not kv.get("disabled", False),
                    }
                )
        out["body_type"] = "form-data"
        out["body_form"] = items
        return out
    return out
def _postman_request_to_internal(pm_request) -> dict:
    """单个 Postman request 对象 -> HttpLite request dict。"""
    if not isinstance(pm_request, dict):
        pm_request = {}
    method = str(pm_request.get("method", "GET") or "GET")
    raw_url, params = _postman_url_parts(pm_request.get("url", ""))
    headers = []
    for h in pm_request.get("header", []) or []:
        if isinstance(h, dict):
            headers.append(
                {
                    "key": str(h.get("key", "")),
                    "value": str(h.get("value", "")),
                    "enabled": not h.get("disabled", False),
                }
            )
    body = _postman_body_to_internal(pm_request.get("body", {}))
    return {
        "method": method,
        "url": raw_url,
        "params": params,
        "headers": headers,
        "body_type": body["body_type"],
        "body_json": body["body_json"],
        "body_form": body["body_form"],
        "body_urlenc": body["body_urlenc"],
        "auth": _postman_auth_to_internal(pm_request.get("auth", {})),
    }
def parse_postman_collection(text: str):
    """解析 Postman Collection v2.1 JSON 文本，返回 (nodes, errors)。

    nodes: 顶层 HttpLite 节点列表（通常一个 folder，名字取 info.name）；
    解析失败时 nodes 为 None，errors 给出原因。
    """
    try:
        data = json.loads(text)
    except Exception as e:
        return None, ["JSON 解析失败：" + str(e)]
    if not isinstance(data, dict) or "item" not in data:
        return None, ["不是有效的 Postman Collection v2.1 JSON（缺少 item 字段）"]
    name = str((data.get("info") or {}).get("name", "导入的集合") or "导入的集合")
    counter = [0]

    def new_id():
        counter[0] += 1
        return f"n{int(time.time() * 1000)}{os.urandom(2).hex()}{counter[0]}"

    def walk(items):
        nodes = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            if "request" in it:
                nodes.append(
                    {
                        "id": new_id(),
                        "type": "request",
                        "name": str(it.get("name", "未命名请求")),
                        "request": _postman_request_to_internal(it.get("request", {})),
                    }
                )
            else:
                nodes.append(
                    {
                        "id": new_id(),
                        "type": "folder",
                        "name": str(it.get("name", "未命名文件夹")),
                        "children": walk(it.get("item", [])),
                    }
                )
        return nodes

    items = data.get("item", [])
    # 顶层仅有一个与 info.name 同名、且不含 request 的文件夹时，直接取其 children，
    # 避免 HttpLite 导出的集合再导入时产生一层冗余嵌套。
    if (
        len(items) == 1
        and isinstance(items[0], dict)
        and "request" not in items[0]
        and str(items[0].get("name", "")) == name
    ):
        items = items[0].get("item", [])
    return [{"id": new_id(), "type": "folder", "name": name, "children": walk(items)}], []
def _internal_request_to_postman(req) -> dict:
    """HttpLite request dict -> Postman request 对象。"""
    req = req or {}
    method = str(req.get("method", "GET") or "GET")
    url = req.get("url", "") or ""
    params = req.get("params", []) or []
    raw_url = url
    if params:
        sep = "&" if "?" in url else "?"
        raw_url = url + sep + "&".join(
            f"{p.get('key', '')}={p.get('value', '')}"
            for p in params
            if isinstance(p, dict) and p.get("enabled", True)
        )
    headers = []
    for h in req.get("headers", []) or []:
        if isinstance(h, dict):
            headers.append(
                {
                    "key": str(h.get("key", "")),
                    "value": str(h.get("value", "")),
                    "disabled": not h.get("enabled", True),
                }
            )
    btype = req.get("body_type", "none")
    body = {"mode": "raw", "raw": ""}
    if btype == "JSON":
        body = {"mode": "raw", "raw": req.get("body_json", "") or "", "options": {"raw": {"language": "json"}}}
    elif btype == "x-www-form-urlencoded":
        body = {
            "mode": "urlencoded",
            "urlencoded": [
                {"key": str(i.get("key", "")), "value": str(i.get("value", "")), "disabled": not i.get("enabled", True)}
                for i in req.get("body_urlenc", []) or []
            ],
        }
    elif btype == "form-data":
        body = {
            "mode": "formdata",
            "formdata": [
                {
                    "key": str(i.get("key", "")),
                    "value": str(i.get("value", "")),
                    "disabled": not i.get("enabled", True),
                    "type": "text",
                }
                for i in req.get("body_form", []) or []
            ],
        }
    auth = {"type": "noauth"}
    a = req.get("auth") or default_auth()
    atype = a.get("type", "noauth")
    if atype == "bearer":
        auth = {"type": "bearer", "bearer": [{"key": "token", "value": str((a.get("bearer") or {}).get("token", "")), "type": "string"}]}
    elif atype == "basic":
        auth = {"type": "basic", "basic": [
            {"key": "username", "value": str((a.get("basic") or {}).get("username", "")), "type": "string"},
            {"key": "password", "value": str((a.get("basic") or {}).get("password", "")), "type": "string"},
        ]}
    elif atype == "apikey":
        auth = {"type": "apikey", "apikey": [
            {"key": "key", "value": str((a.get("apikey") or {}).get("key", "")), "type": "string"},
            {"key": "value", "value": str((a.get("apikey") or {}).get("value", "")), "type": "string"},
            {"key": "in", "value": str((a.get("apikey") or {}).get("in", "header")), "type": "string"},
        ]}
    url_obj = {"raw": raw_url, "host": [], "path": [], "query": []}
    try:
        from urllib.parse import urlsplit, parse_qsl

        parts = urlsplit(raw_url)
        if parts.scheme and parts.netloc:
            url_obj["host"] = [parts.scheme + "://" + parts.netloc]
            url_obj["path"] = [p for p in parts.path.split("/") if p] or [""]
            url_obj["query"] = [
                {"key": k, "value": v}
                for k, v in parse_qsl(parts.query)
            ]
        elif parts.path:
            url_obj["path"] = [p for p in parts.path.split("/") if p] or [""]
    except Exception:
        pass
    return {"method": method, "url": url_obj, "header": headers, "body": body, "auth": auth}
def build_postman_collection(nodes, name="HttpLite 集合", _postman_id=None):
    """HttpLite 集合节点树 -> Postman Collection v2.1 dict。"""
    import uuid

    def walk(items):
        out = []
        for node in items or []:
            if node.get("type") == "folder":
                out.append({"name": str(node.get("name", "")), "item": walk(node.get("children", []))})
            else:
                out.append(
                    {
                        "name": str(node.get("name", "")),
                        "request": _internal_request_to_postman(node.get("request", {})),
                        "response": [],
                    }
                )
        return out

    return {
        "info": {
            "_postman_id": _postman_id or uuid.uuid4().hex,
            "name": name,
            "schema": POSTMAN_SCHEMA,
            "description": "由 HttpLite 导出的 Postman Collection v2.1",
        },
        "item": walk(nodes),
    }
def _count_requests(node) -> int:
    """统计节点树中的请求数。"""
    if node.get("type") == "request":
        return 1
    return sum(_count_requests(c) for c in node.get("children", []))
