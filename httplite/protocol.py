# -*- coding: utf-8 -*-
"""WebSocket（RFC 6455）与 SSE 协议层。"""
from __future__ import annotations
import base64
import hashlib
import os
import socket
import ssl
import struct
import threading
import time
from urllib.parse import urlsplit
from httplite.constants import WS_GUID
def ws_accept_key(key: str) -> str:
    """RFC 6455 Sec-WebSocket-Accept 计算：base64(sha1(key + GUID))。"""
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode("ascii")).digest()).decode("ascii")
def ws_build_frame(opcode: int, payload: bytes, mask: bool = True, mask_key: bytes = b"") -> bytes:
    """构造 WebSocket 数据帧（客户端→服务端按规范必须掩码）。"""
    if mask and not mask_key:
        mask_key = os.urandom(4)
    length = len(payload)
    b0 = 0x80 | opcode
    if length < 126:
        b1 = length
    elif length < 65536:
        b1 = 126
    else:
        b1 = 127
    if mask:
        b1 |= 0x80
    out = bytearray([b0, b1])
    if 126 <= length < 65536:
        out += struct.pack("!H", length)
    elif length >= 65536:
        out += struct.pack("!Q", length)
    if mask:
        out += mask_key
        masked = bytearray(payload)
        for i in range(length):
            masked[i] ^= mask_key[i % 4]
        payload = bytes(masked)
    out += payload
    return bytes(out)
class WsFrameParser:
    """流式帧解析器：feed 数据返回完整帧列表 [(fin, opcode, payload_bytes), ...]。"""

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, data: bytes) -> list:
        self._buf += data
        out = []
        while True:
            frame = self._try_frame()
            if frame is None:
                break
            out.append(frame)
        return out

    def _try_frame(self):
        if len(self._buf) < 2:
            return None
        b0, b1 = self._buf[0], self._buf[1]
        fin = bool(b0 & 0x80)
        opcode = b0 & 0x0F
        masked = bool(b1 & 0x80)
        length = b1 & 0x7F
        pos = 2
        if length == 126:
            if len(self._buf) < 4:
                return None
            length = struct.unpack("!H", self._buf[2:4])[0]
            pos = 4
        elif length == 127:
            if len(self._buf) < 10:
                return None
            length = struct.unpack("!Q", self._buf[2:10])[0]
            pos = 10
        mask = b""
        if masked:
            if len(self._buf) < pos + 4:
                return None
            mask = self._buf[pos : pos + 4]
            pos += 4
        if len(self._buf) < pos + length:
            return None
        payload = bytearray(self._buf[pos : pos + length])
        if masked:
            for i in range(length):
                payload[i] ^= mask[i % 4]
        self._buf = self._buf[pos + length :]
        return (fin, opcode, bytes(payload))
class WsClient:
    """同步 WebSocket 客户端：connect() 完成握手，send_text / recv_frame 收发帧。"""

    def __init__(self, url: str, timeout: float = 10.0, extra_headers: list = None) -> None:
        u = urlsplit(url)
        if u.scheme not in ("ws", "wss"):
            raise ValueError("仅支持 ws:// 或 wss:// 地址")
        self.url = url
        self.timeout = timeout
        self.extra_headers = extra_headers or []
        self.secure = u.scheme == "wss"
        self.host = u.hostname or ""
        self.port = u.port or (443 if self.secure else 80)
        self.path = (u.path or "/") + (("?" + u.query) if u.query else "")
        self.sock = None
        self._send_lock = threading.Lock()

    def connect(self) -> None:
        raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        if self.secure:
            ctx = ssl.create_default_context()
            raw = ctx.wrap_socket(raw, server_hostname=self.host)
        self.sock = raw
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        lines = [
            "GET %s HTTP/1.1" % self.path,
            "Host: %s:%d" % (self.host, self.port),
            "Upgrade: websocket",
            "Connection: Upgrade",
            "Sec-WebSocket-Key: " + key,
            "Sec-WebSocket-Version: 13",
        ]
        for h in self.extra_headers:
            lines.append(h)
        raw.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("utf-8"))
        resp = self._read_http_response()
        status = -1
        if resp.startswith("HTTP/"):
            parts = resp.split(" ", 2)
            try:
                status = int(parts[1])
            except Exception:
                status = -1
        if status != 101:
            raise ConnectionError("WebSocket 握手失败：HTTP %s（%s）" % (status if status > 0 else "未知", resp[:160]))
        expect = ws_accept_key(key)
        got = self._parse_headers(resp).get("sec-websocket-accept", "")
        if got != expect:
            raise ConnectionError("WebSocket 握手校验失败：Sec-WebSocket-Accept 不匹配")

    def _read_http_response(self) -> str:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode("latin-1")

    def _parse_headers(self, resp: str) -> dict:
        headers = {}
        for line in resp.split("\r\n")[1:]:
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        return headers

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("连接已断开")
            buf += chunk
        return buf

    def recv_frame(self):
        head = self._recv_exact(2)
        b0, b1 = head[0], head[1]
        opcode = b0 & 0x0F
        length = b1 & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if (b1 & 0x80) else b""
        payload = bytearray(self._recv_exact(length))
        if mask:
            for i in range(length):
                payload[i] ^= mask[i % 4]
        return opcode, bytes(payload)

    def send_frame(self, opcode: int, payload: bytes) -> None:
        with self._send_lock:
            self.sock.sendall(ws_build_frame(opcode, payload, mask=True))

    def send_text(self, text: str) -> None:
        self.send_frame(0x1, text.encode("utf-8"))

    def abort(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.send_frame(0x8, b"")
        except Exception:
            pass
        self.abort()
def parse_sse_lines(lines) -> list:
    """按 SSE 规范把行序列解析为事件列表：[{'event': name, 'data': str}, ...]。"""
    events = []
    event_name = "message"
    data_lines = []
    for raw in lines:
        if raw == "":
            if data_lines:
                events.append({"event": event_name, "data": "\n".join(data_lines)})
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
        events.append({"event": event_name, "data": "\n".join(data_lines)})
    return events
