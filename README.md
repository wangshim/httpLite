---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 5c96509d255f4e87c60df81df97919d9_8e7ff489b26e11f1b2fa525400638852
    ReservedCode1: GW+l3pQmMf6TAFPnjeGpG7ZzyfxuxWTg1rCfyr9D+8XGTv2Kl2xfpJVMgVBQhBl0c+SjSRShxAcbuhtq2PYghJmMGr6WZpQ+VC7gJuGn9bZj3zHtn+o+w+jgQuQpcy41hFhkYZpbkac0mpT17Zn4XiGusg8AD/ZJslCvD1Ya7K4Y+h5gFk8e7AcowpU=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 5c96509d255f4e87c60df81df97919d9_8e7ff489b26e11f1b2fa525400638852
    ReservedCode2: GW+l3pQmMf6TAFPnjeGpG7ZzyfxuxWTg1rCfyr9D+8XGTv2Kl2xfpJVMgVBQhBl0c+SjSRShxAcbuhtq2PYghJmMGr6WZpQ+VC7gJuGn9bZj3zHtn+o+w+jgQuQpcy41hFhkYZpbkac0mpT17Zn4XiGusg8AD/ZJslCvD1Ya7K4Y+h5gFk8e7AcowpU=
---

# HttpLite

> 轻量级 HTTP 接口测试工具（类 Postman），基于 Python + PySide6 开发，可打包为**免安装单文件 exe**，绿色便携。

> **当前版本：1.6.0**（WebSocket / SSE 实时调试 + 内置更新检查）

HttpLite 面向日常接口调试场景：不想启动笨重的客户端，也不依赖浏览器插件，双击一个 exe 就能发请求、看响应、管变量、带认证。所有数据保存在本地，不联网、不写注册表。

---

## 功能特性

### 请求构建
- 支持 `GET` / `POST` / `PUT` / `DELETE` / `PATCH` / `HEAD` / `OPTIONS` 七种方法
- **Query 参数**：表格化编辑 Key / Value，支持逐条启用或停用，支持「从 URL 导入参数」一键把地址栏里的查询串解析成参数行
- **Headers**：表格化编辑，支持启用 / 停用单条请求头
- **Body**：四种类型
  - `none`：不携带请求体
  - `JSON`：带语法高亮编辑区与「格式化 JSON」按钮
  - `form-data`：表单上传
  - `x-www-form-urlencoded`：URL 编码表单

### 生成代码
- 请求构建区顶部新增「**生成代码**」按钮，一键把当前请求（方法、URL、Query 参数、Headers、Body、认证配置）转成三种代码片段
- 支持 `cURL` / `Python (requests)` / `JavaScript (fetch)` 三标签展示，**切换标签自动复制到剪贴板**，可直接粘贴到终端或代码库
- 认证信息按当前配置真实写入（Bearer / Basic / API Key / AWS v4 / JWT 均生成对应头或参数；OAuth 2.0 使用已缓存 token），变量按当前环境展开

### 多标签页
- 同时打开多个请求标签，每个标签都是一套**完整且独立**的请求上下文（方法、URL、Query、Headers、Body、认证配置、响应区）
- 顶部「＋」新建标签；标签页右侧关闭按钮或 `Ctrl+W` 关闭当前标签
- 标签标题实时反映当前请求（如 `POST {{base_url}}/api/login`），未保存的改动以 `●` 标记
- 关闭未保存到集合的标签时给出提示（不强制保存），已保存或未改动的标签直接关闭
- 新建的请求标签始终跟随全局设置，主题切换后所有标签即时联动

### 响应查看
- 状态码按语义着色（2xx 绿 / 3xx 蓝 / 4xx 橙 / 5xx 红）
- 显示请求耗时与响应体大小
- 「响应体 / 响应头 / 测试」三标签展示
- JSON 响应自动高亮，「美化 JSON」开关可切换压缩 / 缩进视图
- 一键「复制响应」到剪贴板

### 测试 / 断言与变量提取
- 响应面板新增**「测试」**标签页：表格化配置断言，发送请求后自动逐条执行
- 内置 6 种断言：**状态码等于**、**状态码范围**（支持 `2xx` / `200-299` / `200` 写法）、**耗时小于(ms)**、**响应体包含**、**JSON 字段存在**（`$.data.token` 极简路径）、**JSON 字段值等于**
- 断言逐条显示 ✔ 通过 / ✘ 失败及说明，顶部汇总 `通过数/总数`
- 支持**变量提取**：从响应中按 JSON 路径或正则（有捕获组取第一组）提取值，自动写入**当前环境变量**，后续请求可用 `{{变量名}}` 引用
- 断言与提取配置随请求一起保存到集合 / 历史，从集合加载时自动还原

