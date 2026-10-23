# -*- coding: utf-8 -*-
"""后台线程：HTTP / WebSocket / SSE / 更新检查 / 集合运行器。"""
from __future__ import annotations
import json
import sys
import time
from PySide6.QtCore import QThread, Signal
import requests
from httplite.assertions import evaluate_assertion
from httplite.auth import apply_auth, default_auth
from httplite.constants import METHODS, VAR_RX
from httplite.protocol import WsClient, parse_sse_lines
from httplite.updater import check_for_update
from httplite.utils import _enabled_pairs, fmt_ms, substitute
class HttpWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self._payload = payload

    def run(self) -> None:  # noqa: D102
        p = self._payload
        try:
            kwargs = {
                "method": p.get("method", "GET"),
                "url": p.get("url", ""),
                "headers": p.get("headers") or {},
                "params": p.get("params") or None,
                "timeout": p.get("timeout", 30),
                "verify": p.get("verify", True),
                "allow_redirects": p.get("allow_redirects", True),
                "auth": p.get("requests_auth"),
            }
            if p.get("files") is not None:
                kwargs["files"] = p["files"]
            if p.get("data") is not None:
                kwargs["data"] = p["data"]
            if p.get("json") is not None:
                kwargs["json"] = p["json"]
            t0 = time.perf_counter()
            resp = requests.request(**kwargs)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            self.done.emit(
                {
                    "status_code": resp.status_code,
                    "reason": resp.reason,
                    "headers": list(resp.headers.items()),
                    "text": resp.text,
                    "elapsed_ms": elapsed_ms,
                    "size": len(resp.content),
                    "final_url": resp.url,
                    "redirects": len(resp.history),
                }
            )
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "SSL" in type(e).__name__ or "ssl" in msg.lower():
                msg += "\n提示：可尝试在选项区关闭「验证 SSL 证书」后重试。"
            self.failed.emit(msg)
class WsWorker(QThread):
    connected = Signal(str)
    message = Signal(str, str)  # text, direction(in/out)
    error = Signal(str)
    closed = Signal(str)
    finished_conn = Signal()

    def __init__(self, url: str, timeout: float = 10.0, parent=None):
        super().__init__(parent)
        self.url = url
        self.timeout = timeout
        self._stop = False
        self._client: "WsClient | None" = None

    def stop(self) -> None:
        self._stop = True
        if self._client is not None:
            self._client.abort()

    def run(self) -> None:  # noqa: D102
        client = None
        try:
            client = WsClient(self.url, self.timeout)
            client.connect()
            self._client = client
            self.connected.emit(self.url)
            while not self._stop:
                opcode, payload = client.recv_frame()
                if opcode == 0x8:
                    self.closed.emit("连接已关闭（收到 close 帧）")
                    break
                elif opcode == 0x9:
                    client.send_frame(0xA, payload)
                elif opcode == 0xA:
                    continue
                elif opcode == 0x1:
                    try:
                        text = payload.decode("utf-8")
                    except UnicodeDecodeError:
                        text = repr(payload)
                    self.message.emit(text, "in")
                elif opcode == 0x2:
                    self.message.emit("[二进制 %d 字节] %s" % (len(payload), repr(payload[:160])), "in")
                else:
                    self.message.emit("[未知帧 opcode=%d len=%d]" % (opcode, len(payload)), "in")
        except Exception as e:  # noqa: BLE001
            if not self._stop:
                self.error.emit(str(e))
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            self._client = None
            self.finished_conn.emit()
class SseWorker(QThread):
    connected = Signal(str)
    event = Signal(str, str)  # event_name, data
    error = Signal(str)
    closed = Signal(str)
    finished_conn = Signal()

    def __init__(self, url: str, timeout: float = 15.0, verify: bool = False, parent=None):
        super().__init__(parent)
        self.url = url
        self.timeout = timeout
        self.verify = verify
        self._stop = False
        self._resp = None

    def stop(self) -> None:
        self._stop = True
        if self._resp is not None:
            try:
                self._resp.close()
            except Exception:
                pass

    def run(self) -> None:  # noqa: D102
        resp = None
        try:
            resp = requests.get(
                self.url,
                stream=True,
                timeout=(max(5.0, self.timeout), self.timeout),
                verify=self.verify,
            )
            self._resp = resp
            if resp.status_code != 200:
                self.error.emit("SSE 连接失败：HTTP %d" % resp.status_code)
                return
            self.connected.emit(self.url)
            event_name = "message"
            data_lines = []
            for raw in resp.iter_lines(decode_unicode=True):
                if self._stop:
                    break
                if raw is None:
                    continue
                if raw == "":
                    if data_lines:
                        self.event.emit(event_name, "\n".join(data_lines))
                    event_name = "message"
                    data_lines = []
                    continue
                if raw.startswith(":"):
                    continue
                if raw.startswith("event:"):
                    event_name = raw[len("event:") :].strip() or "message"
                elif raw.startswith("data:"):
                    data_lines.append(raw[len("data:") :].lstrip())
                # id: / retry: 行当前忽略
            if data_lines:
                self.event.emit(event_name, "\n".join(data_lines))
        except Exception as e:  # noqa: BLE001
            if not self._stop:
                self.error.emit(str(e))
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
            self._resp = None
            self.finished_conn.emit()
