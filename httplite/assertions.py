# -*- coding: utf-8 -*-
"""响应断言与变量提取。"""
from __future__ import annotations
import json
import re
from httplite.constants import ASSERT_TYPES, EXTRACT_TYPES
def eval_simple_path(obj, path: str):
    """极简 JSON 路径求值：支持 $.a.b[0].c / a.b.c / $[0].name。

    返回 (ok, value)；未命中时 ok=False。
    """
    path = (path or "").strip()
    if not path:
        return False, None
    if path.startswith("$"):
        path = path[1:]
    cur = obj
    i = 0
    n = len(path)
    while i < n:
        ch = path[i]
        if ch == ".":
            i += 1
            continue
        if ch == "[":
            j = path.find("]", i)
            if j < 0:
                return False, None
            inner = path[i + 1 : j].strip().strip("\"'").strip()
            i = j + 1
            if inner.isdigit():
                if isinstance(cur, list) and int(inner) < len(cur):
                    cur = cur[int(inner)]
                else:
                    return False, None
            elif isinstance(cur, dict) and inner in cur:
                cur = cur[inner]
            else:
                return False, None
        else:
            j = i
            while j < n and path[j] not in ".[":
                j += 1
            key = path[i:j]
            i = j
            if key == "":
                continue
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                return False, None
    return True, cur
def parse_status_range(spec: str):
    """解析 2xx / 200-299 / 200 三种写法，返回 (lo, hi) 或 None。"""
    spec = (spec or "").strip().lower()
    m = re.fullmatch(r"([2345])xx", spec)
    if m:
        lo = int(m.group(1)) * 100
        return lo, lo + 99
    m = re.fullmatch(r"(\d+)-(\d+)", spec)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r"(\d+)", spec)
    if m:
        v = int(m.group(1))
        return v, v
    return None
def evaluate_assertion(atype, arg1, arg2, ctx) -> tuple:
    """执行单条断言，返回 (ok, desc)。

    ctx 形如 {"status": int, "elapsed_ms": int, "text": str, "json": obj}。
    """
    ok = False
    desc = ""
    try:
        if atype == "status_eq":
            want = str(arg1 or "").strip()
            got = str(ctx.get("status", ""))
            ok = got == want
            desc = f"状态码 == {want}（实际 {got}）"
        elif atype == "status_range":
            rng = parse_status_range(str(arg1 or ""))
            st = ctx.get("status")
            if rng is None:
                desc = f"无法解析范围：{arg1}"
            else:
                ok = rng[0] <= st <= rng[1]
                desc = f"状态码 {rng[0]}-{rng[1]}（实际 {st}）"
        elif atype == "time_lt":
            try:
                limit = float(arg1 or 0)
            except Exception:
                limit = 0
            got = ctx.get("elapsed_ms", 0) or 0
            ok = got < limit
            desc = f"耗时 < {limit:.0f} ms（实际 {got:.0f} ms）"
        elif atype == "body_contains":
            text = ctx.get("text", "") or ""
            ok = str(arg1 or "") in text
            desc = f"响应体包含「{arg1}」"
        elif atype == "json_exists":
            found, _ = eval_simple_path(ctx.get("json"), str(arg1 or ""))
            ok = found
            desc = f"JSON 字段 {arg1} 存在"
        elif atype == "json_eq":
            found, val = eval_simple_path(ctx.get("json"), str(arg1 or ""))
            ok = found and str(val) == str(arg2 or "")
            desc = f"JSON 字段 {arg1} == {arg2}（实际 {val if found else '不存在'}）"
        else:
            desc = f"未知断言类型：{atype}"
    except Exception as e:  # noqa: BLE001
        desc = f"断言执行异常：{e}"
    return ok, desc
def run_extract(etype, expr, text, json_obj) -> tuple:
    """执行一条变量提取，返回 (ok, value)。

    etype 为 jsonpath 或 regex；jsonpath 取 json_obj 的路径值，
    regex 对 text 做匹配（有捕获组取 group(1)，否则取整个匹配）。
    """
    try:
        if etype == "jsonpath":
            ok, val = eval_simple_path(json_obj, str(expr or ""))
            if ok:
                if isinstance(val, str):
                    return True, val
                return True, json.dumps(val, ensure_ascii=False)
            return False, None
        if etype == "regex":
            m = re.search(str(expr or ""), text or "")
            if not m:
                return False, None
            if m.groups():
                return True, m.group(1)
            return True, m.group(0)
    except Exception:  # noqa: BLE001
        return False, None
    return False, None
