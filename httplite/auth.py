# -*- coding: utf-8 -*-
"""认证内核：Bearer/Basic/Digest/API Key/AWS v4/JWT/OAuth 2.0。"""
from __future__ import annotations
import base64
import datetime
import hashlib
import hmac
import json
import re
import time
from datetime import timezone
from urllib.parse import parse_qsl, quote, urlencode, urlsplit
import requests
from requests.auth import HTTPDigestAuth
from httplite.constants import (
    AUTH_TYPE_KEYS,
    AUTH_TYPE_LABELS,
    JWT_ALGORITHMS,
    OAUTH2_GRANTS,
)
from httplite.utils import b64url, mask_secret, set_header, substitute
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