class CheckUpdateWorker(QThread):
    done = Signal(dict)

    def __init__(self, timeout: float = 8.0, verify: bool = True, parent=None):
        super().__init__(parent)
        self.timeout = timeout
        self.verify = verify

    def run(self) -> None:  # noqa: D102
        self.done.emit(check_for_update(self.timeout, self.verify))
def build_payload_from_snapshot(req: dict, variables: dict, timeout: int, verify: bool, allow_redirects: bool) -> dict:
    """把集合请求快照转换为可发送的 payload（变量替换 + 认证注入）。"""
    variables = variables or {}
    method = (req.get("method") or "GET").upper()
    raw_url = str(req.get("url") or "")
    url = substitute(raw_url, variables).strip()

    headers = {}
    for k, v in _enabled_pairs(req.get("headers")):
        headers[substitute(str(k), variables)] = substitute(str(v), variables)

    params = []
    for k, v in _enabled_pairs(req.get("params")):
        params.append((substitute(str(k), variables), substitute(str(v), variables)))

    body_kind = req.get("body_type") or "none"
    payload = {
        "method": method,
        "url": url,
        "headers": headers,
        "params": params or None,
        "timeout": timeout,
        "verify": verify,
        "allow_redirects": allow_redirects,
        "data": None,
        "files": None,
        "json": None,
        "requests_auth": None,
    }
    if body_kind == "JSON":
        body_text = substitute(req.get("body_json") or "", variables)
        if body_text.strip():
            try:
                payload["json"] = json.loads(body_text)
            except Exception:
                payload["data"] = body_text.encode("utf-8")
                if not any(k.lower() == "content-type" for k in headers):
                    headers["Content-Type"] = "application/json"
    elif body_kind == "form-data":
        files = {}
        for k, v in _enabled_pairs(req.get("body_form")):
            files[substitute(str(k), variables)] = (None, substitute(str(v), variables))
        if files:
            payload["files"] = files
            for k in list(headers):
                if k.lower() == "content-type":
                    headers.pop(k)
    elif body_kind == "x-www-form-urlencoded":
        data = {}
        for k, v in _enabled_pairs(req.get("body_urlenc")):
            data[substitute(str(k), variables)] = substitute(str(v), variables)
        if data:
            payload["data"] = data
            if not any(k.lower() == "content-type" for k in headers):
                headers["Content-Type"] = "application/x-www-form-urlencoded"

    payload["_auth_notes"] = apply_auth(payload, req.get("auth") or default_auth(), variables)
    payload["_raw_url"] = raw_url
    return payload
def run_assertions_on_ctx(tests, ctx) -> tuple:
    """对 ctx 运行全部断言，返回 (passed, total, details)。details 为 [(ok, desc)]。"""
    passed = 0
    total = 0
    details = []
    for t in tests or []:
        if not isinstance(t, dict):
            continue
        atype = str(t.get("atype") or "")
        if not atype:
            continue
        ok, desc = evaluate_assertion(atype, t.get("arg1"), t.get("arg2"), ctx)
        total += 1
        if ok:
            passed += 1
        details.append((ok, desc))
    return passed, total, details
class CollectionRunner(QThread):
    """后台顺序执行集合请求，逐条上报结果。"""

    item_done = Signal(dict)
    all_done = Signal(dict)

    def __init__(self, requests_list, variables, timeout, verify, allow_redirects, parent=None):
        super().__init__(parent)
        self._requests = requests_list
        self._variables = variables or {}
        self._timeout = timeout
        self._verify = verify
        self._allow_redirects = allow_redirects
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:  # noqa: D102
        total = len(self._requests)
        success = 0
        failed = 0
        for i, req in enumerate(self._requests):
            if self._stop:
                break
            result = {
                "index": i,
                "name": str(req.get("name") or req.get("url") or ""),
                "method": (req.get("method") or "GET").upper(),
                "url": substitute(str(req.get("url") or ""), self._variables).strip(),
                "status_code": None,
                "elapsed_ms": None,
                "passed": 0,
                "total": 0,
                "ok": False,
                "error": "",
            }
            try:
                payload = build_payload_from_snapshot(
                    req, self._variables, self._timeout, self._verify, self._allow_redirects
                )
                t0 = time.perf_counter()
                resp = requests.request(
                    method=payload["method"],
                    url=payload["url"],
                    params=payload["params"],
                    headers=payload["headers"],
                    data=payload["data"],
                    json=payload["json"],
                    files=payload["files"],
                    auth=payload["requests_auth"],
                    timeout=payload["timeout"],
                    verify=payload["verify"],
                    allow_redirects=payload["allow_redirects"],
                )
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                try:
                    json_obj = resp.json()
                except Exception:
                    json_obj = None
                ctx = {"status": resp.status_code, "elapsed_ms": elapsed_ms, "text": resp.text, "json": json_obj}
                passed, total_n, _details = run_assertions_on_ctx(req.get("tests"), ctx)
                ok = resp.status_code < 400 and (total_n == 0 or passed == total_n)
                result.update(
                    {
                        "status_code": resp.status_code,
                        "elapsed_ms": elapsed_ms,
                        "passed": passed,
                        "total": total_n,
                        "ok": ok,
                    }
                )
                if ok:
                    success += 1
                else:
                    failed += 1
            except Exception as e:  # noqa: BLE001
                result["error"] = str(e)
                failed += 1
            self.item_done.emit(result)
        self.all_done.emit({"total": total, "success": success, "failed": failed, "stopped": self._stop})
