# -*- coding: utf-8 -*-
"""
HttpLite —— 轻量级 HTTP 接口测试工具（类 Postman）
绿色便携：单文件 exe，免安装、不写注册表，数据保存在 exe 同级目录。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

import requests
from requests.auth import HTTPDigestAuth

try:
    import urllib3

    urllib3.disable_warnings()
except Exception:  # pragma: no cover
    pass

from PySide6.QtCore import Qt, QThread, Signal, QRegularExpression, QSize, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
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
    QFormLayout,
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
        "settings": {"timeout": 30, "verify": True, "follow_redirects": True, "theme": "dark"},
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


# --------------------------------------------------------------------------
# 认证（Authorization）内核
# --------------------------------------------------------------------------
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


def default_auth() -> dict:
    return {
        "type": "noauth",
        "bearer": {"token": "{{token}}"},
        "basic": {"username": "", "password": ""},
        "digest": {"username": "", "password": ""},
        "apikey": {"key": "X-API-Key", "value": "", "in": "header"},
        "awsv4": {
            "access_key": "",
            "secret_key": "",
            "session_token": "",
            "region": "us-east-1",
            "service": "execute-api",
        },
        "jwt": {
            "algorithm": "HS256",
            "secret": "",
            "payload": '{\n    "sub": "1234567890",\n    "name": "HttpLite",\n    "iat": 0\n}',
            "location": "header",
            "header_name": "Authorization",
            "prefix": "Bearer ",
        },
        "oauth2": {
            "grant_type": "client_credentials",
            "token_url": "",
            "client_id": "",
            "client_secret": "",
            "username": "",
            "password": "",
            "scope": "",
            "extra": "",
            "authorize_url": "",
            "redirect_uri": "",
            "authorization_code": "",
            "access_token": "",
            "refresh_token": "",
            "token_type": "Bearer",
            "auto_refresh": False,
            "expires_at": 0,
        },
    }


def bearer_auth(token: str) -> dict:
    cfg = default_auth()
    cfg["type"] = "bearer"
    cfg["bearer"]["token"] = token
    return cfg


def merge_auth(data) -> dict:
    """把（可能缺失字段的）认证配置补齐成完整结构。"""
    base = default_auth()
    if isinstance(data, dict):
        if data.get("type") in AUTH_TYPE_KEYS:
            base["type"] = data["type"]
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key].update(value)
    return base


def auth_label(atype: str) -> str:
    if atype in AUTH_TYPE_KEYS:
        return AUTH_TYPE_LABELS[AUTH_TYPE_KEYS.index(atype)]
    return "无认证"


def auth_tag_of(request) -> str:
    """取请求快照里的认证方式标签（无认证返回空串）。"""
    if not isinstance(request, dict):
        return ""
    cfg = request.get("auth")
    atype = cfg.get("type") if isinstance(cfg, dict) else None
    if atype and atype != "noauth":
        return auth_label(atype)
    return ""


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


def make_jwt(algorithm: str, secret: str, payload_text: str):
    """本地生成 JWT（HS256 / HS384 / HS512 / none）。返回 (token, error)。"""
    alg = (algorithm or "HS256").strip()
    text = (payload_text or "").strip()
    try:
        payload = json.loads(text) if text else {}
    except Exception as e:  # noqa: BLE001
        return None, f"Payload 不是合法 JSON（{e}）"
    if not isinstance(payload, dict):
        return None, "Payload 必须是 JSON 对象"
    header = {"alg": alg, "typ": "JWT"}
    signing_input = ".".join(
        [
            b64url(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
            b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
        ]
    )
    if alg == "none":
        return signing_input + ".", None
    digest = {
        "HS256": hashlib.sha256,
        "HS384": hashlib.sha384,
        "HS512": hashlib.sha512,
    }.get(alg)
    if digest is None:
        return None, f"不支持的算法：{alg}"
    if not secret:
        return None, "未填写 JWT 密钥（Secret）"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), digest).digest()
    return signing_input + "." + b64url(signature), None


def request_body_bytes(payload: dict) -> bytes:
    """还原 requests 实际会发送的请求体字节，用于签名计算。"""
    if payload.get("files") is not None:
        return b""
    data = payload.get("data")
    if data is not None:
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, dict):
            return urlencode(data, doseq=True).encode("utf-8")
    if payload.get("json") is not None:
        # 与 requests 内部 json= 的序列化方式保持一致
        return json.dumps(payload["json"], allow_nan=False).encode("utf-8")
    return b""


def _canonical_query(pairs) -> str:
    encoded = []
    for k, v in pairs:
        if k is None:
            continue
        encoded.append(
            (quote(str(k), safe="-_.~"), quote("" if v is None else str(v), safe="-_.~"))
        )
    encoded.sort()
    return "&".join(f"{k}={v}" for k, v in encoded)


def aws_sign_v4(payload: dict, cfg: dict, variables: dict, amz_date: str = None):
    """AWS Signature Version 4 签名。返回 (需要追加的请求头 dict, 错误信息)。"""
    access = substitute(cfg.get("access_key", ""), variables).strip()
    secret = substitute(cfg.get("secret_key", ""), variables).strip()
    session = substitute(cfg.get("session_token", ""), variables).strip()
    region = substitute(cfg.get("region", ""), variables).strip() or "us-east-1"
    service = substitute(cfg.get("service", ""), variables).strip() or "execute-api"
    if not access or not secret:
        return None, "需要填写 Access Key 与 Secret Key"

    parts = urlsplit(payload.get("url") or "")
    host = parts.netloc
    if not host:
        return None, "URL 缺少主机名"
    path = parts.path or "/"

    body = request_body_bytes(payload)
    payload_hash = hashlib.sha256(body).hexdigest()

    amz_date = amz_date or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_date = amz_date[:8]

    pairs = list(parse_qsl(parts.query, keep_blank_values=True))
    pairs += list(payload.get("params") or [])
    canonical_query = _canonical_query(pairs)

    if service == "s3":
        canonical_uri = quote(path, safe="/~")
    else:
        canonical_uri = quote(quote(path, safe="/~"), safe="/~")

    canon = {"host": host}
    for k, v in (payload.get("headers") or {}).items():
        low = str(k).lower()
        if low in (
            "authorization",
            "host",
            "x-amz-date",
            "x-amz-content-sha256",
            "x-amz-security-token",
        ):
            continue
        canon[low] = re.sub(r"\s+", " ", str(v)).strip()
    canon["x-amz-date"] = amz_date
    if service == "s3":
        canon["x-amz-content-sha256"] = payload_hash
    if session:
        canon["x-amz-security-token"] = session

    signed_headers = ";".join(sorted(canon))
    canonical_headers = "".join(f"{k}:{canon[k]}\n" for k in sorted(canon))
    canonical_request = "\n".join(
        [
            (payload.get("method") or "GET").upper(),
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    scope = f"{short_date}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    def _h(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_signing = _h(
        _h(_h(_h(("AWS4" + secret).encode("utf-8"), short_date), region), service), "aws4_request"
    )
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    out = {
        "X-Amz-Date": amz_date,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }
    if service == "s3":
        out["X-Amz-Content-Sha256"] = payload_hash
    if session:
        out["X-Amz-Security-Token"] = session
    return out, None


# --------------------------------------------------------------------------
# OAuth 2.0 认证内核
# --------------------------------------------------------------------------
def _oauth2_token_request(cfg: dict, variables: dict, extra_data: dict) -> tuple:
    """向 token_url 发起表单 POST，返回 (json_obj, error)。"""
    token_url = substitute(cfg.get("token_url", ""), variables).strip()
    if not token_url:
        return None, "请填写 Token URL"
    data = dict(extra_data)
    client_id = substitute(cfg.get("client_id", ""), variables).strip()
    client_secret = substitute(cfg.get("client_secret", ""), variables).strip()
    if client_id:
        data["client_id"] = client_id
    if client_secret:
        data["client_secret"] = client_secret
    scope = substitute(cfg.get("scope", ""), variables).strip()
    if scope:
        data["scope"] = scope
    extra = substitute(cfg.get("extra", ""), variables).strip()
    if extra:
        try:
            parsed = json.loads(extra)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    data[k] = v
        except Exception as e:
            return None, f"额外参数不是合法 JSON：{e}"
    try:
        resp = requests.post(
            token_url,
            data=data,
            timeout=20,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        if resp.status_code >= 400:
            return None, f"Token 端点返回 HTTP {resp.status_code}：{resp.text[:300]}"
        try:
            obj = resp.json()
        except Exception:
            return None, "Token 端点未返回 JSON：" + resp.text[:300]
        if not isinstance(obj, dict):
            return None, "Token 端点返回结构异常：" + resp.text[:300]
        return obj, None
    except Exception as e:
        return None, str(e)


def oauth2_fetch_token(cfg: dict, variables: dict) -> tuple:
    """按 grant_type 获取 access_token。返回 (token_dict, error)。"""
    grant = cfg.get("grant_type") or "client_credentials"
    if grant == "authorization_code":
        code = substitute(cfg.get("authorization_code", ""), variables).strip()
        if not code:
            return None, "缺少授权码（authorization code），请点击「获取授权码」或手动粘贴回调地址"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": substitute(cfg.get("redirect_uri", ""), variables).strip(),
        }
    elif grant == "password":
        username = substitute(cfg.get("username", ""), variables).strip()
        password = substitute(cfg.get("password", ""), variables).strip()
        if not username or not password:
            return None, "Password 模式需要填写用户名与密码"
        data = {"grant_type": "password", "username": username, "password": password}
    else:
        data = {"grant_type": "client_credentials"}
    obj, err = _oauth2_token_request(cfg, variables, data)
    if err:
        return None, err
    token = obj.get("access_token")
    if not token:
        return None, "响应中没有 access_token：" + json.dumps(obj, ensure_ascii=False)[:300]
    return {
        "access_token": token,
        "refresh_token": obj.get("refresh_token"),
        "expires_in": obj.get("expires_in"),
    }, None


def oauth2_refresh_token(cfg: dict, variables: dict) -> tuple:
    """用 refresh_token 刷新。返回 (token_dict, error)。"""
    refresh = substitute(cfg.get("refresh_token", ""), variables).strip()
    if not refresh:
        return None, "缺少 refresh_token，无法刷新"
    obj, err = _oauth2_token_request(
        cfg, variables, {"grant_type": "refresh_token", "refresh_token": refresh}
    )
    if err:
        return None, err
    token = obj.get("access_token")
    if not token:
        return None, "响应中没有 access_token：" + json.dumps(obj, ensure_ascii=False)[:300]
    return {
        "access_token": token,
        "refresh_token": obj.get("refresh_token") or refresh,
        "expires_in": obj.get("expires_in"),
    }, None


def _oauth2_save_token(cfg: dict, token_dict: dict) -> None:
    cfg["access_token"] = token_dict.get("access_token", "")
    if token_dict.get("refresh_token"):
        cfg["refresh_token"] = token_dict["refresh_token"]
    expires_in = token_dict.get("expires_in")
    try:
        cfg["expires_at"] = int(time.time()) + int(expires_in) if expires_in is not None else 0
    except Exception:
        cfg["expires_at"] = 0
    cfg["authorization_code"] = ""


def oauth2_ensure_token(cfg: dict, variables: dict) -> tuple:
    """确保有可用的 access_token（必要时自动获取 / 刷新），并把结果回写 cfg。返回 (token, error)。"""
    cfg = cfg if isinstance(cfg, dict) else {}
    token = substitute(cfg.get("access_token", ""), variables).strip()
    expires_at = cfg.get("expires_at") or 0
    now = time.time()
    if token and (not expires_at or now < int(expires_at) - 30):
        return token, None
    if cfg.get("auto_refresh") and substitute(cfg.get("refresh_token", ""), variables).strip():
        token_dict, err = oauth2_refresh_token(cfg, variables)
        if err is None:
            _oauth2_save_token(cfg, token_dict)
            return token_dict["access_token"], None
    token_dict, err = oauth2_fetch_token(cfg, variables)
    if err:
        return None, err
    _oauth2_save_token(cfg, token_dict)
    return token_dict["access_token"], None


def oauth2_build_authorize_url(cfg: dict, variables: dict) -> str:
    """拼接授权码模式的授权 URL。"""
    base = substitute(cfg.get("authorize_url", ""), variables).strip()
    if not base:
        return ""
    parts = parse_qsl(urlsplit(base).query, keep_blank_values=True)
    parts = [
        p
        for p in parts
        if p[0] not in ("response_type", "client_id", "redirect_uri", "scope", "state")
    ]
    parts.append(("response_type", "code"))
    client_id = substitute(cfg.get("client_id", ""), variables).strip()
    if client_id:
        parts.append(("client_id", client_id))
    redirect_uri = substitute(cfg.get("redirect_uri", ""), variables).strip()
    if redirect_uri:
        parts.append(("redirect_uri", redirect_uri))
    scope = substitute(cfg.get("scope", ""), variables).strip()
    if scope:
        parts.append(("scope", scope))
    parts.append(("state", "hl" + str(int(time.time()))))
    return base.split("?", 1)[0] + "?" + urlencode(parts, doseq=True)


def oauth2_extract_code(callback: str) -> str:
    """从回调地址 / 文本中提取 authorization code。"""
    if not callback:
        return ""
    m = re.search(r"(?:[?&]|^)code=([^&]+)", callback)
    if m:
        return m.group(1)
    return ""


def apply_auth(payload: dict, auth: dict, variables: dict) -> list:
    """把认证配置真正写入请求（headers / params / requests_auth），返回说明列表。"""
    notes = []
    auth = merge_auth(auth)
    atype = auth["type"]
    if atype == "noauth":
        return notes

    headers = payload.get("headers")
    if headers is None:
        headers = {}
        payload["headers"] = headers
    params = list(payload.get("params") or [])

    if atype == "bearer":
        token = substitute(auth["bearer"].get("token", ""), variables).strip()
        if token:
            set_header(headers, "Authorization", "Bearer " + token)
            notes.append("Authorization: Bearer " + mask_secret(token, 8))
        else:
            notes.append("Bearer Token 为空，未添加认证信息")
    elif atype in ("basic", "digest"):
        cfg = auth[atype]
        user = substitute(cfg.get("username", ""), variables)
        pwd = substitute(cfg.get("password", ""), variables)
        if not user and not pwd:
            notes.append("未填写用户名 / 密码，未添加认证信息")
        elif atype == "basic":
            payload["requests_auth"] = (user, pwd)
            notes.append(f"Basic Auth：{user}（由 requests 生成 Authorization 头）")
        else:
            payload["requests_auth"] = HTTPDigestAuth(user, pwd)
            notes.append(f"Digest Auth：{user}（先请求 401 挑战再重发）")
    elif atype == "apikey":
        cfg = auth["apikey"]
        key = substitute(cfg.get("key", ""), variables).strip()
        value = substitute(cfg.get("value", ""), variables)
        if not key:
            notes.append("API Key 名称为空，未添加认证信息")
        elif (cfg.get("in") or "header") == "query":
            params.append((key, value))
            notes.append(f"Query 参数 {key}={mask_secret(value)}")
        else:
            set_header(headers, key, value)
            notes.append(f"Header {key}: {mask_secret(value)}")
    elif atype == "awsv4":
        signed, err = aws_sign_v4(payload, auth["awsv4"], variables)
        if err:
            notes.append("AWS 签名失败：" + err)
        else:
            headers.update(signed)
            notes.append(
                "AWS Signature v4 已写入 Authorization / X-Amz-Date"
                f"（region={substitute(auth['awsv4'].get('region', ''), variables) or 'us-east-1'},"
                f" service={substitute(auth['awsv4'].get('service', ''), variables) or 'execute-api'}）"
            )
            if payload.get("files") is not None:
                notes.append("提示：multipart 请求体未参与签名计算")
    elif atype == "jwt":
        cfg = auth["jwt"]
        token, err = make_jwt(
            cfg.get("algorithm", "HS256"),
            substitute(cfg.get("secret", ""), variables),
            substitute(cfg.get("payload", ""), variables),
        )
        if err:
            notes.append("JWT 生成失败：" + err)
        else:
            value = (cfg.get("prefix") or "") + token
            if (cfg.get("location") or "header") == "query":
                name = (cfg.get("header_name") or "").strip() or "token"
                params.append((name, token))
                notes.append(f"Query 参数 {name}={mask_secret(token, 12)}")
            else:
                name = (cfg.get("header_name") or "").strip() or "Authorization"
                set_header(headers, name, value)
                notes.append(f"{name}: {mask_secret(value, 12)}")
    elif atype == "oauth2":
        cfg = auth["oauth2"]
        if payload.get("_preview"):
            cached = substitute(cfg.get("access_token", ""), variables).strip()
            if cached:
                set_header(headers, "Authorization", "Bearer " + cached)
                notes.append("OAuth 2.0：将附加缓存 Bearer Token（发送请求时可能自动刷新）")
            else:
                grant = cfg.get("grant_type") or "client_credentials"
                notes.append(
                    "OAuth 2.0：发送请求时将自动获取 access_token（"
                    + dict(OAUTH2_GRANTS).get(grant, grant)
                    + "）"
                )
        else:
            token, err = oauth2_ensure_token(cfg, variables)
            if err:
                notes.append("OAuth 2.0 获取令牌失败：" + err)
            elif token:
                set_header(headers, "Authorization", "Bearer " + token)
                notes.append("OAuth 2.0 已附加 Bearer Token：" + mask_secret(token, 8))

    payload["params"] = params or None
    return notes


# --------------------------------------------------------------------------
# 代码生成（curl / Python / JavaScript）
# --------------------------------------------------------------------------
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


def _quote_shell(text: str) -> str:
    return "'" + str(text).replace("'", "'\\''") + "'"


def _quote_py(text: str) -> str:
    return repr(str(text))


def _pretty_py_dict(d: dict) -> str:
    """headers 用多行 repr，便于阅读。"""
    if not d:
        return "{}"
    return "{\n    " + ",\n    ".join(repr(k) + ": " + repr(v) for k, v in d.items()) + ",\n}"

# --------------------------------------------------------------------------
# Postman 集合导入 / 导出
# --------------------------------------------------------------------------
POSTMAN_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


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


# --------------------------------------------------------------------------
# 响应断言与变量提取（纯函数，离屏可测）
# --------------------------------------------------------------------------
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
    HL_COLORS = {
        "dark": {"key": "#7ec8ff", "str": "#8ddb8a", "num": "#f0a45d", "kw": "#c792ea"},
        "light": {"key": "#1a73e8", "str": "#188038", "num": "#b06000", "kw": "#7b1fa2"},
    }

    def __init__(self, parent=None, theme: str = "dark"):
        super().__init__(parent)
        self._theme = theme
        self._build_formats()

    def _build_formats(self) -> None:
        c = self.HL_COLORS.get(self._theme, self.HL_COLORS["dark"])
        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor(c["key"]))
        key_fmt.setFontWeight(QFont.Weight.Bold)
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor(c["str"]))
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor(c["num"]))
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(c["kw"]))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        self._rules = [
            (QRegularExpression(r'"([^"\\]|\\.)*"(?=\s*:)'), key_fmt),
            (QRegularExpression(r'"(?:[^"\\]|\\.)*"'), str_fmt),
            (QRegularExpression(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"), num_fmt),
            (QRegularExpression(r"\b(?:true|false|null)\b"), kw_fmt),
        ]

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._build_formats()
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# --------------------------------------------------------------------------
# 生成代码对话框
# --------------------------------------------------------------------------
class CodeGenDialog(QDialog):
    """展示 curl / Python / JavaScript 三段代码，切换标签即复制对应片段。"""

    def __init__(self, snippets: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生成代码")
        self.resize(700, 500)
        root = QVBoxLayout(self)
        hint = QLabel("切换标签即自动复制对应代码到剪贴板。")
        hint.setStyleSheet("color:#888;")
        root.addWidget(hint)
        self.tabs = QTabWidget()
        self._edits = {}
        for key, label in (("curl", "cURL"), ("python", "Python (requests)"), ("javascript", "JavaScript (fetch)")):
            edit = QPlainTextEdit()
            edit.setReadOnly(True)
            edit.setPlainText(snippets.get(key, ""))
            edit.setStyleSheet(
                "font-family: Consolas, 'Courier New', monospace; font-size: 12px;"
            )
            self.tabs.addTab(edit, label)
            self._edits[key] = edit
        self.tabs.currentChanged.connect(self._copy_current)
        root.addWidget(self.tabs, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        bb.clicked.connect(self.reject)
        root.addWidget(bb)
        self._copy_current(0)

    def _copy_current(self, index: int) -> None:
        if not (0 <= index < len(self._edits)):
            return
        key = list(self._edits.keys())[index]
        QApplication.clipboard().setText(self._edits[key].toPlainText())
        self.setWindowTitle("生成代码 · 已复制 " + key.upper())


# --------------------------------------------------------------------------
# 键值表（Query / Headers / form-data / urlencoded 共用）
# --------------------------------------------------------------------------
class KeyValueTable(QTableWidget):
    def __init__(self, key_label: str = "参数名", value_label: str = "参数值"):
        super().__init__(0, 3)
        self.key_label = key_label
        self._loading = False
        self.setHorizontalHeaderLabels(["启用", key_label, value_label])
        self.setColumnWidth(0, 48)
        self.setColumnWidth(1, 220)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.cellChanged.connect(self._on_cell_changed)
        self._auto_append = True
        self.add_row()

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._loading or not self._auto_append:
            return
        # 仅当最后一行已有内容时自动补一行（避免清空后无限增长）
        if row == self.rowCount() - 1:
            k = self.item(row, 1)
            v = self.item(row, 2)
            if (k and k.text().strip()) or (v and v.text().strip()):
                self.add_row()

    def add_row(self, key: str = "", value: str = "") -> None:
        self._loading = True
        try:
            r = self.rowCount()
            self.insertRow(r)
            chk = QCheckBox()
            chk.setChecked(True)
            chk.setStyleSheet("margin-left:8px;")
            self.setCellWidget(r, 0, chk)
            self.setItem(r, 1, QTableWidgetItem(key))
            self.setItem(r, 2, QTableWidgetItem(value))
        finally:
            self._loading = False

    def delete_selected(self) -> None:
        rows = sorted({i.row() for i in self.selectedItems()}, reverse=True)
        if not rows:
            rows = [self.rowCount() - 1]
        self._loading = True
        try:
            for r in rows:
                if 0 <= r < self.rowCount():
                    self.removeRow(r)
        finally:
            self._loading = False
        if self.rowCount() == 0:
            self.add_row()

    def clear_all(self) -> None:
        self._auto_append = False
        self.setRowCount(0)
        self.add_row()
        self._auto_append = True

    def pairs(self, with_enabled: bool = False):
        out = []
        for r in range(self.rowCount()):
            w = self.cellWidget(r, 0)
            enabled = not isinstance(w, QCheckBox) or w.isChecked()
            k_item = self.item(r, 1)
            v_item = self.item(r, 2)
            key = (k_item.text() if k_item else "").strip()
            if not key:
                continue
            value = v_item.text() if v_item else ""
            if with_enabled:
                out.append({"key": key, "value": value, "enabled": enabled})
            elif enabled:
                out.append((key, value))
        return out

    def set_pairs(self, pairs) -> None:
        self._loading = True
        self._auto_append = False
        self.setRowCount(0)
        for p in pairs:
            if isinstance(p, dict):
                key, value, enabled = p.get("key", ""), p.get("value", ""), p.get("enabled", True)
            else:
                key, value, enabled = p[0], p[1], True
            r = self.rowCount()
            self.insertRow(r)
            chk = QCheckBox()
            chk.setChecked(bool(enabled))
            chk.setStyleSheet("margin-left:8px;")
            self.setCellWidget(r, 0, chk)
            self.setItem(r, 1, QTableWidgetItem(key))
            self.setItem(r, 2, QTableWidgetItem(value))
        self._loading = False
        self._auto_append = True
        if self.rowCount() == 0:
            self.add_row()


# --------------------------------------------------------------------------
# 网络请求线程
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# 集合运行器
# --------------------------------------------------------------------------
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


class CollectionRunnerDialog(QDialog):
    """按顺序运行集合内全部请求，实时展示进度，失败项可双击定位。"""

    def __init__(self, requests_list: list, main: "MainWindow", parent=None):
        super().__init__(parent)
        self._main = main
        self._requests = requests_list
        self._runner = None
        self.setWindowTitle("运行集合")
        self.resize(980, 480)
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.progress_label = QLabel("准备运行 %d 个请求…" % len(requests_list))
        top.addWidget(self.progress_label, 1)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self._stop_clicked)
        top.addWidget(self.stop_btn)
        root.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["#", "方法", "名称 / 错误", "URL", "状态码", "耗时", "断言通过"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 100)
        self.table.cellDoubleClicked.connect(self._locate_row)
        self.table.itemDoubleClicked.connect(lambda it: self._locate_row(it.row(), 0))
        root.addWidget(self.table, 1)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-weight:600;")
        root.addWidget(self.summary_label)

        self._row_of_index = {}

        self._runner = CollectionRunner(
            requests_list,
            self._main.variables(),
            self._main.timeout_spin.value(),
            not self._main.verify_chk.isChecked(),
            self._main.redirect_chk.isChecked(),
            self,
        )
        self._runner.item_done.connect(self._on_item_done)
        self._runner.all_done.connect(self._on_all_done)
        self._runner.finished.connect(self._on_runner_finished)
        self._runner.start()

    def _stop_clicked(self) -> None:
        if self._runner is not None and self._runner.isRunning():
            self._runner.stop()
            self.stop_btn.setEnabled(False)
            self.progress_label.setText("正在停止…")

    def _on_item_done(self, result: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._row_of_index[result.get("index")] = row
        idx = result.get("index", row)
        ok = bool(result.get("ok"))

        def mk(text, color=None):
            it = QTableWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, idx)
            if color:
                it.setForeground(QBrush(QColor(color)))
            return it

        self.table.setItem(row, 0, mk(str(idx + 1)))
        self.table.setItem(row, 1, mk(result.get("method") or "", "#5aa9f0"))
        name_text = result.get("name") or ""
        if result.get("error"):
            name_text = "失败：" + result["error"]
        self.table.setItem(row, 2, mk(name_text, "#f05f5f" if result.get("error") else None))
        self.table.setItem(row, 3, mk(result.get("url") or ""))
        code = result.get("status_code")
        if code is None:
            self.table.setItem(row, 4, mk("ERR", "#f05f5f"))
        else:
            self.table.setItem(row, 4, mk(str(code), STATUS_COLORS.get(str(code)[0], "#8d949c")))
        ms = result.get("elapsed_ms")
        self.table.setItem(row, 5, mk(fmt_ms(ms) if ms is not None else "-"))
        passed = result.get("passed", 0)
        total_n = result.get("total", 0)
        ast_text = f"{passed}/{total_n}" if total_n else "-"
        self.table.setItem(row, 6, mk(ast_text, "#3ecf8e" if total_n and passed == total_n else ("#f0a45d" if total_n else None)))
        self.progress_label.setText("已完成 %d/%d 个请求…" % (row + 1, len(self._requests)))

    def _on_all_done(self, summary: dict) -> None:
        if summary.get("stopped"):
            self.summary_label.setText("已停止：成功 %d / 失败 %d（共 %d 个）" % (summary["success"], summary["failed"], summary["total"]))
        else:
            self.summary_label.setText("运行结束：成功 %d / 失败 %d（共 %d 个）" % (summary["success"], summary["failed"], summary["total"]))

    def _on_runner_finished(self) -> None:
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("完成")

    def _locate_row(self, row: int, _col: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or not (0 <= idx < len(self._requests)):
            return
        req = self._requests[idx]
        self._main._new_request_tab(req)
        self._main.status_msg("已在新标签页定位：" + (req.get("name") or ""))


# --------------------------------------------------------------------------
# 环境管理对话框
# --------------------------------------------------------------------------
class EnvDialog(QDialog):
    def __init__(self, envs: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("环境变量管理")
        self.resize(720, 560)
        self._envs = [dict(e) for e in envs]
        lay = QVBoxLayout(self)

        self.env_list = QListWidget()
        self.env_list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self.env_list, 1)

        btns = QHBoxLayout()
        b_add = QPushButton("新建环境")
        b_add.clicked.connect(self._add_env)
        b_copy = QPushButton("复制环境")
        b_copy.clicked.connect(self._copy_env)
        b_ren = QPushButton("重命名")
        b_ren.clicked.connect(self._rename_env)
        b_del = QPushButton("删除环境")
        b_del.clicked.connect(self._delete_env)
        for b in (b_add, b_copy, b_ren, b_del):
            btns.addWidget(b)
        btns.addStretch(1)
        lay.addLayout(btns)

        self.vars_table = KeyValueTable("变量名", "变量值")
        lay.addWidget(self.vars_table, 1)

        self._name_lab = QLabel("")
        lay.addWidget(self._name_lab)

        self._refresh_list()
        self._on_row(0)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _refresh_list(self) -> None:
        self.env_list.clear()
        for e in self._envs:
            self.env_list.addItem(e.get("name", "未命名"))
        if self.env_list.count() == 0:
            self.env_list.addItem("默认环境")
            self._envs.append({"name": "默认环境", "variables": []})
        self.env_list.setCurrentRow(0)

    def _current_env(self):
        row = self.env_list.currentRow()
        if 0 <= row < len(self._envs):
            return self._envs[row]
        return None

    def _save_row_vars(self) -> None:
        env = self._current_env()
        if env is not None:
            env["variables"] = self.vars_table.pairs(with_enabled=True)

    def _on_row(self, row: int) -> None:
        self._save_row_vars()
        env = self._current_env()
        if env is None:
            return
        self._name_lab.setText("环境：%s" % env.get("name", ""))
        self.vars_table.set_pairs(env.get("variables", []))

    def _add_env(self) -> None:
        self._save_row_vars()
        name, ok = QInputDialog.getText(self, "新建环境", "环境名称：", text="新环境")
        if not ok or not name.strip():
            return
        name = name.strip()
        if any(e.get("name") == name for e in self._envs):
            QMessageBox.warning(self, "重名", "已存在同名环境。")
            return
        self._envs.append({"name": name, "variables": []})
        self._refresh_list()
        self.env_list.setCurrentRow(len(self._envs) - 1)

    def _copy_env(self) -> None:
        env = self._current_env()
        if env is None:
            return
        self._save_row_vars()
        name = env.get("name", "新环境") + " 副本"
        self._envs.append({"name": name, "variables": [dict(v) for v in env.get("variables", [])]})
        self._refresh_list()
        self.env_list.setCurrentRow(len(self._envs) - 1)

    def _rename_env(self) -> None:
        env = self._current_env()
        if env is None:
            return
        self._save_row_vars()
        name, ok = QInputDialog.getText(self, "重命名", "新名称：", text=env.get("name", ""))
        if ok and name.strip():
            env["name"] = name.strip()
            self._refresh_list()

    def _delete_env(self) -> None:
        env = self._current_env()
        if env is None:
            return
        self._save_row_vars()
        if QMessageBox.question(self, "确认", f"确定删除环境「{env.get('name')}」？") != QMessageBox.Yes:
            return
        self._envs.remove(env)
        self._refresh_list()

    def result_data(self) -> list:
        self._save_row_vars()
        return self._envs


# --------------------------------------------------------------------------
# 主题配色（深色 / 浅色）
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# 请求标签页（一个标签 = 一套完整的请求编辑上下文 + 独立响应区）
# --------------------------------------------------------------------------
class RequestTab(QWidget):
    def __init__(self, main, initial: dict = None):
        super().__init__()
        self._main = main
        self._theme = main.current_theme()
        self.worker = None
        self.last_response = None
        self.auth = default_auth()
        self._last_auth_notes = []
        self.is_dirty = False
        self._suppress_dirty = False
        self._auth_bindings = []
        self._auth_secret_widgets = []
        self._auth_hints = []
        self.tests = []
        self.extracts = []
        self._last_json = None
        self._build_ui()
        if initial:
            self.apply_request(initial)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # 顶部：方法 + URL + 发送 + 保存
        top = QHBoxLayout()
        top.setSpacing(6)
        self.method_combo = QComboBox()
        self.method_combo.addItems(METHODS)
        self.method_combo.setFixedWidth(112)
        self.method_combo.setStyleSheet("font-weight:600;")
        self.method_combo.currentIndexChanged.connect(self._mark_dirty)
        self.method_combo.currentIndexChanged.connect(self._notify_label_change)
        top.addWidget(self.method_combo)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("请输入请求地址，支持 {{变量}}，例如 {{base_url}}/api/login")
        self.url_edit.returnPressed.connect(self.send_request)
        self.url_edit.textChanged.connect(self._mark_dirty)
        self.url_edit.textChanged.connect(self._notify_label_change)
        top.addWidget(self.url_edit, 1)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("primary")
        self.send_btn.setFixedWidth(96)
        self.send_btn.clicked.connect(self.send_request)
        top.addWidget(self.send_btn)

        self.save_btn = QPushButton("保存到集合")
        self.save_btn.setFixedWidth(110)
        self.save_btn.clicked.connect(lambda: self._main.save_to_collection(self))
        top.addWidget(self.save_btn)

        self.code_btn = QPushButton("生成代码")
        self.code_btn.setFixedWidth(96)
        self.code_btn.clicked.connect(self._show_codegen)
        top.addWidget(self.code_btn)
        root.addLayout(top)

        # 主体：请求详情 + 响应
        split = QSplitter(Qt.Vertical)
        root.addWidget(split, 1)
        self.req_tabs = QTabWidget()

        # ---- Query 参数 ----
        params_wrap = QWidget()
        pv = QVBoxLayout(params_wrap)
        pv.setContentsMargins(6, 6, 6, 6)
        self.params_table = KeyValueTable()
        self.params_table.cellChanged.connect(self._mark_dirty)
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
        self.req_tabs.addTab(params_wrap, "Query 参数")

        # ---- Authorization ----
        auth_wrap = QWidget()
        av = QVBoxLayout(auth_wrap)
        av.setContentsMargins(6, 6, 6, 6)

        at = QHBoxLayout()
        at.addWidget(QLabel("认证类型："))
        self.auth_type = QComboBox()
        self.auth_type.addItems(AUTH_TYPE_LABELS)
        self.auth_type.setFixedWidth(200)
        self.auth_type.currentIndexChanged.connect(self._on_auth_type_changed)
        at.addWidget(self.auth_type)
        self.auth_show_chk = QCheckBox("显示密钥")
        self.auth_show_chk.stateChanged.connect(self._toggle_auth_secret)
        at.addWidget(self.auth_show_chk)
        at.addStretch(1)
        av.addLayout(at)

        self.auth_stack = QStackedWidget()
        self.auth = default_auth()

        def auth_page(fields, hint=""):
            outer = QWidget()
            fl = QFormLayout(outer)
            fl.setContentsMargins(6, 6, 6, 6)
            fl.setLabelAlignment(Qt.AlignRight)
            for text, widget, path, secret in fields:
                lab = QLabel(text)
                fl.addRow(lab, widget)
                self._bind_auth(path, widget, secret)
            if hint:
                lab = QLabel(hint)
                lab.setWordWrap(True)
                lab.setStyleSheet(self._hint_style())
                fl.addRow(lab)
                self._auth_hints.append(lab)
            self.auth_stack.addWidget(outer)

        # 0 无认证
        none_page = QLabel("不使用认证信息。")
        none_page.setAlignment(Qt.AlignCenter)
        none_page.setStyleSheet(self._muted_style())
        self.auth_stack.addWidget(none_page)

        # 1 Bearer
        self.auth_bearer_token = QLineEdit()
        self.auth_bearer_token.setPlaceholderText("如 {{token}}")
        auth_page([("Token：", self.auth_bearer_token, "bearer.token", True)], "自动写入 Authorization: Bearer <token>。")

        # 2 Basic
        self.auth_basic_user = QLineEdit()
        self.auth_basic_user.setPlaceholderText("用户名")
        self.auth_basic_pwd = QLineEdit()
        self.auth_basic_pwd.setPlaceholderText("密码")
        auth_page(
            [("用户名：", self.auth_basic_user, "basic.username", False), ("密码：", self.auth_basic_pwd, "basic.password", True)],
            "使用 HTTP Basic 认证，由 requests 自动生成 Authorization 头。",
        )

        # 3 Digest
        self.auth_digest_user = QLineEdit()
        self.auth_digest_user.setPlaceholderText("用户名")
        self.auth_digest_pwd = QLineEdit()
        self.auth_digest_pwd.setPlaceholderText("密码")
        auth_page(
            [("用户名：", self.auth_digest_user, "digest.username", False), ("密码：", self.auth_digest_pwd, "digest.password", True)],
            "HTTP Digest 摘要认证：首次请求收到 401 挑战后，自动按服务器 nonce 重发。",
        )

        # 4 API Key
        self.auth_apikey_key = QLineEdit()
        self.auth_apikey_key.setPlaceholderText("如 X-API-Key")
        self.auth_apikey_value = QLineEdit()
        self.auth_apikey_value.setPlaceholderText("如 {{api_key}}")
        self.auth_apikey_in = QComboBox()
        self.auth_apikey_in.addItem("Header", "header")
        self.auth_apikey_in.addItem("Query 参数", "query")
        auth_page(
            [("Key 名称：", self.auth_apikey_key, "apikey.key", False), ("Value：", self.auth_apikey_value, "apikey.value", True), ("添加到：", self.auth_apikey_in, "apikey.in", False)],
            "把 Key/Value 作为请求头或查询参数附加到请求上。",
        )

        # 5 AWS Signature v4
        self.auth_aws_access = QLineEdit()
        self.auth_aws_access.setPlaceholderText("AKIA...")
        self.auth_aws_secret = QLineEdit()
        self.auth_aws_secret.setPlaceholderText("Secret Access Key")
        self.auth_aws_session = QLineEdit()
        self.auth_aws_session.setPlaceholderText("可选，临时凭证才需要")
        self.auth_aws_region = QLineEdit("us-east-1")
        self.auth_aws_service = QLineEdit("execute-api")
        auth_page(
            [
                ("Access Key：", self.auth_aws_access, "awsv4.access_key", False),
                ("Secret Key：", self.auth_aws_secret, "awsv4.secret_key", True),
                ("Session Token：", self.auth_aws_session, "awsv4.session_token", True),
                ("Region：", self.auth_aws_region, "awsv4.region", False),
                ("Service：", self.auth_aws_service, "awsv4.service", False),
            ],
            "按 AWS4-HMAC-SHA256 对当前方法 / 地址 / 查询串 / 请求体现场签名，"
            "自动写入 X-Amz-Date 与 Authorization 头（API Gateway 常用 Service=execute-api）。",
        )

        # 6 JWT
        self.auth_jwt_alg = QComboBox()
        for alg in JWT_ALGORITHMS:
            self.auth_jwt_alg.addItem(alg, alg)
        self.auth_jwt_secret = QLineEdit()
        self.auth_jwt_secret.setPlaceholderText("HS256/384/512 的签名密钥")
        self.auth_jwt_payload = QPlainTextEdit()
        self.auth_jwt_payload.setPlaceholderText('{\n    "sub": "1234567890"\n}')
        self.auth_jwt_payload.setFixedHeight(96)
        self.auth_jwt_loc = QComboBox()
        self.auth_jwt_loc.addItem("Header", "header")
        self.auth_jwt_loc.addItem("Query 参数", "query")
        self.auth_jwt_name = QLineEdit("Authorization")
        self.auth_jwt_prefix = QLineEdit("Bearer ")
        auth_page(
            [
                ("算法：", self.auth_jwt_alg, "jwt.algorithm", False),
                ("Secret：", self.auth_jwt_secret, "jwt.secret", True),
                ("Payload：", self.auth_jwt_payload, "jwt.payload", False),
                ("添加到：", self.auth_jwt_loc, "jwt.location", False),
                ("名称：", self.auth_jwt_name, "jwt.header_name", False),
                ("前缀：", self.auth_jwt_prefix, "jwt.prefix", False),
            ],
            "本地用密钥对 Payload 现场签发 JWT（HS256/HS384/HS512）。"
            "iat / exp 等声明请自行写在 Payload 里。",
        )

        # 7 OAuth 2.0
        self.auth_oauth2_grant = QComboBox()
        for gk, gl in OAUTH2_GRANTS:
            self.auth_oauth2_grant.addItem(gl, gk)
        self.auth_oauth2_token_url = QLineEdit()
        self.auth_oauth2_token_url.setPlaceholderText("https://auth.example.com/oauth/token")
        self.auth_oauth2_client_id = QLineEdit()
        self.auth_oauth2_client_secret = QLineEdit()
        self.auth_oauth2_client_secret.setPlaceholderText("Client Secret")
        self.auth_oauth2_username = QLineEdit()
        self.auth_oauth2_username.setPlaceholderText("Password 模式使用")
        self.auth_oauth2_password = QLineEdit()
        self.auth_oauth2_password.setPlaceholderText("Password 模式使用")
        self.auth_oauth2_scope = QLineEdit()
        self.auth_oauth2_scope.setPlaceholderText("可选，空格分隔多个 scope")
        self.auth_oauth2_extra = QLineEdit()
        self.auth_oauth2_extra.setPlaceholderText('可选 JSON，如 {"audience": "api"}')
        self.auth_oauth2_authorize_url = QLineEdit()
        self.auth_oauth2_authorize_url.setPlaceholderText("https://auth.example.com/oauth/authorize")
        self.auth_oauth2_redirect_uri = QLineEdit()
        self.auth_oauth2_redirect_uri.setPlaceholderText("https://client.example.com/callback")
        self.auth_oauth2_code = QLineEdit()
        self.auth_oauth2_code.setPlaceholderText("授权码（可自动获取，也可粘贴回调地址后提取）")
        self.auth_oauth2_access_token = QLineEdit()
        self.auth_oauth2_access_token.setPlaceholderText("手动粘贴 access_token（可选，留空则自动获取）")
        self.auth_oauth2_refresh_token = QLineEdit()
        self.auth_oauth2_refresh_token.setPlaceholderText("手动粘贴 refresh_token（可选）")
        self.auth_oauth2_auto = QCheckBox("过期后自动刷新（需要 refresh_token）")
        self.auth_oauth2_auto.stateChanged.connect(self._mark_dirty)
        self.auth_oauth2_auto.stateChanged.connect(self._on_auth_changed)
        oauth_page = QWidget()
        of = QFormLayout(oauth_page)
        of.setContentsMargins(6, 6, 6, 6)
        of.setLabelAlignment(Qt.AlignRight)
        of.addRow("授权流程：", self.auth_oauth2_grant)
        self._bind_auth("oauth2.grant_type", self.auth_oauth2_grant)
        of.addRow("Token URL：", self.auth_oauth2_token_url)
        self._bind_auth("oauth2.token_url", self.auth_oauth2_token_url)
        of.addRow("Client ID：", self.auth_oauth2_client_id)
        self._bind_auth("oauth2.client_id", self.auth_oauth2_client_id)
        of.addRow("Client Secret：", self.auth_oauth2_client_secret)
        self._bind_auth("oauth2.client_secret", self.auth_oauth2_client_secret, True)
        of.addRow("用户名：", self.auth_oauth2_username)
        self._bind_auth("oauth2.username", self.auth_oauth2_username)
        of.addRow("密码：", self.auth_oauth2_password)
        self._bind_auth("oauth2.password", self.auth_oauth2_password, True)
        of.addRow("Scope：", self.auth_oauth2_scope)
        self._bind_auth("oauth2.scope", self.auth_oauth2_scope)
        of.addRow("额外参数(JSON)：", self.auth_oauth2_extra)
        self._bind_auth("oauth2.extra", self.auth_oauth2_extra)
        of.addRow("授权 URL：", self.auth_oauth2_authorize_url)
        self._bind_auth("oauth2.authorize_url", self.auth_oauth2_authorize_url)
        of.addRow("回调地址：", self.auth_oauth2_redirect_uri)
        self._bind_auth("oauth2.redirect_uri", self.auth_oauth2_redirect_uri)
        of.addRow("授权码：", self.auth_oauth2_code)
        self._bind_auth("oauth2.authorization_code", self.auth_oauth2_code)
        b_auth = QPushButton("获取授权码并打开浏览器")
        b_auth.clicked.connect(self._oauth2_authorize)
        b_paste = QPushButton("粘贴回调地址提取授权码")
        b_paste.clicked.connect(self._oauth2_paste_callback)
        auth_btns = QHBoxLayout()
        auth_btns.addWidget(b_auth)
        auth_btns.addWidget(b_paste)
        of.addRow("", auth_btns)
        of.addRow("Access Token：", self.auth_oauth2_access_token)
        self._bind_auth("oauth2.access_token", self.auth_oauth2_access_token, True)
        of.addRow("Refresh Token：", self.auth_oauth2_refresh_token)
        self._bind_auth("oauth2.refresh_token", self.auth_oauth2_refresh_token, True)
        of.addRow("", self.auth_oauth2_auto)
        b_refresh = QPushButton("手动刷新 Token")
        b_refresh.clicked.connect(self._oauth2_refresh_now)
        b_clear = QPushButton("清除 Token")
        b_clear.clicked.connect(self._oauth2_clear_token)
        tk_btns = QHBoxLayout()
        tk_btns.addWidget(b_refresh)
        tk_btns.addWidget(b_clear)
        of.addRow("", tk_btns)
        lab_hint = QLabel(
            "Client Credentials / Password 模式在发送请求时自动向 Token URL 换取 access_token "
            "并附加 Bearer；Authorization Code 模式先获取授权码，发送时用授权码换 token。"
            "获取到的 token 随请求快照持久化，可用「手动刷新 Token」刷新。"
        )
        lab_hint.setWordWrap(True)
        lab_hint.setStyleSheet(self._hint_style())
        of.addRow(lab_hint)
        self._auth_hints.append(lab_hint)
        self.auth_stack.addWidget(oauth_page)

        av.addWidget(self.auth_stack)

        self.auth_preview = QLabel("不使用认证信息。")
        self.auth_preview.setWordWrap(True)
        self.auth_preview.setStyleSheet(self._preview_style())
        av.addWidget(self.auth_preview)
        av.addStretch(1)
        self.req_tabs.addTab(auth_wrap, "Authorization")

        # 认证预览跟随地址 / 方法 / 环境变化
        self.url_edit.textChanged.connect(self._on_auth_changed)
        self.method_combo.currentIndexChanged.connect(self._on_auth_changed)
        self._main.env_combo.currentIndexChanged.connect(self.refresh_auth_preview)

        # ---- Headers ----
        head_wrap = QWidget()
        hv2 = QVBoxLayout(head_wrap)
        hv2.setContentsMargins(6, 6, 6, 6)
        self.headers_table = KeyValueTable()
        self.headers_table.cellChanged.connect(self._mark_dirty)
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
        self.req_tabs.addTab(head_wrap, "Headers")

        # ---- Body ----
        body_wrap = QWidget()
        bv = QVBoxLayout(body_wrap)
        bv.setContentsMargins(6, 6, 6, 6)
        bt = QHBoxLayout()
        bt.addWidget(QLabel("Body 类型："))
        self.body_type = QComboBox()
        self.body_type.addItems(["none", "JSON", "form-data", "x-www-form-urlencoded"])
        self.body_type.setFixedWidth(210)
        self.body_type.currentIndexChanged.connect(self._on_body_type_changed)
        self.body_type.currentIndexChanged.connect(self._mark_dirty)
        bt.addWidget(self.body_type)
        self.fmt_btn = QPushButton("格式化 JSON")
        self.fmt_btn.clicked.connect(self.format_json_body)
        bt.addWidget(self.fmt_btn)
        self.body_hint = QLabel("")
        self.body_hint.setStyleSheet(self._hint_style())
        bt.addWidget(self.body_hint)
        bt.addStretch(1)
        bv.addLayout(bt)

        self.body_stack = QStackedWidget()
        bv.addWidget(self.body_stack, 1)

        none_page = QLabel("该请求不携带 Body。")
        none_page.setAlignment(Qt.AlignCenter)
        none_page.setStyleSheet(self._muted_style())
        self.body_stack.addWidget(none_page)

        self.body_json = QPlainTextEdit()
        self.body_json.setPlaceholderText('{\n    "key": "value"\n}')
        self.body_json.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.body_json.textChanged.connect(self._mark_dirty)
        self.json_hl = JsonHighlighter(self.body_json.document(), self._theme)
        self.body_stack.addWidget(self.body_json)

        self.body_form = KeyValueTable(key_label="字段名")
        self.body_form.cellChanged.connect(self._mark_dirty)
        self.body_stack.addWidget(self.body_form)

        self.body_urlenc = KeyValueTable(key_label="字段名")
        self.body_urlenc.cellChanged.connect(self._mark_dirty)
        self.body_stack.addWidget(self.body_urlenc)
        self.req_tabs.addTab(body_wrap, "Body")

        # ---- 响应区 ----
        resp_wrap = QWidget()
        rv = QVBoxLayout(resp_wrap)
        rv.setContentsMargins(6, 6, 6, 6)
        rv.setSpacing(6)

        rbar = QHBoxLayout()
        self.status_label = QLabel("尚未发送请求")
        self.status_label.setObjectName("statusChip")
        self._set_status_chip("尚未发送请求", "default")
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
        self.resp_hl = JsonHighlighter(self.resp_body.document(), self._theme)
        self.resp_tabs.addTab(self.resp_body, "响应体")
        self.resp_headers = QTableWidget(0, 2)
        self.resp_headers.setHorizontalHeaderLabels(["响应头", "值"])
        self.resp_headers.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.resp_headers.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.resp_headers.setColumnWidth(0, 260)
        self.resp_headers.verticalHeader().setVisible(False)
        self.resp_headers.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.resp_tabs.addTab(self.resp_headers, "响应头")

        # 测试 / 变量提取
        tests_wrap = QWidget()
        tv = QVBoxLayout(tests_wrap)
        tv.setContentsMargins(6, 6, 6, 6)
        tv.setSpacing(6)

        tlab = QLabel("断言（发送请求后自动执行，逐条显示通过 / 失败并汇总）：")
        tlab.setStyleSheet(self._hint_style())
        tv.addWidget(tlab)
        self.tests_table = QTableWidget(0, 4)
        self.tests_table.setHorizontalHeaderLabels(["启用", "断言类型", "参数", "期望值"])
        self.tests_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tests_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tests_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tests_table.verticalHeader().setVisible(False)
        self.tests_table.setColumnWidth(0, 46)
        self.tests_table.setColumnWidth(3, 140)
        self.tests_table.cellChanged.connect(self._mark_dirty)
        tv.addWidget(self.tests_table, 1)
        tbtn = QHBoxLayout()
        b_add = QPushButton("添加断言")
        b_add.clicked.connect(lambda: self._add_assertion_row())
        b_del = QPushButton("删除选中")
        b_del.clicked.connect(self._delete_assertion_rows)
        b_run = QPushButton("重新执行")
        b_run.clicked.connect(self._rerun_tests)
        tbtn.addWidget(b_add)
        tbtn.addWidget(b_del)
        tbtn.addWidget(b_run)
        tbtn.addStretch(1)
        tv.addLayout(tbtn)
        self.test_result = QLabel("发送请求后自动执行断言。")
        self.test_result.setWordWrap(True)
        self.test_result.setTextFormat(Qt.RichText)
        tv.addWidget(self.test_result)

        tv.addSpacing(10)
        elab = QLabel("变量提取（从响应中提取值写入当前环境变量，后续请求可用 {{变量}} 引用）：")
        elab.setStyleSheet(self._hint_style())
        tv.addWidget(elab)
        self.extract_table = QTableWidget(0, 3)
        self.extract_table.setHorizontalHeaderLabels(["变量名", "类型", "表达式"])
        self.extract_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.extract_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.extract_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.extract_table.verticalHeader().setVisible(False)
        self.extract_table.setColumnWidth(0, 150)
        self.extract_table.setColumnWidth(1, 110)
        self.extract_table.cellChanged.connect(self._mark_dirty)
        tv.addWidget(self.extract_table, 1)
        ebtn = QHBoxLayout()
        b_eadd = QPushButton("添加提取")
        b_eadd.clicked.connect(lambda: self._add_extract_row())
        b_edel = QPushButton("删除选中")
        b_edel.clicked.connect(self._delete_extract_rows)
        ebtn.addWidget(b_eadd)
        ebtn.addWidget(b_edel)
        ebtn.addStretch(1)
        tv.addLayout(ebtn)
        self.extract_result = QLabel("")
        self.extract_result.setWordWrap(True)
        self.extract_result.setTextFormat(Qt.RichText)
        tv.addWidget(self.extract_result)
        tv.addStretch(1)

        self.resp_tabs.addTab(tests_wrap, "测试")
        rv.addWidget(self.resp_tabs, 1)
        split.addWidget(self.req_tabs)
        split.addWidget(resp_wrap)
        split.setSizes([420, 420])

    # ------------------------------------------------------------------
    # 主题 / 样式辅助
    # ------------------------------------------------------------------
    def _hint_style(self) -> str:
        return f"color:{THEME_COLORS[self._theme]['hint']};"

    def _muted_style(self) -> str:
        return f"color:{THEME_COLORS[self._theme]['muted']};"

    def _preview_style(self) -> str:
        return f"color:{THEME_COLORS[self._theme]['preview']}; padding:2px 0;"

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self.json_hl.set_theme(theme)
        self.resp_hl.set_theme(theme)
        for lab in self._auth_hints:
            lab.setStyleSheet(self._hint_style())
        self.body_hint.setStyleSheet(self._hint_style())
        self.auth_preview.setStyleSheet(self._preview_style())
        for i in range(self.body_stack.count()):
            w = self.body_stack.widget(i)
            if isinstance(w, QLabel) and not w.text().strip().startswith("{"):
                w.setStyleSheet(self._muted_style())
        if self.status_label.text() == "尚未发送请求":
            self._set_status_chip("尚未发送请求", "default")

    def refresh_auth_preview(self, *_args) -> None:
        self._on_auth_changed()

    def _set_status_chip(self, text: str, kind: str = "default") -> None:
        c = THEME_COLORS[self._theme]
        if kind == "busy":
            bg, fg = c["chip_busy_bg"], c["chip_busy_fg"]
        elif kind == "err":
            bg, fg = c["chip_err_bg"], c["chip_err_fg"]
        else:
            bg, fg = c["chip_default_bg"], c["chip_default_fg"]
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"background:{bg}; color:{fg}; padding:4px 12px; border-radius:10px; font-weight:600;"
        )

    def _set_status_chip_color(self, color: str) -> None:
        self.status_label.setStyleSheet(
            f"background:{color}33; color:{color}; padding:4px 12px; border-radius:10px; font-weight:700;"
        )

    # ------------------------------------------------------------------
    # 标签脏标记
    # ------------------------------------------------------------------
    def _mark_dirty(self, *_args) -> None:
        if not self._suppress_dirty:
            self.is_dirty = True

    def _notify_label_change(self, *_args) -> None:
        self._main._update_tab_label(self)

    # ------------------------------------------------------------------
    # 认证面板
    # ------------------------------------------------------------------
    def _bind_auth(self, path: str, widget, secret: bool = False) -> None:
        self._auth_bindings.append((path, widget))
        if secret:
            self._auth_secret_widgets.append(widget)
            widget.setEchoMode(QLineEdit.EchoMode.Password)
        if isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(self._on_auth_changed)
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(self._on_auth_changed)
        else:
            widget.textChanged.connect(self._on_auth_changed)
        widget.textChanged.connect(self._mark_dirty) if not isinstance(widget, QComboBox) else None

    def _toggle_auth_secret(self) -> None:
        show = self.auth_show_chk.isChecked()
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        for widget in self._auth_secret_widgets:
            widget.setEchoMode(mode)

    # ---- OAuth 2.0 面板操作 ----
    def _oauth2_authorize(self) -> None:
        self._sync_auth_from_ui()
        url = oauth2_build_authorize_url(self.auth["oauth2"], self._main.variables())
        if not url:
            QMessageBox.information(self, "提示", "请先填写授权 URL（Authorization URL）。")
            return
        QApplication.clipboard().setText(url)
        self._main.status_msg("授权 URL 已复制到剪贴板，正在打开浏览器…")
        QDesktopServices.openUrl(QUrl(url))

    def _oauth2_paste_callback(self) -> None:
        self._sync_auth_from_ui()
        text = QApplication.clipboard().text() or ""
        code, ok = QInputDialog.getText(
            self, "粘贴回调地址", "粘贴授权后的回调地址（应包含 code=…）：", text=text
        )
        if not ok:
            return
        code_val = oauth2_extract_code(code)
        if not code_val:
            QMessageBox.warning(self, "提示", "未从回调地址中提取到 code 参数。")
            return
        self.auth["oauth2"]["authorization_code"] = code_val
        self._auth_set_widget_value(self.auth_oauth2_code, code_val)
        self._update_auth_preview()
        self._mark_dirty()
        self._main.status_msg("已提取授权码：" + mask_secret(code_val))

    def _oauth2_refresh_now(self) -> None:
        self._sync_auth_from_ui()
        token_dict, err = oauth2_refresh_token(self.auth["oauth2"], self._main.variables())
        if err:
            QMessageBox.warning(self, "刷新失败", err)
            return
        _oauth2_save_token(self.auth["oauth2"], token_dict)
        self.set_auth(self.auth)
        self._main.status_msg("Token 已刷新并写入当前请求配置。")

    def _oauth2_clear_token(self) -> None:
        self._sync_auth_from_ui()
        self.auth["oauth2"]["access_token"] = ""
        self.auth["oauth2"]["refresh_token"] = ""
        self.auth["oauth2"]["expires_at"] = 0
        self.auth["oauth2"]["authorization_code"] = ""
        self.set_auth(self.auth)
        self._main.status_msg("已清除 OAuth 2.0 Token。")

    def _on_auth_type_changed(self, index: int) -> None:
        if 0 <= index < self.auth_stack.count():
            self.auth_stack.setCurrentIndex(index)
        self._on_auth_changed()
        self._mark_dirty()

    def _on_auth_changed(self, *_args) -> None:
        self._sync_auth_from_ui()
        self._update_auth_preview()

    @staticmethod
    def _auth_widget_value(widget):
        if isinstance(widget, QComboBox):
            data = widget.currentData()
            return data if data is not None else widget.currentText()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        return ""

    @staticmethod
    def _auth_set_widget_value(widget, value) -> None:
        value = "" if value is None else value
        if isinstance(widget, QComboBox):
            for i in range(widget.count()):
                if widget.itemData(i) == value or widget.itemText(i) == value:
                    widget.setCurrentIndex(i)
                    return
            widget.setCurrentIndex(0)
        elif isinstance(widget, QPlainTextEdit):
            widget.setPlainText(str(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))

    def _sync_auth_from_ui(self) -> None:
        auth = merge_auth(self.auth)
        index = self.auth_type.currentIndex()
        if 0 <= index < len(AUTH_TYPE_KEYS):
            auth["type"] = AUTH_TYPE_KEYS[index]
        for path, widget in self._auth_bindings:
            section, _, field = path.partition(".")
            auth.setdefault(section, {})[field] = self._auth_widget_value(widget)
        if hasattr(self, "auth_oauth2_auto"):
            auth["oauth2"]["auto_refresh"] = bool(self.auth_oauth2_auto.isChecked())
        self.auth = auth

    def auth_snapshot(self) -> dict:
        return merge_auth(self.auth)

    def set_auth(self, data) -> None:
        auth = merge_auth(data)
        for path, widget in self._auth_bindings:
            section, _, field = path.partition(".")
            self._auth_set_widget_value(widget, auth.get(section, {}).get(field, ""))
        index = AUTH_TYPE_KEYS.index(auth["type"]) if auth["type"] in AUTH_TYPE_KEYS else 0
        self.auth_type.blockSignals(True)
        self.auth_type.setCurrentIndex(index)
        self.auth_type.blockSignals(False)
        self.auth_stack.setCurrentIndex(index)
        if hasattr(self, "auth_oauth2_auto"):
            oauth = auth.get("oauth2", {})
            self.auth_oauth2_auto.blockSignals(True)
            self.auth_oauth2_auto.setChecked(bool(oauth.get("auto_refresh")))
            self.auth_oauth2_auto.blockSignals(False)
        self.auth = auth
        self._update_auth_preview()

    def _update_auth_preview(self) -> None:
        auth = self.auth_snapshot()
        if auth["type"] == "noauth":
            self.auth_preview.setText("不使用认证信息。")
            return
        if auth["type"] == "awsv4" and not self.url_edit.text().strip():
            self.auth_preview.setText("预览 → 请先填写请求地址（AWS 签名依赖 Host 与请求路径）")
            return
        probe = {
            "method": self.method_combo.currentText(),
            "url": substitute(self.url_edit.text().strip(), self._main.variables()),
            "headers": {},
            "params": [],
            "data": None,
            "files": None,
            "json": None,
            "requests_auth": None,
            "_preview": True,
        }
        try:
            notes = apply_auth(probe, auth, self._main.variables())
        except Exception as e:  # noqa: BLE001
            self.auth_preview.setText("认证预览失败：" + str(e))
            return
        self.auth_preview.setText("预览 → " + ("；".join(notes) if notes else "无变化"))

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
            self._main.status_msg("URL 中没有查询参数")
            return
        base, _, query = url.partition("?")
        self.url_edit.setText(base)
        count = 0
        for k, v in parse_qsl(query, keep_blank_values=True):
            self.params_table.add_row(k, v)
            count += 1
        self._main.status_msg(f"已从 URL 导入 {count} 个查询参数")

    # ------------------------------------------------------------------
    # 发送请求
    # ------------------------------------------------------------------
    def _show_codegen(self) -> None:
        try:
            req = self.snapshot()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "生成代码", "获取请求配置失败：" + str(e))
            return
        snippets = generate_code_snippets(req, self._main.variables())
        dlg = CodeGenDialog(snippets, self)
        dlg.exec()

    def _collect_request(self) -> dict:
        variables = self._main.variables()
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
            "timeout": self._main.timeout_spin.value(),
            "verify": not self._main.verify_chk.isChecked(),
            "allow_redirects": self._main.redirect_chk.isChecked(),
            "data": None,
            "files": None,
            "json": None,
            "requests_auth": None,
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

        payload["_auth_notes"] = apply_auth(payload, self.auth, variables)
        payload["_raw_url"] = raw_url
        return payload

    def send_request(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._main.status_msg("已有请求正在进行中…")
            return
        payload = self._collect_request()
        if not payload["url"]:
            QMessageBox.information(self, "提示", "请先输入请求地址。")
            return
        if "{{" in payload["url"]:
            self._main.status_msg("警告：URL 中仍存在未解析的变量")

        self.send_btn.setEnabled(False)
        self.send_btn.setText("请求中")
        self._set_status_chip("请求中…", "busy")
        self._main._save_settings()
        self._main._persist()

        self._last_auth_notes = list(payload.get("_auth_notes") or [])
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
        self._set_status_chip("请求失败", "err")
        self.time_label.setText("耗时：-")
        self.size_label.setText("大小：-")
        self.resp_body.setPlainText(message)
        self.resp_headers.setRowCount(0)
        self.test_result.setText('<span style="color:#f05f5f;">请求失败，未执行断言。</span>')
        self.extract_result.setText("")
        self._main._add_history(self.snapshot(), error=message)
        self._main.status_msg("请求失败：" + message.splitlines()[0] + self._auth_note_suffix(), 10000)

    def _on_response(self, data: dict) -> None:
        self.last_response = data
        code = data["status_code"]
        color = STATUS_COLORS.get(str(code)[0], "#8d949c")
        self.status_label.setText(f"{code} {data.get('reason', '')}".strip())
        self._set_status_chip_color(color)
        self.time_label.setText(f"耗时：{fmt_ms(data['elapsed_ms'])}")
        self.size_label.setText(f"大小：{fmt_size(data['size'])}")
        self._render_response_body()

        self.resp_headers.setRowCount(0)
        for i, (k, v) in enumerate(data.get("headers", [])):
            self.resp_headers.insertRow(i)
            self.resp_headers.setItem(i, 0, QTableWidgetItem(str(k)))
            self.resp_headers.setItem(i, 1, QTableWidgetItem(str(v)))

        self._run_tests_and_extracts(data)
        self._main._add_history(self.snapshot(), status=code)
        self._main.status_msg(
            f"请求完成：{code} · {fmt_ms(data['elapsed_ms'])} · {fmt_size(data['size'])}"
            + self._auth_note_suffix(),
            8000,
        )

    def _auth_note_suffix(self) -> str:
        if not self._last_auth_notes:
            return ""
        return "　|　认证：" + "；".join(self._last_auth_notes)

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
            self._main.status_msg("暂无响应内容可复制")
            return
        QApplication.clipboard().setText(self.last_response.get("text", ""))
        self._main.status_msg("响应内容已复制到剪贴板")

    def save_response(self) -> None:
        if not self.last_response:
            self._main.status_msg("暂无响应内容可保存")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存响应内容", os.path.join(app_dir(), "response.txt"), "文本文件 (*.txt);;JSON (*.json);;所有文件 (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.last_response.get("text", ""))
            self._main.status_msg("响应已保存到 " + path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "保存失败", str(e))

    # ------------------------------------------------------------------
    # 请求快照 / 载入
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 断言 / 变量提取辅助
    # ------------------------------------------------------------------
    def _add_assertion_row(self, atype="status_eq", arg1="", arg2=""):
        row = self.tests_table.rowCount()
        self.tests_table.insertRow(row)
        chk = QCheckBox()
        chk.setChecked(True)
        chk.stateChanged.connect(self._mark_dirty)
        self.tests_table.setCellWidget(row, 0, chk)
        cb = QComboBox()
        for key, lab in ASSERT_TYPES:
            cb.addItem(lab, key)
        idx = next((i for i in range(cb.count()) if cb.itemData(i) == atype), 0)
        cb.setCurrentIndex(idx)
        cb.currentIndexChanged.connect(self._mark_dirty)
        self.tests_table.setCellWidget(row, 1, cb)
        self.tests_table.setItem(row, 2, QTableWidgetItem(str(arg1)))
        self.tests_table.setItem(row, 3, QTableWidgetItem(str(arg2)))

    def _delete_assertion_rows(self):
        rows = sorted({i.row() for i in self.tests_table.selectedItems()}, reverse=True)
        for r in rows:
            self.tests_table.removeRow(r)
        if rows:
            self._mark_dirty()

    def _add_extract_row(self, key="", etype="jsonpath", expr=""):
        row = self.extract_table.rowCount()
        self.extract_table.insertRow(row)
        self.extract_table.setItem(row, 0, QTableWidgetItem(str(key)))
        cb = QComboBox()
        for tkey, tlab in EXTRACT_TYPES:
            cb.addItem(tlab, tkey)
        idx = next((i for i in range(cb.count()) if cb.itemData(i) == etype), 0)
        cb.setCurrentIndex(idx)
        cb.currentIndexChanged.connect(self._mark_dirty)
        self.extract_table.setCellWidget(row, 1, cb)
        self.extract_table.setItem(row, 2, QTableWidgetItem(str(expr)))

    def _delete_extract_rows(self):
        rows = sorted({i.row() for i in self.extract_table.selectedItems()}, reverse=True)
        for r in rows:
            self.extract_table.removeRow(r)
        if rows:
            self._mark_dirty()

    def _collect_tests_from_ui(self) -> list:
        out = []
        for row in range(self.tests_table.rowCount()):
            w = self.tests_table.cellWidget(row, 0)
            enabled = bool(w.isChecked()) if isinstance(w, QCheckBox) else True
            cb = self.tests_table.cellWidget(row, 1)
            atype = cb.currentData() if isinstance(cb, QComboBox) else "status_eq"
            arg1 = self.tests_table.item(row, 2).text() if self.tests_table.item(row, 2) else ""
            arg2 = self.tests_table.item(row, 3).text() if self.tests_table.item(row, 3) else ""
            out.append({"enabled": enabled, "type": atype, "arg1": arg1, "arg2": arg2})
        return out

    def _collect_extracts_from_ui(self) -> list:
        out = []
        for row in range(self.extract_table.rowCount()):
            key = self.extract_table.item(row, 0).text() if self.extract_table.item(row, 0) else ""
            cb = self.extract_table.cellWidget(row, 1)
            etype = cb.currentData() if isinstance(cb, QComboBox) else "jsonpath"
            expr = self.extract_table.item(row, 2).text() if self.extract_table.item(row, 2) else ""
            out.append({"key": key, "type": etype, "expr": expr})
        return out

    def _load_tests_from_data(self, tests) -> None:
        self.tests_table.setRowCount(0)
        for t in tests or []:
            if isinstance(t, dict):
                self._add_assertion_row(t.get("type", "status_eq"), t.get("arg1", ""), t.get("arg2", ""))

    def _load_extracts_from_data(self, extracts) -> None:
        self.extract_table.setRowCount(0)
        for e in extracts or []:
            if isinstance(e, dict):
                self._add_extract_row(e.get("key", ""), e.get("type", "jsonpath"), e.get("expr", ""))

    def _rerun_tests(self):
        if self.last_response is None:
            self._main.status_msg("暂无响应，无法执行断言")
            return
        self._run_tests_and_extracts(self.last_response)

    def _run_tests_and_extracts(self, data: dict) -> None:
        text = data.get("text", "") or ""
        try:
            json_obj = json.loads(text)
        except Exception:  # noqa: BLE001
            json_obj = None
        self._last_json = json_obj
        ctx = {
            "status": data.get("status_code"),
            "elapsed_ms": data.get("elapsed_ms", 0),
            "text": text,
            "json": json_obj,
        }
        self._run_tests_ui(ctx)
        self._run_extracts_ui(ctx)

    def _run_tests_ui(self, ctx: dict) -> None:
        tests = [t for t in self._collect_tests_from_ui() if t.get("enabled")]
        if not tests:
            self.test_result.setText('<span style="color:%s;">暂无启用断言。</span>' % THEME_COLORS[self._theme]["hint"])
            return
        passed = 0
        rows = []
        for t in tests:
            ok, desc = evaluate_assertion(t.get("type"), t.get("arg1"), t.get("arg2"), ctx)
            if ok:
                passed += 1
                rows.append('<span style="color:#3ecf8e;">✔ 通过</span>　' + desc)
            else:
                rows.append('<span style="color:#f05f5f;">✘ 失败</span>　' + desc)
        total = len(tests)
        color = "#3ecf8e" if passed == total else "#f0a45d"
        self.test_result.setText(
            "<b>断言汇总：<span style='color:%s;'>%d/%d 通过</span></b><br/>" % (color, passed, total) + "<br/>".join(rows)
        )

    def _run_extracts_ui(self, ctx: dict) -> None:
        items = [e for e in self._collect_extracts_from_ui() if str(e.get("key", "")).strip()]
        if not items:
            self.extract_result.setText("")
            return
        lines = []
        written = 0
        for e in items:
            ok, val = run_extract(e.get("type"), e.get("expr"), ctx.get("text", ""), ctx.get("json"))
            if ok:
                self._main.set_env_variable(str(e["key"]).strip(), str(val))
                written += 1
                lines.append(
                    '<span style="color:#3ecf8e;">✔ 已写入</span>　'
                    + str(e["key"]).strip()
                    + " = "
                    + str(val)[:60]
                )
            else:
                lines.append(
                    '<span style="color:#f05f5f;">✘ 提取失败</span>　'
                    + str(e["key"]).strip()
                    + "（"
                    + str(e.get("type"))
                    + ": "
                    + str(e.get("expr"))
                    + "）"
                )
        color = "#3ecf8e" if written == len(items) else "#f0a45d"
        self.extract_result.setText(
            "<b>变量提取：<span style='color:%s;'>%d/%d 成功</span></b><br/>" % (color, written, len(items)) + "<br/>".join(lines)
        )
        if written:
            self._main.status_msg(f"变量提取完成：{written} 个变量已写入当前环境", 6000)

    def snapshot(self) -> dict:
        return {
            "method": self.method_combo.currentText(),
            "url": self.url_edit.text(),
            "params": self.params_table.pairs(with_enabled=True),
            "headers": self.headers_table.pairs(with_enabled=True),
            "body_type": self.body_type.currentText(),
            "body_json": self.body_json.toPlainText(),
            "body_form": self.body_form.pairs(with_enabled=True),
            "body_urlenc": self.body_urlenc.pairs(with_enabled=True),
            "auth": self.auth_snapshot(),
            "tests": self._collect_tests_from_ui(),
            "extracts": self._collect_extracts_from_ui(),
        }

    def apply_request(self, req: dict) -> None:
        if not req:
            return
        self._suppress_dirty = True
        try:
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
            self.set_auth(req.get("auth"))
            self._load_tests_from_data(req.get("tests"))
            self._load_extracts_from_data(req.get("extracts"))
        finally:
            self._suppress_dirty = False
        self.is_dirty = False
        self._notify_label_change()

# --------------------------------------------------------------------------
# 主题样式表
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# 主窗口
# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.state = load_state()
        self._tabs = []
        self._theme = "dark"
        self._shortcuts = []
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(make_app_icon())
        self.resize(1320, 860)
        self.setMinimumSize(1024, 660)
        self._build_ui()
        self._load_settings()
        self._refresh_env_combo()
        self._rebuild_history()
        self._rebuild_collections()
        self._new_request_tab()
        self.status_msg("就绪。数据目录：" + DATA_DIR)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 4)
        root.setSpacing(6)

        # 全局选项行（环境 / 证书 / 重定向 / 超时）
        opts = QHBoxLayout()
        opts.setSpacing(6)
        opts.addWidget(QLabel("环境："))
        self.env_combo = QComboBox()
        self.env_combo.setFixedWidth(180)
        self.env_combo.currentIndexChanged.connect(self._on_env_changed)
        opts.addWidget(self.env_combo)
        b_env = QPushButton("管理环境")
        b_env.clicked.connect(self.manage_envs)
        opts.addWidget(b_env)
        opts.addSpacing(10)
        self.verify_chk = QCheckBox("验证 SSL 证书")
        self.verify_chk.setChecked(False)
        opts.addWidget(self.verify_chk)
        self.redirect_chk = QCheckBox("跟随重定向")
        self.redirect_chk.setChecked(True)
        opts.addWidget(self.redirect_chk)
        opts.addWidget(QLabel("超时(秒)："))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 600)
        self.timeout_spin.setValue(30)
        opts.addWidget(self.timeout_spin)
        self.var_hint = QLabel("")
        self.var_hint.setStyleSheet(self._hint_style())
        opts.addWidget(self.var_hint, 1)
        root.addLayout(opts)

        # 标签工具条
        tb = QHBoxLayout()
        tb.setSpacing(6)
        b_new = QPushButton("＋ 新建请求")
        b_new.clicked.connect(lambda: self._new_request_tab())
        b_new.setFixedHeight(28)
        tb.addWidget(b_new)
        b_close = QPushButton("× 关闭当前标签")
        b_close.clicked.connect(self._close_current_tab)
        b_close.setFixedHeight(28)
        tb.addWidget(b_close)
        tb.addSpacing(12)
        tb.addWidget(QLabel("主题："))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色", "浅色"])
        self.theme_combo.setFixedWidth(96)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        tb.addWidget(self.theme_combo)
        tb.addStretch(1)
        root.addLayout(tb)

        # 主分栏：左侧历史/集合，右侧请求标签
        main_split = QSplitter(Qt.Horizontal)
        root.addWidget(main_split, 1)

        left = QTabWidget()
        hist_wrap = QWidget()
        hv = QVBoxLayout(hist_wrap)
        hv.setContentsMargins(6, 6, 6, 6)
        hv.setSpacing(6)
        self.hist_filter = QLineEdit()
        self.hist_filter.setPlaceholderText("搜索 URL 关键字…")
        self.hist_filter.textChanged.connect(self._rebuild_history)
        hv.addWidget(self.hist_filter)
        frow = QHBoxLayout()
        self.hist_method = QComboBox()
        self.hist_method.addItem("全部方法", None)
        for m in METHODS:
            self.hist_method.addItem(m, m)
        self.hist_method.currentIndexChanged.connect(self._rebuild_history)
        self.hist_status = QComboBox()
        self.hist_status.addItem("全部状态", None)
        for s in ("2xx", "3xx", "4xx", "5xx"):
            self.hist_status.addItem(s, s)
        self.hist_status.addItem("失败(ERR)", "ERR")
        self.hist_status.currentIndexChanged.connect(self._rebuild_history)
        frow.addWidget(self.hist_method, 1)
        frow.addWidget(self.hist_status, 1)
        hv.addLayout(frow)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._load_history_item)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._history_menu)
        hv.addWidget(self.history_list, 1)
        left.addTab(hist_wrap, "历史记录")

        coll_wrap = QWidget()
        cv = QVBoxLayout(coll_wrap)
        cv.setContentsMargins(6, 6, 6, 6)
        self.coll_tree = QTreeWidget()
        self.coll_tree.setHeaderHidden(True)
        self.coll_tree.itemDoubleClicked.connect(self._load_collection_item)
        self.coll_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.coll_tree.customContextMenuRequested.connect(self._collection_menu)
        coll_bar = QHBoxLayout()
        b_imp = QPushButton("导入 Postman")
        b_imp.clicked.connect(self.import_postman)
        b_exp = QPushButton("导出 Postman")
        b_exp.clicked.connect(self.export_postman)
        b_sel = QPushButton("导出选中请求")
        b_sel.clicked.connect(self.export_postman_request)
        b_run = QPushButton("运行集合")
        b_run.setObjectName("primary")
        b_run.clicked.connect(self.run_collection)
        self.run_coll_btn = b_run
        coll_bar.addWidget(b_imp)
        coll_bar.addWidget(b_exp)
        coll_bar.addWidget(b_sel)
        coll_bar.addWidget(b_run)
        cv.addLayout(coll_bar)
        cv.addWidget(self.coll_tree, 1)
        left.addTab(coll_wrap, "集合")

        self.request_tabs = QTabWidget()
        self.request_tabs.setTabsClosable(True)
        self.request_tabs.tabCloseRequested.connect(self._close_request_tab)
        main_split.addWidget(left)
        main_split.addWidget(self.request_tabs)
        main_split.setSizes([300, 1020])

        for seq, slot in (
            ("Ctrl+Return", self._send_current),
            ("Ctrl+Enter", self._send_current),
            ("Ctrl+S", lambda: self.save_to_collection(self.current_tab())),
        ):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(slot)
            self._shortcuts.append(sc)

        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪")

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------
    def current_theme(self) -> str:
        return self._theme

    def _hint_style(self) -> str:
        return f"color:{THEME_COLORS[self._theme]['hint']};"

    def _on_theme_changed(self, index: int) -> None:
        name = "dark" if index == 0 else "light"
        self._apply_theme(name)
        s = self._settings()
        s["theme"] = name
        self._persist()
        self.status_msg("主题已切换为：" + ("深色" if name == "dark" else "浅色"))

    def _apply_theme(self, name: str) -> None:
        self._theme = name if name in THEMES else "dark"
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(THEMES[self._theme])
        for tab in self._tabs:
            tab.set_theme(self._theme)
        self._update_var_hint()

    # ------------------------------------------------------------------
    # 请求标签页管理
    # ------------------------------------------------------------------
    def current_tab(self) -> "RequestTab | None":
        return self.request_tabs.currentWidget()

    def _send_current(self) -> None:
        tab = self.current_tab()
        if tab is not None:
            tab.send_request()

    def _new_request_tab(self, initial: dict = None) -> "RequestTab":
        tab = RequestTab(self, initial)
        self._tabs.append(tab)
        idx = self.request_tabs.addTab(tab, "新请求")
        self.request_tabs.setCurrentIndex(idx)
        self._update_tab_label(tab)
        return tab

    def _update_tab_label(self, tab: "RequestTab") -> None:
        idx = self.request_tabs.indexOf(tab)
        if idx < 0:
            return
        m = tab.method_combo.currentText()
        u = tab.url_edit.text().strip()
        label = m + " " + (u.split("?")[0][:42] if u else "新请求")
        self.request_tabs.setTabText(idx, label)

    def _close_request_tab(self, index: int) -> None:
        tab = self.request_tabs.widget(index)
        if tab is None:
            return
        if tab.worker is not None and tab.worker.isRunning():
            QMessageBox.information(self, "提示", "该标签请求正在进行中，请等待完成后再关闭。")
            return
        if tab.is_dirty:
            if (
                QMessageBox.question(
                    self, "关闭确认", "该请求尚未保存到集合，关闭将丢失当前编辑内容。是否继续关闭？"
                )
                != QMessageBox.Yes
            ):
                return
        self._tabs.remove(tab)
        self.request_tabs.removeTab(index)
        tab.deleteLater()
        if self.request_tabs.count() == 0:
            self._new_request_tab()

    def _close_current_tab(self) -> None:
        self._close_request_tab(self.request_tabs.currentIndex())

    # ------------------------------------------------------------------
    # 设置持久化
    # ------------------------------------------------------------------
    def _settings(self) -> dict:
        return self.state.setdefault("settings", {})

    def _load_settings(self) -> None:
        s = self._settings()
        self.timeout_spin.setValue(int(s.get("timeout", 30)))
        self.verify_chk.setChecked(not bool(s.get("verify", True)))
        self.redirect_chk.setChecked(bool(s.get("follow_redirects", True)))
        theme = s.get("theme", "dark")
        self._theme = theme if theme in THEMES else "dark"
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(0 if self._theme == "dark" else 1)
        self.theme_combo.blockSignals(False)
        self._apply_theme(self._theme)

    def _save_settings(self) -> None:
        s = self._settings()
        s["timeout"] = self.timeout_spin.value()
        s["verify"] = not self.verify_chk.isChecked()
        s["follow_redirects"] = self.redirect_chk.isChecked()
        s["theme"] = self._theme

    def _persist(self) -> None:
        save_state(self.state)

    def status_msg(self, text: str, timeout: int = 5000) -> None:
        self.statusBar().showMessage(text, timeout)

    # ------------------------------------------------------------------
    # 环境
    # ------------------------------------------------------------------
    def _refresh_env_combo(self) -> None:
        self.env_combo.blockSignals(True)
        self.env_combo.clear()
        active = self.state.get("active_env", "")
        for e in self.state.get("environments", []):
            self.env_combo.addItem(e.get("name", ""))
        if active:
            idx = self.env_combo.findText(active)
            if idx >= 0:
                self.env_combo.setCurrentIndex(idx)
        self.env_combo.blockSignals(False)
        self._on_env_changed()

    def _on_env_changed(self, *_args) -> None:
        self.state["active_env"] = self.env_combo.currentText()
        self._update_var_hint()
        for tab in self._tabs:
            tab.refresh_auth_preview()
        self._persist()

    def _update_var_hint(self) -> None:
        env = self._current_env()
        if env:
            vars_ = [v for v in env.get("variables", []) if v.get("enabled", True)]
            self.var_hint.setText(f"当前环境：{env.get('name')}（{len(vars_)} 个变量）")
            self.var_hint.setStyleSheet(self._hint_style())
        else:
            self.var_hint.setText("")

    def _current_env(self):
        for e in self.state.get("environments", []):
            if e.get("name") == self.env_combo.currentText():
                return e
        return None

    def variables(self) -> dict:
        env = self._current_env()
        out = {}
        if env:
            for v in env.get("variables", []):
                if v.get("enabled", True):
                    out[v.get("key", "")] = v.get("value", "")
        return out

    def manage_envs(self) -> None:
        dlg = EnvDialog(self.state.get("environments", []), self)
        if dlg.exec() != QDialog.Accepted:
            return
        self.state["environments"] = dlg.result_data()
        self._refresh_env_combo()
        self._persist()

    # ------------------------------------------------------------------
    # 历史记录
    # ------------------------------------------------------------------
    def _add_history(self, req: dict, status=None, error=None) -> None:
        entry = {
            "method": req.get("method", "GET"),
            "url": req.get("url", ""),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "error": error,
            "request": req,
        }
        hist = self.state.setdefault("history", [])
        hist.insert(0, entry)
        del hist[300:]
        save_state(self.state)
        self._rebuild_history()

    def _rebuild_history(self) -> None:
        self.history_list.clear()
        kw = self.hist_filter.text().strip().lower()
        meth = self.hist_method.currentData()
        st = self.hist_status.currentData()
        for idx, h in enumerate(self.state.get("history", [])):
            url = (h.get("url") or "").lower()
            if kw and kw not in url:
                continue
            if meth and h.get("method") != meth:
                continue
            s = h.get("status")
            err = h.get("error")
            if st == "ERR":
                if not (err and s is None):
                    continue
            elif st:
                if s is None or str(s)[0] != st[0]:
                    continue
            tag = f"{s}" if s else ("ERR" if err else "-")
            auth_tag = auth_tag_of(h.get("request"))
            suffix = f"　〔{auth_tag}〕" if auth_tag else ""
            item = QListWidgetItem(f"[{h.get('method')}] {tag}  {h.get('url', '')}{suffix}")
            item.setToolTip(
                f"时间：{h.get('time')}\n方法：{h.get('method')}\n地址：{h.get('url')}\n状态：{tag}"
            )
            if auth_tag:
                item.setToolTip(item.toolTip() + "　认证：" + auth_tag)
            item.setData(Qt.UserRole, idx)
            self.history_list.addItem(item)

    def _load_history_item(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        hist = self.state.get("history", [])
        if not (0 <= idx < len(hist)):
            return
        tab = self.current_tab()
        if tab is None:
            tab = self._new_request_tab()
        tab.apply_request(hist[idx].get("request", {}))
        self.status_msg("已载入历史请求")

    def _open_history_new_tab(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        hist = self.state.get("history", [])
        if not (0 <= idx < len(hist)):
            return
        tab = self._new_request_tab(hist[idx].get("request", {}))
        self.request_tabs.setCurrentWidget(tab)
        self.status_msg("已在新标签中打开历史请求")

    def _history_menu(self, pos) -> None:
        item = self.history_list.itemAt(pos)
        menu = QMenu(self)
        act_open = menu.addAction("载入到当前标签") if item else None
        act_new = menu.addAction("在新标签中打开") if item else None
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
        elif act_new and chosen == act_new:
            self._open_history_new_tab(item)
        elif act_resend and chosen == act_resend:
            self._load_history_item(item)
            self._send_current()
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
                    a_tag = auth_tag_of(r)
                    item.setToolTip(
                        0,
                        f"{r.get('method', 'GET')} {r.get('url', '')}"
                        + (f"　认证：{a_tag}" if a_tag else ""),
                    )
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

    def save_to_collection(self, tab=None) -> None:
        tab = tab or self.current_tab()
        if tab is None:
            return
        url = tab.url_edit.text().strip()
        if not url:
            QMessageBox.information(self, "提示", "请先输入请求地址。")
            return
        default_name = f"{tab.method_combo.currentText()} {url.split('?')[0].rstrip('/').split('/')[-1] or 'request'}"
        name, ok = self._ask_text("保存到集合", "请求名称：", default_name)
        if not ok or not name.strip():
            return
        sel = self._selected_node()
        node = {
            "id": self._new_id(),
            "type": "request",
            "name": name.strip(),
            "request": tab.snapshot(),
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
        tab.is_dirty = False
        self.status_msg(f"已保存到集合：{name.strip()}")

    def _load_collection_item(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        node = self._find_node(item.data(0, Qt.UserRole))
        if not node:
            return
        if node.get("type") == "folder":
            item.setExpanded(not item.isExpanded())
            return
        tab = self.current_tab()
        if tab is None:
            tab = self._new_request_tab()
        tab.apply_request(node.get("request", {}))
        self.status_msg("已载入集合请求：" + node.get("name", ""))

    def _collection_menu(self, pos) -> None:
        item = self.coll_tree.itemAt(pos)
        found = self._find_node(item.data(0, Qt.UserRole)) if item else None
        sel_node = found[0] if found else None
        parent_list = found[1] if found else None

        menu = QMenu(self)
        act_load = menu.addAction("载入到当前标签") if (sel_node and sel_node.get("type") == "request") else None
        act_new = menu.addAction("在新标签中打开") if (sel_node and sel_node.get("type") == "request") else None
        act_save = menu.addAction("保存当前请求到此处")
        act_folder = menu.addAction("新建子文件夹")
        act_ren = menu.addAction("重命名") if sel_node else None
        act_del = menu.addAction("删除") if sel_node else None
        chosen = menu.exec(self.coll_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if act_load is not None and chosen == act_load:
            tab = self.current_tab()
            if tab is None:
                tab = self._new_request_tab()
            tab.apply_request(sel_node.get("request", {}))
        elif act_new is not None and chosen == act_new:
            tab = self._new_request_tab(sel_node.get("request", {}))
            self.request_tabs.setCurrentWidget(tab)
            self.status_msg("已在新标签中打开：" + sel_node.get("name", ""))
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

    def run_collection(self) -> None:
        requests_list = self._collect_request_nodes(self.state.get("collections", []))
        if not requests_list:
            QMessageBox.information(self, "运行集合", "集合中没有可运行的请求。请先在集合中保存请求。")
            return
        dlg = CollectionRunnerDialog(requests_list, self, self)
        dlg.exec()

    @staticmethod
    def _collect_request_nodes(nodes) -> list:
        out = []
        for n in nodes or []:
            if n.get("type") == "request":
                out.append(n)
            else:
                out.extend(MainWindow._collect_request_nodes(n.get("children", [])))
        return out

    # ------------------------------------------------------------------
    # Postman 导入 / 导出
    # ------------------------------------------------------------------
    def import_postman(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 Postman 集合", "", "Postman Collection (*.json);;JSON (*.json);;所有文件 (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "导入失败", str(e))
            return
        nodes, errors = parse_postman_collection(text)
        if nodes is None:
            QMessageBox.warning(self, "导入失败", "\n".join(errors))
            return
        colls = self.state.setdefault("collections", [])
        name = nodes[0].get("name", "导入的集合")
        existing = [c for c in colls if c.get("name") == name]
        if existing:
            existing[0]["children"] = nodes[0].get("children", [])
        else:
            colls.append(nodes[0])
        save_state(self.state)
        self._rebuild_collections()
        count = _count_requests(nodes[0])
        msg = f"导入成功：{name}（{count} 个请求）"
        if errors:
            msg += "；部分字段未能完整映射"
        self.status_msg(msg, 8000)

    def _export_postman_to_file(self, nodes, default_name) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Postman 集合", os.path.join(app_dir(), default_name), "Postman Collection (*.json);;JSON (*.json)"
        )
        if not path:
            return
        data = build_postman_collection(nodes, default_name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status_msg("已导出到 " + path, 8000)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "导出失败", str(e))

    def export_postman(self) -> None:
        sel = self._selected_node()
        if sel:
            target = sel[0]
        else:
            target = None
        if target is not None and target.get("type") == "folder":
            nodes = [target]
            default_name = target.get("name", "集合")
        else:
            nodes = self.state.get("collections", [])
            default_name = "HttpLite 集合"
        if not nodes:
            QMessageBox.information(self, "提示", "集合为空，暂无可导出的内容。")
            return
        self._export_postman_to_file(nodes, default_name)

    def export_postman_request(self) -> None:
        sel = self._selected_node()
        if not sel or sel[0].get("type") != "request":
            QMessageBox.information(self, "提示", "请先在集合中选中一个请求节点。")
            return
        self._export_postman_to_file([sel[0]], sel[0].get("name", "请求"))

    def set_env_variable(self, key: str, value: str) -> None:
        """把提取到的值写入当前环境变量（存在则更新，不存在则追加）。"""
        env = self._current_env()
        if env is None:
            return
        vars_ = env.setdefault("variables", [])
        found = False
        for v in vars_:
            if v.get("key") == key:
                v["value"] = value
                v["enabled"] = True
                found = True
                break
        if not found:
            vars_.append({"key": key, "value": value, "enabled": True})
        self._update_var_hint()
        self._persist()

    def _ask_text(self, title, label, text):
        return QInputDialog.getText(self, title, label, text=text)

    def _new_id(self) -> str:
        return f"n{int(time.time() * 1000)}{os.urandom(2).hex()}"

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        self._save_settings()
        save_state(self.state)
        for tab in self._tabs:
            if tab.worker is not None and tab.worker.isRunning():
                tab.worker.wait(2000)
        super().closeEvent(event)


# --------------------------------------------------------------------------
def run_self_test() -> None:
    """`HttpLite.exe --self-test`：在打包环境中验证 HTTP/SSL/JSON/认证与 UI 能力并写出结果文件。"""
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
    auth_ok = True
    try:
        probe = {
            "method": "GET",
            "url": "https://iam.amazonaws.com/?Action=ListUsers&Version=2010-05-08",
            "headers": {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
            "params": [],
            "data": None,
            "files": None,
            "json": None,
            "requests_auth": None,
        }
        signed, err = aws_sign_v4(
            probe,
            {
                "access_key": "AKIDEXAMPLE",
                "secret_key": "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
                "session_token": "",
                "region": "us-east-1",
                "service": "iam",
            },
            {},
            amz_date="20150830T123600Z",
        )
        good = signed is not None and (
            "5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7"
            in signed.get("Authorization", "")
        )
        auth_ok = auth_ok and good
        lines.append("aws sigv4 vector: " + ("ok" if good else "FAIL " + str(err or signed)))
    except Exception as e:  # noqa: BLE001
        auth_ok = False
        lines.append("aws sigv4 error: " + repr(e))
    try:
        token, err = make_jwt(
            "HS256",
            "your-256-bit-secret",
            '{"sub":"1234567890","name":"John Doe","iat":1516239022}',
        )
        expect = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        good = token == expect
        auth_ok = auth_ok and good
        lines.append("jwt hs256 vector: " + ("ok" if good else "FAIL " + str(token or err)))
    except Exception as e:  # noqa: BLE001
        auth_ok = False
        lines.append("jwt error: " + repr(e))
    try:
        p2 = {
            "method": "GET",
            "url": "https://example.com/",
            "headers": {},
            "params": [],
            "data": None,
            "files": None,
            "json": None,
            "requests_auth": None,
        }
        apply_auth(p2, bearer_auth("abc"), {})
        apply_auth(p2, {"type": "apikey", "apikey": {"key": "k", "value": "v", "in": "query"}}, {})
        good = p2["headers"].get("Authorization") == "Bearer abc" and ("k", "v") in p2["params"]
        auth_ok = auth_ok and good
        lines.append("auth inject ok: " + str(good))
    except Exception as e:  # noqa: BLE001
        auth_ok = False
        lines.append("auth inject error: " + repr(e))
    ok = ok and auth_ok

    # Postman 导入 / 导出 round-trip（纯逻辑）
    try:
        sample = {
            "info": {"name": "Demo", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
            "item": [
                {
                    "name": "Get User",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "https://httpbin.org/get?a=1",
                            "host": ["https://httpbin.org"],
                            "path": ["get"],
                            "query": [{"key": "a", "value": "1"}],
                        },
                        "header": [{"key": "X-Token", "value": "abc"}],
                        "body": {"mode": "raw", "raw": ""},
                        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "tok123", "type": "string"}]},
                    },
                },
                {
                    "name": "Sub",
                    "item": [
                        {
                            "name": "Post JSON",
                            "request": {
                                "method": "POST",
                                "url": "https://httpbin.org/post",
                                "header": [],
                                "body": {"mode": "raw", "raw": '{"k":1}', "options": {"raw": {"language": "json"}}},
                                "auth": {"type": "noauth"},
                            },
                        }
                    ],
                },
            ],
        }
        nodes, perr = parse_postman_collection(json.dumps(sample, ensure_ascii=False))
        pm_ok = nodes is not None and len(nodes) == 1 and len(nodes[0]["children"]) == 2
        pm_ok = pm_ok and nodes[0]["children"][1]["children"][0]["request"]["body_type"] == "JSON"
        pm_ok = pm_ok and nodes[0]["children"][0]["request"]["auth"]["type"] == "bearer"
        pm_ok = pm_ok and nodes[0]["children"][0]["request"]["params"] == [
            {"key": "a", "value": "1", "enabled": True}
        ]
        exported = build_postman_collection(nodes, "Demo")
        raw_ok = exported["item"][0]["item"][0]["request"]["url"]["raw"].endswith("?a=1")
        nodes2, _ = parse_postman_collection(json.dumps(exported, ensure_ascii=False))
        pm_ok = pm_ok and raw_ok and nodes2 is not None and nodes2[0]["children"][0]["request"]["params"] == [
            {"key": "a", "value": "1", "enabled": True}
        ]
        lines.append("postman import/export: " + ("ok" if pm_ok else "FAIL " + ";".join(perr or [])))
        ok = ok and pm_ok
    except Exception as e:  # noqa: BLE001
        ok = False
        lines.append("postman error: " + repr(e))

    # 断言与变量提取纯逻辑
    try:
        ctx = {
            "status": 200,
            "elapsed_ms": 350,
            "text": '{"data":{"name":"HttpLite","tags":["a","b"]}}',
            "json": {"data": {"name": "HttpLite", "tags": ["a", "b"]}},
        }
        r1, _ = evaluate_assertion("status_eq", "200", "", ctx)
        r2, _ = evaluate_assertion("status_range", "2xx", "", ctx)
        r3, _ = evaluate_assertion("time_lt", "500", "", ctx)
        r4, _ = evaluate_assertion("body_contains", "HttpLite", "", ctx)
        r5, _ = evaluate_assertion("json_exists", "$.data.name", "", ctx)
        r6, _ = evaluate_assertion("json_eq", "$.data.tags[0]", "a", ctx)
        r7, _ = evaluate_assertion("status_eq", "404", "", ctx)
        ast_ok = r1 and r2 and r3 and r4 and r5 and r6 and (not r7)
        ev1, v1 = run_extract("jsonpath", "$.data.name", ctx["text"], ctx["json"])
        ev2, v2 = run_extract("regex", r'"name":\s*"([^"]+)"', ctx["text"], ctx["json"])
        ext_ok = ev1 and v1 == "HttpLite" and ev2 and v2 == "HttpLite"
        lines.append("assert runner: " + ("ok" if ast_ok else "FAIL"))
        lines.append("extract runner: " + ("ok" if ext_ok else "FAIL"))
        ok = ok and ast_ok and ext_ok
    except Exception as e:  # noqa: BLE001
        ok = False
        lines.append("assert/extract error: " + repr(e))

    # OAuth 2.0 纯逻辑（不触发网络）
    try:
        ou = oauth2_build_authorize_url(
            {
                "authorize_url": "https://auth.example.com/authorize",
                "client_id": "cid123",
                "redirect_uri": "http://localhost:8080/cb",
                "scope": "read write",
                "extra": "",
                "access_token": "",
            },
            {},
        )
        ou_ok = ou is not None and "client_id=cid123" in ou and "response_type=code" in ou
        ec1 = oauth2_extract_code("https://localhost/cb?code=ABC123&state=x")
        ec2 = oauth2_extract_code("https://localhost/cb?state=x")
        ec_ok = ec1 == "ABC123" and ec2 == ""
        _tok, rerr = oauth2_refresh_token({"refresh_token": ""}, {})
        ref_ok = rerr is not None and "refresh_token" in rerr
        oauth_ok = ou_ok and ec_ok and ref_ok
        lines.append("oauth2 authorize url: " + ("ok" if ou_ok else "FAIL " + str(ou)))
        lines.append("oauth2 extract code: " + ("ok" if ec_ok else "FAIL"))
        lines.append("oauth2 refresh guard: " + ("ok" if ref_ok else "FAIL"))
        ok = ok and oauth_ok
    except Exception as e:  # noqa: BLE001
        ok = False
        lines.append("oauth2 error: " + repr(e))

    # 代码生成纯逻辑
    try:
        gen_req = {
            "method": "POST",
            "url": "https://api.example.com/login?env=prod",
            "params": [{"key": "debug", "value": "1", "enabled": True}],
            "headers": [{"key": "X-Token", "value": "abc", "enabled": True}],
            "body_type": "JSON",
            "body_json": '{"user":"alice","pwd":"123"}',
            "body_form": [],
            "body_urlenc": [],
            "auth": bearer_auth("tok123"),
        }
        snips = generate_code_snippets(gen_req, {})
        curl_s = snips["curl"]
        py_s = snips["python"]
        js_s = snips["javascript"]
        cg_ok = (
            "curl" in snips
            and "-X POST" in curl_s
            and "Bearer tok123" in curl_s
            and "--data-raw" in curl_s
            and "requests.request" in py_s
            and "'user': 'alice'" in py_s
            and "fetch(" in js_s
            and "Bearer tok123" in js_s
            and "debug=1" in curl_s
        )
        lines.append("codegen curl/python/js: " + ("ok" if cg_ok else "FAIL"))
        ok = ok and cg_ok
    except Exception as e:  # noqa: BLE001
        ok = False
        lines.append("codegen error: " + repr(e))

    # 集合运行器纯逻辑（payload 构建 + 断言统计）
    try:
        snap = {
            "method": "GET",
            "url": "{{base}}/ping",
            "params": [{"key": "x", "value": "{{v}}", "enabled": True}],
            "headers": [],
            "body_type": "none",
            "body_json": "",
            "body_form": [],
            "body_urlenc": [],
            "auth": bearer_auth("tok99"),
        }
        pl = build_payload_from_snapshot(snap, {"base": "https://httpbin.org", "v": "42"}, 30, True, True)
        runner_ok = pl["url"] == "https://httpbin.org/ping" and pl["params"] == [("x", "42")]
        runner_ok = runner_ok and pl["headers"].get("Authorization") == "Bearer tok99"
        passed, total_n, _det = run_assertions_on_ctx(
            [{"atype": "status_eq", "arg1": "200", "arg2": ""}, {"atype": "json_exists", "arg1": "$.ok", "arg2": ""}],
            {"status": 200, "elapsed_ms": 100, "text": '{"ok":true}', "json": {"ok": True}},
        )
        runner_ok = runner_ok and passed == 2 and total_n == 2
        passed2, total2, _d = run_assertions_on_ctx(
            [{"atype": "status_eq", "arg1": "404", "arg2": ""}],
            {"status": 200, "elapsed_ms": 100, "text": "", "json": None},
        )
        runner_ok = runner_ok and passed2 == 0 and total2 == 1
        lines.append("collection runner logic: " + ("ok" if runner_ok else "FAIL"))
        ok = ok and runner_ok
    except Exception as e:  # noqa: BLE001
        ok = False
        lines.append("collection runner error: " + repr(e))

    # UI 冒烟：多标签 / 主题 / 历史过滤（离屏）
    try:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        qapp = QApplication(sys.argv)
        qapp.setStyleSheet(THEMES["dark"])
        win = MainWindow()
        base = win.request_tabs.count()
        win._new_request_tab()
        win._new_request_tab()
        added = win.request_tabs.count()
        win._close_request_tab(win.request_tabs.count() - 1)
        closed = win.request_tabs.count()
        win._apply_theme("light")
        theme_ok = win._theme == "light" and bool(QApplication.instance().styleSheet())
        win._add_history(
            {"method": "GET", "url": "https://www.baidu.com", "params": [], "headers": [],
             "body_type": "none", "body_json": "", "body_form": [], "body_urlenc": [], "auth": default_auth()},
            status=200,
        )
        win.hist_filter.setText("baidu")
        flt_kw = win.history_list.count()
        win.hist_filter.setText("")
        win.hist_status.setCurrentIndex(1)  # 2xx
        flt_st = win.history_list.count()
        win._apply_theme("dark")
        tab0 = win.current_tab()
        tab0._add_assertion_row("status_eq", "200", "")
        tab0._add_assertion_row("json_exists", "$.a", "")
        tab0._add_extract_row("smoke_var", "jsonpath", "$.a.b")
        win.set_env_variable("smoke_extract", "hello")
        cur_env = win._current_env() or {}
        smoke_env = any(
            v.get("key") == "smoke_extract" and v.get("value") == "hello"
            for v in cur_env.get("variables", [])
        )
        smoke_tests = tab0.tests_table.rowCount() == 2 and tab0.extract_table.rowCount() == 1
        lines.append(f"ui tests tab: rows={tab0.tests_table.rowCount()}/{tab0.extract_table.rowCount()} env_extract={smoke_env}")
        ok = ok and smoke_env and smoke_tests
        # OAuth 2.0 面板注册 + 代码生成按钮 + 集合运行按钮
        oauth_panel = (
            tab0.auth_type.count() == 8
            and tab0.auth_stack.count() == 8
            and "OAuth 2.0" in [tab0.auth_type.itemText(i) for i in range(tab0.auth_type.count())]
        )
        code_btn_ok = hasattr(tab0, "code_btn") and tab0.code_btn.text() == "生成代码"
        run_btn_ok = hasattr(win, "run_coll_btn") and win.run_coll_btn.text() == "运行集合"
        oauth_preview = ""
        try:
            oauth_preview = tab0.auth_preview.text()
        except Exception:
            pass
        lines.append(f"ui oauth panel: pages={tab0.auth_stack.count()} types={tab0.auth_type.count()} oauth={oauth_panel}")
        lines.append(f"ui codegen btn: {code_btn_ok}")
        lines.append(f"ui run-coll btn: {run_btn_ok}")
        ok = ok and oauth_panel and code_btn_ok and run_btn_ok
        win.close()
        good_ui = (
            added == base + 2
            and closed == added - 1
            and theme_ok
            and flt_kw >= 1
            and flt_st >= 1
        )
        ok = ok and good_ui
        lines.append(f"ui multi-tab: base={base} add={added} close={closed}")
        lines.append(f"theme light qss: {'ok' if theme_ok else 'FAIL'}")
        lines.append(f"history filter: kw_baidu={flt_kw} status_2xx={flt_st}")
    except Exception as e:  # noqa: BLE001
        ok = False
        lines.append("ui smoke error: " + repr(e))

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


def run_ui_shot(out_dir: str, theme_name: str = None) -> None:
    """`HttpLite.exe --ui-shot <目录> [dark|light]`：离屏渲染界面并截图（浅色 / 深色两套）。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    lines = []
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        lines.append("mkdir error: " + repr(e))
    try:
        qapp = QApplication(sys.argv)
        themes = [theme_name] if theme_name else ["dark", "light"]
        for theme in themes:
            qapp.setStyleSheet(THEMES[theme])
            win = MainWindow()
            win._apply_theme(theme)
            win.resize(1240, 800)
            win.show()
            qapp.processEvents()
            tab = win._tabs[0]
            # 演示多标签：新增一个带内容的标签
            win._new_request_tab(
                {
                    "method": "GET",
                    "url": "https://httpbin.org/get?from=multi",
                    "params": [{"key": "from", "value": "multi", "enabled": True}],
                    "headers": [],
                    "body_type": "none",
                    "body_json": "",
                    "body_form": [],
                    "body_urlenc": [],
                    "auth": default_auth(),
                }
            )
            tabs_found = any(
                "Authorization" in [t.req_tabs.tabText(i) for i in range(t.req_tabs.count())]
                for t in win._tabs
            )
            lines.append(f"[{theme}] auth pages: {win._tabs[0].auth_stack.count()}")
            lines.append(
                f"[{theme}] auth types: {' / '.join(win._tabs[0].auth_type.itemText(i) for i in range(win._tabs[0].auth_type.count()))}"
            )
            lines.append(f"[{theme}] auth tab found: {tabs_found}")
            win.request_tabs.setCurrentIndex(0)
            tab.url_edit.setText("https://api.example.com/v1/orders")
            tab.method_combo.setCurrentText("POST")
            qapp.processEvents()
            shots = [
                ("auth_bearer.png", bearer_auth("eyJhbGciOiJIUzI1NiJ9.demo.token")),
                ("auth_basic.png", merge_auth({"type": "basic", "basic": {"username": "demo", "password": "s3cret"}})),
                (
                    "auth_apikey.png",
                    merge_auth(
                        {"type": "apikey", "apikey": {"key": "X-API-Key", "value": "sk-live-123", "in": "query"}}
                    ),
                ),
                (
                    "auth_aws.png",
                    merge_auth(
                        {
                            "type": "awsv4",
                            "awsv4": {
                                "access_key": "AKIAIOSFODNN7EXAMPLE",
                                "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                                "session_token": "",
                                "region": "us-east-1",
                                "service": "execute-api",
                            },
                        }
                    ),
                ),
                (
                    "auth_jwt.png",
                    merge_auth(
                        {
                            "type": "jwt",
                            "jwt": {
                                "algorithm": "HS256",
                                "secret": "topsecret",
                                "payload": '{\n    "sub": "1234567890",\n    "name": "HttpLite"\n}',
                                "location": "header",
                                "header_name": "Authorization",
                                "prefix": "Bearer ",
                            },
                        }
                    ),
                ),
                (
                    "auth_oauth2.png",
                    merge_auth(
                        {
                            "type": "oauth2",
                            "oauth2": {
                                "grant_type": "client_credentials",
                                "token_url": "https://auth.example.com/oauth/token",
                                "client_id": "demo-client",
                                "client_secret": "demo-secret",
                                "username": "",
                                "password": "",
                                "scope": "read write",
                                "extra": "",
                                "authorize_url": "https://auth.example.com/authorize",
                                "redirect_uri": "http://localhost:8080/cb",
                                "authorization_code": "",
                                "access_token": "tk-cached-12345",
                                "refresh_token": "rt-cached-67890",
                                "token_type": "Bearer",
                                "auto_refresh": True,
                                "expires_at": 0,
                            },
                        }
                    ),
                ),
            ]
            for name, cfg in shots:
                tab.set_auth(cfg)
                qapp.processEvents()
                saved = win.grab().save(os.path.join(out_dir, f"{theme}_{name}"))
                lines.append(
                    f"[{theme}] {name} saved={saved} type={tab.auth_type.currentText()} panel={tab.auth_stack.currentIndex()}"
                )
            lines.append(f"[{theme}] preview: {tab.auth_preview.text()[:160]}")
            # 多标签视图
            win.request_tabs.setCurrentIndex(1)
            qapp.processEvents()
            saved = win.grab().save(os.path.join(out_dir, f"{theme}_multi_tab.png"))
            lines.append(f"[{theme}] multi_tab saved={saved} tabs={win.request_tabs.count()}")
            # 历史搜索过滤视图
            win.hist_filter.setText("httpbin")
            win.request_tabs.setCurrentIndex(0)
            qapp.processEvents()
            saved = win.grab().save(os.path.join(out_dir, f"{theme}_history_filter.png"))
            lines.append(f"[{theme}] history_filter saved={saved} items={win.history_list.count()}")
            # 测试 / 变量提取视图
            tab = win._tabs[0]
            tab.tests_table.setRowCount(0)
            tab.extract_table.setRowCount(0)
            tab._add_assertion_row("status_eq", "200", "")
            tab._add_assertion_row("status_range", "2xx", "")
            tab._add_assertion_row("time_lt", "800", "")
            tab._add_assertion_row("body_contains", "success", "")
            tab._add_assertion_row("json_exists", "$.data.token", "")
            tab._add_assertion_row("json_eq", "$.data.role", "admin")
            tab._add_extract_row("access_token", "jsonpath", "$.data.token")
            tab._add_extract_row("user_id", "regex", r'"id":\s*(\d+)')
            tab.last_response = {
                "status_code": 200,
                "reason": "OK",
                "elapsed_ms": 312,
                "size": 512,
                "text": '{"data":{"token":"tk-9f2a","id":42,"role":"admin"}}',
            }
            tab.resp_tabs.setCurrentIndex(2)
            tab._run_tests_and_extracts(tab.last_response)
            qapp.processEvents()
            saved = win.grab().save(os.path.join(out_dir, f"{theme}_tests.png"))
            lines.append(f"[{theme}] tests saved={saved} rows={tab.tests_table.rowCount()}/{tab.extract_table.rowCount()}")
            # 代码生成对话框
            try:
                tab = win._tabs[0]
                tab.set_auth(bearer_auth("tk-shot-abc"))
                tab.method_combo.setCurrentText("POST")
                tab.url_edit.setText("https://api.example.com/v1/orders")
                req = tab.snapshot()
                snips = generate_code_snippets(req, win.variables())
                dlg = CodeGenDialog(snips, win)
                dlg.resize(700, 480)
                dlg.show()
                qapp.processEvents()
                saved = dlg.grab().save(os.path.join(out_dir, f"{theme}_codegen.png"))
                lines.append(f"[{theme}] codegen saved={saved} tabs={dlg.tabs.count()} first_len={len(snips['curl'])}")
                dlg.close()
            except Exception as e:  # noqa: BLE001
                lines.append(f"[{theme}] codegen error: {repr(e)}")
            # 集合运行器对话框（静态空集合冒烟，不触发网络）
            try:
                empty_req = {
                    "name": "Demo GET",
                    "method": "GET",
                    "url": "https://httpbin.org/get",
                    "params": [],
                    "headers": [],
                    "body_type": "none",
                    "body_json": "",
                    "body_form": [],
                    "body_urlenc": [],
                    "auth": default_auth(),
                    "tests": [{"atype": "status_eq", "arg1": "200", "arg2": ""}],
                }
                runner_dlg = CollectionRunnerDialog([empty_req], win, win)
                runner_dlg.resize(980, 460)
                runner_dlg.show()
                qapp.processEvents()
                saved = runner_dlg.grab().save(os.path.join(out_dir, f"{theme}_runner.png"))
                lines.append(f"[{theme}] runner saved={saved} cols={runner_dlg.table.columnCount()} rows={runner_dlg.table.rowCount()}")
                runner_dlg.close()
                if runner_dlg._runner is not None and runner_dlg._runner.isRunning():
                    runner_dlg._runner.stop()
                    runner_dlg._runner.wait(6000)
            except Exception as e:  # noqa: BLE001
                lines.append(f"[{theme}] runner error: {repr(e)}")
            win.close()
    except Exception as e:  # noqa: BLE001
        lines.append("ui-shot error: " + repr(e))
    try:
        with open(os.path.join(out_dir, "HttpLite_uishot.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass
    sys.exit(0)


def main() -> None:
    if "--self-test" in sys.argv:
        run_self_test()
        return
    if "--ui-shot" in sys.argv:
        pos = sys.argv.index("--ui-shot")
        target = sys.argv[pos + 1] if len(sys.argv) > pos + 1 else app_dir()
        theme = None
        if len(sys.argv) > pos + 2 and sys.argv[pos + 2] in ("dark", "light"):
            theme = sys.argv[pos + 2]
        run_ui_shot(target, theme)
        return
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setStyleSheet(THEMES["dark"])
    app.setWindowIcon(make_app_icon())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
