# -*- coding: utf-8 -*-
"""请求代码生成：cURL / Python / JavaScript。"""
from __future__ import annotations
import json
import re
from urllib.parse import quote
from httplite.constants import METHODS
from httplite.auth import apply_auth, default_auth, set_header
from httplite.utils import substitute, _enabled_pairs, _js_str, _pretty_py_dict, _quote_py, _quote_shell
def generate_code_snippets(req: dict, variables: dict = None) -> dict:
    """把请求快照（snapshot 结构）转成 curl / Python(requests) / JavaScript(fetch) 三段代码。

    认证头由 apply_auth 以预览模式注入（OAuth 2.0 仅使用已缓存 token，不触发网络请求）。
    """
    variables = variables or {}
    method = (req.get("method") or "GET").upper()
    raw_url = substitute(str(req.get("url") or ""), variables).strip()
    auth = req.get("auth") or default_auth()

    params = _enabled_pairs(req.get("params"))
    headers = {}
    for k, v in _enabled_pairs(req.get("headers")):
        set_header(headers, str(k), str(v))
    probe = {
        "method": method,
        "url": raw_url,
        "headers": headers,
        "params": list(params),
        "data": None,
        "files": None,
        "json": None,
        "requests_auth": None,
        "_preview": True,
    }
    try:
        apply_auth(probe, auth, variables)
    except Exception as e:  # noqa: BLE001
        headers["X-HttpLite-Auth-Error"] = str(e)
    params = probe["params"] or []

    query_s = "&".join(f"{quote(k, safe='')}={quote(str(v), safe='')}" for k, v in params)
    url = raw_url
    if query_s:
        url = url + ("&" if "?" in url else "?") + query_s

    body_kind = req.get("body_type") or "none"
    body_json = req.get("body_json") or ""
    body_form = _enabled_pairs(req.get("body_form"))
    body_urlenc = _enabled_pairs(req.get("body_urlenc"))

    body_text = ""
    py_body = ""
    body_kw = "data"
    js_body = ""

    if body_kind == "JSON" and body_json.strip():
        try:
            obj = json.loads(body_json)
            body_text = json.dumps(obj, ensure_ascii=False)
            py_body = repr(obj)
            body_kw = "json"
        except Exception:
            body_text = body_json
            py_body = repr(body_json)
            body_kw = "data"
        js_body = "    body: " + _js_str(body_text) + ","
    elif body_kind == "form-data" and body_form:
        parts = []
        for k, v in body_form:
            parts.append(f"-F '{k}={v}'".replace("'", "'\\''"))
        body_text = " \\\n  ".join(parts)
        py_body = repr({k: ("", str(v)) for k, v in body_form})
        body_kw = "files"
        lines = ["    const body = new FormData();"]
        for k, v in body_form:
            lines.append(f'    body.append({_js_str(k)}, {_js_str(v)});')
        js_body = "\n".join(lines)
    elif body_kind == "x-www-form-urlencoded" and body_urlenc:
        parts = []
        for k, v in body_urlenc:
            parts.append("--data-urlencode " + f"'{k}={v}'".replace("'", "'\\''"))
        body_text = " \\\n  ".join(parts)
        py_body = repr(dict(body_urlenc))
        body_kw = "data"
        js_body = "    body: new URLSearchParams(" + _js_str(json.dumps(dict(body_urlenc), ensure_ascii=False)) + "),"

    # curl
    lines = [f"curl -X {method} {_quote_shell(url)}"]
    for k, v in headers.items():
        lines.append(f"  -H {_quote_shell(f'{k}: {v}')}")
    if body_text:
        if body_kind == "form-data":
            lines.append("  " + body_text)
        elif body_kind == "x-www-form-urlencoded":
            lines.append("  " + body_text)
        else:
            lines.append("  --data-raw " + _quote_shell(body_text))
    curl_code = " \\\n".join(lines) + "\n"

    # Python
    py_lines = [
        "import requests",
        "",
        f"url = {_quote_py(url)}",
        "headers = " + _pretty_py_dict(headers) if headers else "headers = {}",
    ]
    if params:
        py_lines.append("params = " + repr(dict(params)))
    if py_body:
        py_lines.append("payload = " + py_body)
    py_lines.append("")
    py_lines.append('resp = requests.request(')
    py_lines.append(f"    {_quote_py(method)}, url,")
    py_lines.append("    headers=headers,")
    if params:
        py_lines.append("    params=params,")
    if py_body:
        py_lines.append(f"    {body_kw}=payload,")
    py_lines.append("    timeout=30,")
    py_lines.append(")")
    py_lines.append("print(resp.status_code)")
    py_lines.append("print(resp.text)")
    py_code = "\n".join(py_lines) + "\n"

    # JavaScript
    js_lines = [
        f"const url = {_js_str(url)};",
        "const options = {",
        f"  method: {_js_str(method)},",
    ]
    if headers:
        js_lines.append("  headers: " + json.dumps(headers, ensure_ascii=False, indent=2).replace("\n", "\n  ") + ",")
    else:
        js_lines.append("  headers: {},")
    if js_body:
        js_lines.append(js_body)
    js_lines.append("};")
    if params:
        js_lines.append("const params = " + json.dumps(dict(params), ensure_ascii=False) + ";")
        js_lines.append("options.url = url + '?' + new URLSearchParams(params).toString();")
        js_lines.append("const resp = await fetch(options.url, options);")
    else:
        js_lines.append("const resp = await fetch(url, options);")
    js_lines.append("const data = await resp.json().catch(() => null);")
    js_lines.append("console.log(resp.status, data);")
    js_code = "\n".join(js_lines) + "\n"

    return {"curl": curl_code, "python": py_code, "javascript": js_code}
