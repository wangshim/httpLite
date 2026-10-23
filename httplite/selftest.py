# -*- coding: utf-8 -*-
"""自检与离屏截图。"""
from __future__ import annotations
import json
import os
import sys
import time
from urllib.parse import urlsplit
import requests
from PySide6.QtWidgets import QApplication
from httplite.assertions import *
from httplite.auth import *
from httplite.codegen import *
from httplite.constants import *
from httplite.persistence import *
from httplite.postman import *
from httplite.protocol import *
from httplite.updater import *
from httplite.utils import *
from httplite.workers import *
from httplite.ui import *
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

    # WebSocket / SSE / 更新检查 功能自检（本地回环，不依赖外网）
    try:
        ws_ok = ws_accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
        frame = ws_build_frame(0x1, b"selftest", mask=True)
        parser = WsFrameParser()
        parsed = parser.feed(frame)
        frame_ok = len(parsed) == 1 and parsed[0][2] == b"selftest"
        sse_ok = parse_sse_lines("event: e\ndata: d\n\n".splitlines()) == [{"event": "e", "data": "d"}]
        ver_ok = version_compare("1.6.1", "1.6.0") > 0 and version_compare("v1.6.0", "1.6.0") == 0
        upd_panel_ok = hasattr(win, "ws_panel") and win.left_tabs.count() == 3
        upd_btn_ok = hasattr(win, "check_upd_btn") and win.check_upd_btn.text() == "检查更新"
        ws_new = ws_ok and frame_ok and sse_ok and ver_ok and upd_panel_ok and upd_btn_ok
        ok = ok and ws_new
        lines.append(
            f"ws/sse/update: accept={ws_ok} frame={frame_ok} sse={sse_ok} version={ver_ok} "
            f"ws_panel={upd_panel_ok} upd_btn={upd_btn_ok}"
        )
    except Exception as e:  # noqa: BLE001
        ok = False
        lines.append("ws/sse/update error: " + repr(e))

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
            # WebSocket / SSE 面板视图（不触发真实连接）
            try:
                ws_panel = win.ws_panel
                win.left_tabs.setCurrentWidget(ws_panel)
                ws_panel.type_combo.setCurrentText("WebSocket")
                ws_panel.url_edit.setText("wss://echo.websocket.org/")
                qapp.processEvents()
                saved = win.grab().save(os.path.join(out_dir, f"{theme}_ws.png"))
                ws_panel.type_combo.setCurrentText("SSE")
                ws_panel.url_edit.setText("https://api.example.com/events")
                qapp.processEvents()
                saved2 = win.grab().save(os.path.join(out_dir, f"{theme}_sse.png"))
                lines.append(f"[{theme}] ws saved={saved} type={ws_panel.type_combo.currentText()} url={ws_panel.url_edit.text()}")
                lines.append(f"[{theme}] sse saved={saved2} state={ws_panel.status_label.text()}")
            except Exception as e:  # noqa: BLE001
                lines.append(f"[{theme}] ws/sse error: {repr(e)}")
            win.close()
    except Exception as e:  # noqa: BLE001
        lines.append("ui-shot error: " + repr(e))
    try:
        with open(os.path.join(out_dir, "HttpLite_uishot.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass
    sys.exit(0)