### Postman 导入 / 导出
- **导入 Postman Collection v2.1**：`集合` 面板顶部「导入 Postman」按钮，选择导出的 `.json` 文件即可
- 完整映射：请求方法、URL（含 Query 参数）、Headers、Body（JSON / raw / urlencoded / form-data）、Bearer / Basic / API Key 认证、文件夹树结构；同名集合重复导入时覆盖更新
- **导出 Postman v2.1**：选中集合文件夹后「导出 Postman」按选中文件夹导出，未选中时导出全部集合；「导出选中请求」可把单个请求导出为独立集合文件，便于分享或迁回 Postman
- 导出的 JSON 符合 v2.1 schema，可被 Postman / 其他工具直接导入

### 历史记录与集合
- 每次发送自动写入**历史记录**，右键可重发、另存到集合、清空历史
- 历史列表顶部提供**搜索与过滤**：按 URL 关键字实时过滤，并按请求方法、响应状态码（2xx / 3xx / 4xx / 5xx / 错误）下拉筛选，三个条件可叠加
- **集合**以树形结构管理（文件夹 / 请求），支持新建、重命名、删除、右键发送
- 请求可一键「保存到集合」（快捷键 `Ctrl+S`），完整保留方法、地址、参数、请求头、Body 与认证配置

### 集合运行器
- 集合面板顶部新增「**运行集合**」按钮，按顺序执行集合内全部请求（嵌套文件夹递归展开）
- 执行期间**实时**更新每个请求的方法、URL、状态码、耗时、断言通过率，支持中途「停止」
- 结束后汇总**成功 / 失败**统计（按 2xx 判定成功，断言失败同样计入失败），失败项**双击可定位**到对应请求标签，便于复现调试

### WebSocket / SSE 实时调试（v1.6.0）
- 左侧新增 **「WebSocket / SSE」** 独立面板，类型下拉切换 WebSocket 与 SSE 两种连接
- **WebSocket**：支持 `ws://` / `wss://` 连接（标准库原生实现 RFC 6455，零第三方依赖）；连接后实时显示收发消息列表（带时间戳与 发送/接收 标记），底部输入框可发送文本消息并即时回显；状态徽章实时展示 未连接 / 连接中 / 已连接 / 连接失败 / 已断开
- **断开重连**：连接中断后点击「重连」即可重新建立连接；「断开」主动关闭当前连接；「清空消息」清空收发记录
- **SSE**：支持 `http://` / `https://` 的 `text/event-stream` 订阅地址；连接后事件流内容**实时追加**显示（含 `event:` 事件名与 `data:` 数据），显示连接状态，可随时断开
- 面板配色随深色 / 浅色主题联动

### 内置更新检查（v1.6.0）
- 顶部选项行新增「**检查更新**」按钮：点击后请求 GitHub Releases API（仓库 `wangshim/httpLite`），获取最新版本号并与当前版本比较
- 发现新版本时弹窗提示：当前版本、最新版本、发布时间、更新说明与**下载地址**，可直接复制前往下载
- 「**启动时检查更新**」勾选框默认开启：每次启动延迟静默检查，有新版时弹窗提示；取消勾选后不再自动检查，仍可随时手动点击「检查更新」
- 版本比较支持 `v` 前缀与多段数字（如 `1.6.1` > `1.6.0`），网络失败时静默降级（手动点击时给出失败原因），不影响正常使用

### 主题（深色 / 浅色）
- 设置区提供「深色」/「浅色」主题下拉切换，选择即时生效并**持久化**到 `workspace.json`，下次启动自动恢复
- 全部界面元素适配深色：主窗口、请求编辑区、表格、标签页、菜单、认证面板、JSON 高亮、状态徽章等
- 深色主题面向夜间 / 暗色环境下的长时间调试场景

### 环境变量
- 多环境管理，环境之间可切换、复制、重命名、删除
- 在 URL / Headers / Body / 认证字段中使用 `{{变量名}}`，发送时按当前环境自动替换
- 变量可单独取消勾选以临时停用
- 内置 `默认环境`（`base_url=https://httpbin.org`）与 `本地调试` 两个示例环境

### 认证方式（8 种，均真实作用于请求并随请求存入历史与集合）

