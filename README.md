# HttpLite

> 轻量级 HTTP 接口测试工具（类 Postman），基于 Python + PySide6 开发，可打包为**免安装单文件 exe**，绿色便携。

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

### 响应查看
- 状态码按语义着色（2xx 绿 / 3xx 蓝 / 4xx 橙 / 5xx 红）
- 显示请求耗时与响应体大小
- 「响应体 / 响应头」双标签展示
- JSON 响应自动高亮，「美化 JSON」开关可切换压缩 / 缩进视图
- 一键「复制响应」到剪贴板

### 历史记录与集合
- 每次发送自动写入**历史记录**，右键可重发、另存到集合、清空历史
- **集合**以树形结构管理（文件夹 / 请求），支持新建、重命名、删除、右键发送
- 请求可一键「保存到集合」（快捷键 `Ctrl+S`），完整保留方法、地址、参数、请求头、Body 与认证配置

### 环境变量
- 多环境管理，环境之间可切换、复制、重命名、删除
- 在 URL / Headers / Body / 认证字段中使用 `{{变量名}}`，发送时按当前环境自动替换
- 变量可单独取消勾选以临时停用
- 内置 `默认环境`（`base_url=https://httpbin.org`）与 `本地调试` 两个示例环境

### 认证方式（7 种，均真实作用于请求并随请求存入历史与集合）

| 认证方式 | 说明 | 主要字段 |
| --- | --- | --- |
| 无认证 | 不携带任何认证信息 | — |
| Bearer Token | 自动添加 `Authorization: Bearer <Token>` 请求头 | Token |
| Basic Auth | HTTP Basic，`Authorization: Basic base64(用户名:密码)` | 用户名、密码 |
| Digest Auth | HTTP Digest 摘要认证，收到 401 挑战后自动按服务器 nonce 重发 | 用户名、密码 |
| API Key | 将 Key/Value 附加为请求头或查询参数 | Key 名称、Value、添加到（Header / Query 参数） |
| AWS Signature v4 | 按 AWS4-HMAC-SHA256 对当前方法 / 地址 / 查询串 / 请求体现场签名，自动写入 `X-Amz-Date` 与 `Authorization` 头 | Access Key、Secret Key、Session Token（可选）、Region、Service |
| JWT | 本地用密钥现场签发 JWT，支持 `HS256` / `HS384` / `HS512` / `none` | 算法、Secret、Payload、添加到（Header / Query 参数）、名称、前缀 |

- 认证面板支持「显示密钥」开关，默认对密钥类字段做掩码显示
- 面板底部提供实时**认证预览**，随方法 / 地址 / 环境变化同步更新
- 敏感字段支持 `{{变量}}` 占位，密钥不必硬编码在请求里
- JWT 的 `iat` / `exp` 等声明请直接写在 Payload 中；AWS Signature v4 调用 API Gateway 时 `Service` 常用 `execute-api`

### 便携与数据安全
- 单文件 exe，免安装、不写注册表
- 数据默认写入 **exe 同级目录** `HttpLite_data\workspace.json`；该目录不可写时自动回退到 `%APPDATA%\HttpLite_data`
- 整包（exe + 数据目录）拷贝即完成迁移

### 快捷键

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl+Enter` / `Ctrl+Return` | 发送请求 |
| `Ctrl+S` | 保存当前请求到集合 |

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
5. 需要复用请求时点「保存到集合」（或 `Ctrl+S`），之后从左侧集合树双击 / 右键即可再次调用
6. 所有改动（历史、集合、环境、设置）都会自动持久化到数据目录

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
HttpLite.exe --self-test            # 校验 HTTP / SSL / JSON 能力，结果写入 exe 同级的 HttpLite_selftest.txt
HttpLite.exe --ui-shot <输出目录>    # 离屏渲染 Authorization 面板并截图，用于界面核验
```

---

## 技术栈

- **语言**：Python 3.11
- **GUI**：PySide6（Qt for Python），单窗口 + 多标签页布局，`QSyntaxHighlighter` 实现 JSON 高亮
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