| 认证方式 | 说明 | 主要字段 |
| --- | --- | --- |
| 无认证 | 不携带任何认证信息 | — |
| Bearer Token | 自动添加 `Authorization: Bearer <Token>` 请求头 | Token |
| Basic Auth | HTTP Basic，`Authorization: Basic base64(用户名:密码)` | 用户名、密码 |
| Digest Auth | HTTP Digest 摘要认证，收到 401 挑战后自动按服务器 nonce 重发 | 用户名、密码 |
| API Key | 将 Key/Value 附加为请求头或查询参数 | Key 名称、Value、添加到（Header / Query 参数） |
| AWS Signature v4 | 按 AWS4-HMAC-SHA256 对当前方法 / 地址 / 查询串 / 请求体现场签名，自动写入 `X-Amz-Date` 与 `Authorization` 头 | Access Key、Secret Key、Session Token（可选）、Region、Service |
| JWT | 本地用密钥现场签发 JWT，支持 `HS256` / `HS384` / `HS512` / `none` | 算法、Secret、Payload、添加到（Header / Query 参数）、名称、前缀 |
| OAuth 2.0 | 按授权流程获取 `access_token` 并以 `Bearer` 自动附加请求，支持手动刷新 | 见下表 |

- 认证面板支持「显示密钥」开关，默认对密钥类字段做掩码显示
- 面板底部提供实时**认证预览**，随方法 / 地址 / 环境变化同步更新
- 敏感字段支持 `{{变量}}` 占位，密钥不必硬编码在请求里
- JWT 的 `iat` / `exp` 等声明请直接写在 Payload 中；AWS Signature v4 调用 API Gateway 时 `Service` 常用 `execute-api`

#### OAuth 2.0 说明

- 支持三种授权流程（Grant Type）：
  - **Client Credentials（客户端凭证）**：`client_id` + `client_secret` 换取 token，适合服务端到服务端调用
  - **Password（密码模式）**：`username` + `password` 换取 token，适合受信客户端
  - **Authorization Code（授权码模式）**：点击「获取授权」复制授权 URL 并打开浏览器，授权后把回调地址粘贴回输入框自动提取 `code` 换取 token（也可直接手动填入 `authorization_code`）
- 获取到的 `access_token` / `refresh_token` 缓存在请求配置中并随请求持久化到历史 / 集合，发送时自动以 `Authorization: Bearer <token>` 附加
- 支持**手动刷新**（按钮「刷新 Token」，要求服务器支持 refresh_token）与「自动刷新」开关（token 过期或缺失时自动用 refresh_token 换取新 token）
- Token URL / 授权 URL / 客户端信息均支持 `{{变量}}` 占位

### 便携与数据安全
- 单文件 exe，免安装、不写注册表
- 数据默认写入 **exe 同级目录** `HttpLite_data\workspace.json`；该目录不可写时自动回退到 `%APPDATA%\HttpLite_data`
- 整包（exe + 数据目录）拷贝即完成迁移

### 快捷键

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl+Enter` / `Ctrl+Return` | 发送当前标签的请求 |
| `Ctrl+S` | 保存当前标签的请求到集合 |
| `Ctrl+T` | 新建请求标签 |
| `Ctrl+W` | 关闭当前请求标签 |

---

## 环境要求

- 操作系统：Windows（开发与验证环境为 Windows 10）
- Python：3.11
- 运行依赖：

| 依赖 | 版本（开发环境实测） | 用途 |
| --- | --- | --- |
| PySide6 | 6.11.2 | 桌面 GUI |
| requests | 2.34.2 | HTTP 请求 |
| urllib3 | 2.8.0 | requests 传输层 |

---

## 快速开始（源码运行）

```bash
pip install PySide6 requests
python app.py
```

## 使用说明

1. 顶部选择请求方法，填入 URL（可用 `{{base_url}}/path` 形式引用环境变量）
2. 在「Query 参数」「Headers」「Body」「Authorization」标签页中按需配置请求内容
3. 在右上角下拉框选择**环境**，必要时点开环境管理增删变量
4. 点击「发送」（或 `Ctrl+Enter`），下方查看响应状态、耗时、大小与响应体 / 响应头
5. 需要自动校验响应时，切到「测试」标签添加断言（如状态码 `2xx`、`body 包含 success`）；需要把响应里的 `token` 等值带进后续请求时，在「变量提取」中填变量名与 JSON 路径 / 正则，发送后自动写入当前环境
6. 需要复用请求时点「保存到集合」（或 `Ctrl+S`），之后从左侧集合树双击 / 右键即可再次调用
7. 从 Postman 迁移：集合面板点「导入 Postman」选 v2.1 导出文件；分享给 Postman 用户：选中集合文件夹点「导出 Postman」（或右键选中请求点「导出选中请求」）
8. 需要 OAuth 2.0 认证时：认证方式选「OAuth 2.0」，按 Grant Type 填好 Token URL / 客户端信息后点「获取 Token」（Authorization Code 先「获取授权」在浏览器授权并把回调地址粘贴回「授权码」框），发送时自动附带 Bearer token；token 过期可点「刷新 Token」或打开「自动刷新」
9. 需要把当前请求分享为代码：点「生成代码」，在 cURL / Python / JavaScript 三个标签间切换，切换时自动复制，直接粘贴使用
10. 需要批量跑集合：集合面板点「运行集合」，实时查看每个请求的方法 / URL / 状态码 / 耗时 / 断言通过率，结束后查看成功失败统计，失败项双击跳转到对应请求
11. 所有改动（历史、集合、环境、设置）都会自动持久化到数据目录
12. 需要实时联调 WebSocket / SSE 时：切到左侧「WebSocket / SSE」标签，类型选 WebSocket（`ws://` / `wss://` 地址）或 SSE（`http(s)://` 事件流地址），点「连接」，WebSocket 可输入文本发送并实时回显；中断后点「重连」恢复
13. 需要确认版本时：点顶部「检查更新」手动请求 GitHub Releases 最新版本；「启动时检查更新」勾选框控制是否每次启动自动静默检查，发现新版会弹窗给出下载地址

---

## 打包为单文件 exe

### 方式一：命令行直接打包

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --noupx --icon HttpLite.ico app.py
```

产物为 `dist\HttpLite.exe`（本机实测约 46.7 MB），双击即可运行，无需安装 Python 与依赖。

### 方式二：使用仓库内 spec 文件

```bash
pyinstaller HttpLite.spec
```

> 说明：`HttpLite.spec` 中的 `app.py` 与 `HttpLite.ico` 使用绝对路径，换机器打包前请按实际目录调整。

### 打包后自检

exe 内置两个免交互自检开关，便于确认打包产物在 frozen 环境下能力正常：

```bash
HttpLite.exe --self-test            # 校验 HTTP / SSL / JSON / 认证向量（含 OAuth 2.0 逻辑）/ Postman 导入导出 / 断言与提取 / 代码生成 / 集合运行器 / WebSocket·SSE·更新检查逻辑 / UI 冒烟，结果写入 exe 同级的 HttpLite_selftest.txt
HttpLite.exe --ui-shot <输出目录> [dark|light]   # 离屏渲染并截图（认证面板含 OAuth 2.0 / 多标签 / 历史过滤 / 测试断言 / 代码生成 / 集合运行器），默认深色
```

---

## 技术栈

- **语言**：Python 3.11
- **GUI**：PySide6（Qt for Python），单窗口 + 多标签页布局，`QSyntaxHighlighter` 实现 JSON 高亮，内置深 / 浅两套 QSS 主题并支持运行时切换
- **Postman 互通**：Collection v2.1 JSON 解析 / 生成（URL、Headers、Body、认证、文件夹树），支持极简 JSON 路径与正则表达式断言 / 提取
- **代码生成**：请求一键转 cURL / Python(requests) / JavaScript(fetch) 三语言片段，自动复制到剪贴板
- **集合运行器**：集合内请求顺序批量执行，实时展示状态 / 耗时 / 断言通过率并汇总统计，失败项可跳转定位
- **WebSocket / SSE（v1.6.0）**：标准库 `socket` / `ssl` / `struct` 原生实现 RFC 6455 客户端（握手 + 帧编解码），独立面板实时收发与连接状态；SSE 基于 requests 流式解析 `text/event-stream`
- **内置更新检查（v1.6.0）**：GitHub Releases API 版本比对 + 新版本弹窗（含下载地址），支持启动静默检查开关
- **OAuth 2.0**：Client Credentials / Password / Authorization Code 三种授权流程，token 自动以 Bearer 附加，支持手动刷新与自动刷新
- **网络**：requests（含 `HTTPDigestAuth`），请求在独立 `QThread` 中执行，避免阻塞界面
- **认证签名**：标准库 `hmac` / `hashlib` / `base64` 手写实现 AWS Signature v4 与 JWT 签发
- **数据持久化**：单个 `workspace.json` 文件
- **打包**：PyInstaller（`--onefile --windowed --noupx`）

---

## 目录结构

```
httplite-src/
├── app.py               # 主程序（单文件源码，含界面、请求、认证、持久化与自检逻辑）
├── HttpLite.spec        # PyInstaller 打包配置
├── HttpLite.ico         # 应用图标
├── README.md            # 本文件
├── LICENSE              # MIT 许可证
└── .gitignore
```

运行时生成（不纳入版本控制）：

```
HttpLite_data/workspace.json   # 历史、集合、环境、设置
HttpLite_selftest.txt          # --self-test 输出
```

---

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
*（内容由AI生成，仅供参考）*
