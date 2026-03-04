# SSO 单点登录集成开发文档

## 1. 背景与目标

### 1.1 现状

Data Formulator（以下简称 DF）已集成 Apache Superset，支持以下登录方式：

- **Superset 账号密码登录**：前端提交用户名/密码 → DF 后端代理调用 Superset `/api/v1/security/login`（provider: db）→ 获取 JWT → 存入 Flask Session
- **匿名（访客）登录**：不连接 Superset，使用本地功能

### 1.2 目标

Superset 已接入企业 SSO 单点登录系统（OAuth2 协议），支持：
- 账号密码登录
- 企业微信扫码登录

本次改造目标：**在 DF 登录页面增加 SSO 登录入口**，复用 Superset 已有的 SSO 登录流程，使用户可以通过 SSO（含企微扫码）完成认证，并获取 Superset JWT 用于后续 API 调用。

### 1.3 改造原则

- 保留现有的 Superset 账号密码登录
- 保留现有的匿名（访客）登录
- SSO 登录流程完全复用 Superset 侧的 OAuth2 配置，DF 不需要独立对接 SSO Provider
- 最小化对 Superset 的改动
- **DF 端零额外配置**：只要 `SUPERSET_URL` 已配置，SSO 功能自动可用

---

## 2. 技术方案

### 2.1 方案概述

采用 **Popup 弹窗 + Superset Session 转 JWT** 的方式：

1. DF 前端弹出 Popup 窗口，打开 Superset 的登录页面
2. 用户在 Popup 中完成 SSO 认证（账密或企微扫码）
3. Superset 完成 OAuth 回调，创建 Session（用户已登录 Superset）
4. Popup 自动跳转到 Superset 的自定义 bridge 端点，将 Session 转换为 JWT
5. 通过 `window.postMessage` 将 JWT 传回 DF 主窗口
6. DF 前端将 JWT 发送给 DF 后端，存入 Flask Session
7. Popup 自动关闭，用户完成登录

### 2.2 流程图

```
┌──────────────────── DF 主窗口 (http://10.0.1.1:5000) ──────────────────┐
│                                                                         │
│  LoginView                                                              │
│  ┌─────────────────────────────────────────────┐                        │
│  │  [SSO 单点登录]          ← 新增              │                        │
│  │  ────────── 或 ──────────                    │                        │
│  │  [Superset 账号密码登录]  ← 现有功能，保留    │                        │
│  │  ────────── 或 ──────────                    │                        │
│  │  [以访客身份继续]         ← 现有功能，保留    │                        │
│  └─────────────────────────────────────────────┘                        │
│                    │ 用户点击 "SSO 单点登录"                              │
│                    ▼                                                     │
│  ① window.open("http://SUPERSET:8088/login/?next=...")                  │
│  ② window.addEventListener('message', handler)                          │
│                    │                                                     │
│     ┌──────────────┼─── Popup 窗口（Superset 域名下）────────┐            │
│     │              ▼                                          │            │
│     │  http://SUPERSET:8088/login/                            │            │
│     │  Superset 登录页 → 点击 SSO 按钮 → 跳转到 SSO           │            │
│     │              ▼                                          │            │
│     │  SSO 登录页面                                           │            │
│     │  ├── 账号密码输入                                        │            │
│     │  └── 企业微信扫码                                        │            │
│     │              ▼                                          │            │
│     │  SSO 回调 → Superset OAuth Callback                     │            │
│     │  Superset 创建 Session（用户已登录 Superset）             │            │
│     │              ▼                                          │            │
│     │  ③ Superset 内部重定向到 /df-sso-bridge/?df_origin=...  │            │
│     │     ← 注意：这个地址还是在 Superset 域名下！              │            │
│     │     (自定义端点：Session → JWT + postMessage)            │            │
│     │              ▼                                          │            │
│     │  ④ window.opener.postMessage(                           │            │
│     │       { type:'df-sso-auth', access_token, ... },        │            │
│     │       'http://10.0.1.1:5000'   ← DF 的 origin          │            │
│     │     )                                                   │            │
│     │  ⑤ window.close()                                       │            │
│     └──────────────┼──────────────────────────────────────────┘            │
│                    ▼                                                     │
│  ⑥ onMessage: 收到 tokens                                               │
│     POST /api/auth/sso/save-tokens { tokens, user }                     │
│  ⑦ DF 后端验证 token → 存入 Flask Session                                │
│  ⑧ 登录完成，刷新 UI                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 关键设计：`next` 参数和 `df_origin` 参数

#### `next` 参数

`next` 是 **Superset 内部的重定向参数**，指定 SSO 登录成功后 Superset 跳转到**自己服务器上的哪个路径**。

```
http://SUPERSET:8088/login/?next=/df-sso-bridge/?df_origin=...
                             ~~~~~~~~~~~~~~~~~~~
                             这是 Superset 自己服务器上的路径，不是 DF 的地址
```

整个 Popup 流程中，浏览器地址**始终在 Superset 域名下**：
1. `http://SUPERSET:8088/login/` → Superset 登录页
2. `https://sso.company.com/authorize?...` → SSO Provider
3. `http://SUPERSET:8088/oauth-authorized/...` → Superset 回调
4. `http://SUPERSET:8088/df-sso-bridge/?df_origin=...` → Bridge 端点

DF 的地址从头到尾没有出现在 Superset 的跳转链中。DF 主窗口只是静静地等待 `postMessage`。

#### `df_origin` 参数

DF 前端在打开 Popup 时，把自己的 `window.location.origin` 编码到 URL 中传给 Superset bridge 端点：

```javascript
const dfOrigin = encodeURIComponent(window.location.origin);
// 例如: http%3A%2F%2F10.0.1.1%3A5000

const next = encodeURIComponent(`/df-sso-bridge/?df_origin=${dfOrigin}`);
const popupUrl = `${SUPERSET_URL}/login/?next=${next}`;
```

Bridge 端点从 `request.args.get('df_origin')` 读取 DF 的 origin，用于 `postMessage` 的安全 `targetOrigin`。

**好处**：
- Superset 端**不需要硬编码任何 DF 地址**，零配置
- 每次 Popup 打开时动态传递，DF 换地址也不需要改 Superset
- `postMessage` 仍然有 `targetOrigin` 安全校验

---

## 3. Superset 端改动

### 3.1 新增自定义 Security Manager

在 Superset 的 `superset_config.py` 中添加一个自定义 SecurityManager，提供 `/df-sso-bridge/` 端点。

**文件**：`superset_config.py`（追加内容）

**功能**：

- 检查当前用户是否已通过 SSO 登录（Flask-Login session）
- 如果已登录，颁发 Superset JWT（access_token + refresh_token）
- 返回一个 HTML 页面，通过 `postMessage` 将 token 和用户信息发送给 DF 主窗口
- 自动关闭 Popup

**代码设计**：

```python
from superset.security import SupersetSecurityManager
from flask_appbuilder import expose
from flask import request, Response
from flask_login import current_user

class CustomSecurityManager(SupersetSecurityManager):

    @expose("/df-sso-bridge/", methods=["GET"])
    def df_sso_bridge(self):
        """
        供 Data Formulator 使用的 SSO 桥接端点。
        当用户通过 SSO 登录 Superset 后，此端点：
        1. 为当前用户颁发 JWT access_token 和 refresh_token
        2. 通过 postMessage 将 token 发送给 DF 父窗口
        3. 自动关闭 Popup 窗口

        DF 通过 URL 参数 df_origin 传入自己的 origin，
        bridge 使用该值作为 postMessage 的 targetOrigin 进行安全校验。
        """
        # df_origin 由 DF 前端通过 URL 参数传入
        df_origin = request.args.get("df_origin", "*")

        if not current_user.is_authenticated:
            return Response(
                "<html><body><p>未登录，请关闭此窗口重试。</p></body></html>",
                status=401,
                mimetype="text/html",
            )

        from flask_jwt_extended import create_access_token, create_refresh_token

        access_token = create_access_token(identity=current_user.id, fresh=True)
        refresh_token = create_refresh_token(identity=current_user.id)

        user_data = {
            "id": current_user.id,
            "username": current_user.username,
            "first_name": getattr(current_user, "first_name", "") or "",
            "last_name": getattr(current_user, "last_name", "") or "",
        }

        import json

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SSO Bridge</title></head>
<body>
<p>正在完成登录...</p>
<script>
(function() {{
    var payload = {{
        type: 'df-sso-auth',
        access_token: {json.dumps(access_token)},
        refresh_token: {json.dumps(refresh_token)},
        user: {json.dumps(user_data)}
    }};
    var targetOrigin = {json.dumps(df_origin)};
    if (window.opener) {{
        window.opener.postMessage(payload, targetOrigin);
        setTimeout(function() {{ window.close(); }}, 500);
    }} else {{
        document.body.innerHTML = '<p>登录成功，请关闭此窗口并返回 Data Formulator。</p>';
    }}
}})();
</script>
</body></html>"""
        return Response(html, mimetype="text/html")


CUSTOM_SECURITY_MANAGER_CLASS = CustomSecurityManager
```

### 3.2 配置说明

Superset 端**无需额外配置项**。只需：

1. 将上述代码追加到 `superset_config.py`
2. 重启 Superset

`df_origin` 由 DF 前端每次动态传入，不需要在 Superset 端维护任何 DF 地址列表。

### 3.3 验证

- 浏览器直接访问 `SUPERSET_URL/df-sso-bridge/`，应返回 401 页面（未登录）
- 先通过 Superset 正常 SSO 登录，再访问 `SUPERSET_URL/df-sso-bridge/?df_origin=http://test`，应看到"正在完成登录..."页面并尝试 postMessage

### 3.4 安全说明

- `postMessage` 使用 DF 传入的 `df_origin` 作为 `targetOrigin`，浏览器会校验接收窗口的 origin 是否匹配，不匹配则消息被丢弃
- `/df-sso-bridge/` 端点需要有效的 Superset Session，未认证用户无法获取 JWT
- Popup 是独立窗口（非 iframe），不受 `X-Frame-Options` 限制

---

## 4. DF 后端改动

### 4.1 新增 SSO Token 保存端点

**文件**：`py-src/data_formulator/superset/auth_routes.py`

新增路由 `/api/auth/sso/save-tokens`，接收前端从 Popup 获取的 Superset JWT，验证后写入 Flask Session。

**设计**：

```python
@auth_bp.route("/sso/save-tokens", methods=["POST"])
def sso_save_tokens():
    """
    接收前端通过 Popup SSO 流程获取的 Superset JWT tokens。
    验证 token 有效性后写入 Flask Session。
    """
    if not current_app.config.get("SUPERSET_ENABLED"):
        return jsonify({"status": "error", "message": "Superset is not configured"}), 501

    data = request.get_json(force=True)
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    user_from_popup = data.get("user", {})

    if not access_token:
        return jsonify({"status": "error", "message": "Missing access_token"}), 400

    # 验证 token：调用 Superset /api/v1/me 确认 token 真实有效
    try:
        user_info = _bridge().get_user_info(access_token)
    except Exception:
        # 若 /api/v1/me 不可用，使用 Popup 传来的用户信息作为 fallback
        user_info = user_from_popup

    if not user_info or not user_info.get("id"):
        # 再尝试 JWT fallback 解析
        user_info = _user_from_jwt_fallback(access_token, user_from_popup.get("username", ""))

    session["superset_token"] = access_token
    session["superset_refresh_token"] = refresh_token
    session["superset_user"] = user_info
    session.permanent = True

    user_id = user_info.get("id")
    if user_id is not None:
        session["session_id"] = f"superset_user_{user_id}"
    elif "session_id" not in session:
        session["session_id"] = f"superset_anon_{secrets.token_hex(8)}"
    session.permanent = True

    return jsonify({
        "status": "ok",
        "user": {
            "id": user_info.get("id"),
            "username": user_info.get("username", ""),
            "first_name": user_info.get("first_name", ""),
            "last_name": user_info.get("last_name", ""),
        },
        "session_id": session["session_id"],
    })
```

### 4.2 app-config 端点改动

**文件**：`py-src/data_formulator/app.py`

在 `/api/app-config` 返回值中新增 SSO 登录 URL，供前端使用。

**逻辑**：只要 `SUPERSET_URL` 已配置，就自动启用 SSO 登录按钮。**无需额外环境变量**。

```python
# 在 get_app_config() 的 config dict 中新增：
"SSO_LOGIN_URL": (app.config['SUPERSET_URL'].rstrip('/') + '/login/')
                  if app.config.get('SUPERSET_ENABLED') else None,
```

前端根据 `SSO_LOGIN_URL` 是否为 `null` 来决定是否显示 SSO 按钮。

### 4.3 OPEN_ENDPOINTS 更新

**文件**：`py-src/data_formulator/app.py`

将新端点加入免 Session 校验白名单：

```python
OPEN_ENDPOINTS = frozenset([
    # ... 现有端点 ...
    '/api/auth/sso/save-tokens',   # 新增
])
```

### 4.4 文件改动汇总（后端）

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `py-src/data_formulator/superset/auth_routes.py` | 新增路由 | 添加 `POST /api/auth/sso/save-tokens` |
| `py-src/data_formulator/app.py` | 修改 | `get_app_config()` 新增 `SSO_LOGIN_URL` 字段；`OPEN_ENDPOINTS` 新增端点 |

> **注意**：`.env.template` 无需修改，无新增环境变量。

---

## 5. DF 前端改动

### 5.1 API 端点注册

**文件**：`src/app/utils.tsx`

在 `getUrls()` 中新增：

```typescript
AUTH_SSO_SAVE_TOKENS: `/api/auth/sso/save-tokens`,
```

### 5.2 Redux State 默认值更新

**文件**：`src/app/dfSlice.tsx`

在 `serverConfig` 初始值中新增字段：

```typescript
SSO_LOGIN_URL: null as string | null,
```

### 5.3 LoginView 改造

**文件**：`src/views/LoginView.tsx`

这是改动最大的前端文件。需要在保留现有 UI 结构的基础上，新增 SSO 登录按钮和 Popup 处理逻辑。

#### 5.3.1 改造后的登录页布局

```
┌──────────────────────────────┐
│        Data Formulator       │
│   Connect your account...    │
│                              │
│  ┌── Superset Connection ──┐ │
│  │  [SSO 单点登录]          │ │  ← 新增（SSO_LOGIN_URL 存在时显示）
│  │  ── 或使用账号密码 ──     │ │  ← 新增分割线
│  │  用户名 [________]      │ │  ← 现有
│  │  密码   [________]      │ │  ← 现有
│  │  [登录]                  │ │  ← 现有
│  └──────────────────────────┘ │
│  ────────── 或 ──────────    │  ← 现有
│  [以访客身份继续]             │  ← 现有
└──────────────────────────────┘
```

当 `SUPERSET_ENABLED = true` 且 `SSO_LOGIN_URL` 不为 `null` 时，SSO 按钮出现在最上方。

#### 5.3.2 核心逻辑：SSO Popup 处理

```typescript
const handleSSOLogin = () => {
    setLoading(true);
    setError(null);

    // SSO_LOGIN_URL 由后端 app-config 提供，例如 "http://SUPERSET:8088/login/"
    const baseLoginUrl = serverConfig.SSO_LOGIN_URL;
    if (!baseLoginUrl) {
        setError(t('auth.ssoFailed', { message: 'SSO not configured' }));
        setLoading(false);
        return;
    }

    // 把 DF 的 origin 编码到 next 参数中，供 Superset bridge 端点使用
    const dfOrigin = encodeURIComponent(window.location.origin);
    const next = encodeURIComponent(`/df-sso-bridge/?df_origin=${dfOrigin}`);
    const ssoUrl = `${baseLoginUrl}?next=${next}`;

    // 打开 Popup 窗口，居中显示
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const popup = window.open(
        ssoUrl,
        'df-sso-login',
        `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`
    );

    if (!popup) {
        setError(t('auth.ssoPopupBlocked'));
        setLoading(false);
        return;
    }

    // 监听 postMessage
    const handleMessage = async (event: MessageEvent) => {
        if (event.data?.type !== 'df-sso-auth') return;

        window.removeEventListener('message', handleMessage);
        clearInterval(pollTimer);

        const { access_token, refresh_token, user } = event.data;

        try {
            const resp = await fetch(getUrls().AUTH_SSO_SAVE_TOKENS, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ access_token, refresh_token, user }),
            });
            const data = await resp.json();

            if (data.status === 'ok') {
                await dispatch(getSessionId()).unwrap();
                const configResp = await fetch(getUrls().APP_CONFIG, { credentials: 'include' });
                const configData = await configResp.json();
                dispatch(dfActions.setServerConfig(configData));
                onLoginSuccess();
            } else {
                setError(data.message || t('auth.ssoFailed', { message: 'Unknown error' }));
            }
        } catch (err: any) {
            setError(err.message || 'Network error');
        } finally {
            setLoading(false);
        }
    };

    window.addEventListener('message', handleMessage);

    // 轮询检测 Popup 是否被用户手动关闭
    const pollTimer = setInterval(() => {
        if (popup.closed) {
            clearInterval(pollTimer);
            window.removeEventListener('message', handleMessage);
            setLoading(false);
        }
    }, 1000);
};
```

#### 5.3.3 LoginView 不需要新增 Props

SSO 登录 URL 直接从 Redux store 的 `serverConfig.SSO_LOGIN_URL` 读取，通过现有的 `useSelector` 获取，无需修改 LoginView 的 Props 接口。

### 5.4 App.tsx 改动

**无需修改**。SSO 配置通过 `serverConfig` 自动传递，LoginView 从 Redux store 读取。

### 5.5 i18n 国际化

**文件**：`src/i18n/locales/en/common.json` 和 `src/i18n/locales/zh/common.json`

在 `auth` 分组下新增：

**英文**：

```json
"ssoLogin": "SSO Login",
"ssoLoggingIn": "Logging in via SSO...",
"ssoDescription": "Login with your enterprise account via Single Sign-On",
"ssoPopupBlocked": "Popup blocked. Please allow popups for this site.",
"ssoFailed": "SSO login failed: {{message}}",
"ssoOrPassword": "or sign in with Superset account"
```

**中文**：

```json
"ssoLogin": "SSO 单点登录",
"ssoLoggingIn": "正在通过 SSO 登录...",
"ssoDescription": "使用企业账号通过单点登录系统认证",
"ssoPopupBlocked": "弹窗被拦截，请允许本站弹出窗口。",
"ssoFailed": "SSO 登录失败：{{message}}",
"ssoOrPassword": "或使用 Superset 账号登录"
```

### 5.6 文件改动汇总（前端）

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/app/utils.tsx` | 修改 | `getUrls()` 新增 `AUTH_SSO_SAVE_TOKENS` |
| `src/app/dfSlice.tsx` | 修改 | `serverConfig` 初始值新增 `SSO_LOGIN_URL` |
| `src/views/LoginView.tsx` | 修改 | 新增 SSO 按钮、Popup 处理逻辑 |
| `src/i18n/locales/en/common.json` | 修改 | 新增 SSO 相关翻译 |
| `src/i18n/locales/zh/common.json` | 修改 | 新增 SSO 相关翻译 |

> `src/app/App.tsx` 不需要修改。

---

## 6. 完整改动文件清单

### DF 端（共 5 个文件 + 2 个 i18n 文件）

| # | 文件 | 类型 | 改动量 |
|---|------|------|--------|
| 1 | `py-src/data_formulator/superset/auth_routes.py` | 修改 | ~40 行（新增 1 个路由） |
| 2 | `py-src/data_formulator/app.py` | 修改 | ~5 行（config 新增字段 + OPEN_ENDPOINTS） |
| 3 | `src/app/utils.tsx` | 修改 | ~1 行 |
| 4 | `src/app/dfSlice.tsx` | 修改 | ~1 行 |
| 5 | `src/views/LoginView.tsx` | 修改 | ~80 行（SSO 按钮 + Popup 逻辑） |
| 6 | `src/i18n/locales/en/common.json` | 修改 | ~6 行 |
| 7 | `src/i18n/locales/zh/common.json` | 修改 | ~6 行 |

### Superset 端（共 1 个文件）

| # | 文件 | 类型 | 改动量 |
|---|------|------|--------|
| 1 | `superset_config.py` | 修改 | ~40 行（自定义 SecurityManager + bridge 端点） |

---

## 7. 配置指南

### 7.1 Superset 端

**步骤**：

1. 在 `superset_config.py` 末尾追加第 3 节的 `CustomSecurityManager` 代码
2. 重启 Superset

**就这两步，没有其他配置。**

**验证**：
- 浏览器直接访问 `SUPERSET_URL/df-sso-bridge/`，应看到"未登录"提示
- 先通过 Superset 正常 SSO 登录，再访问 `SUPERSET_URL/df-sso-bridge/?df_origin=http://test`，应看到"正在完成登录..."并尝试 postMessage

### 7.2 DF 端

**无需任何额外配置。** 只要 `.env` 中的 `SUPERSET_URL` 已配置：

```env
SUPERSET_URL=http://10.0.1.2:8088
```

DF 自动：
- 在 `app-config` 中返回 `SSO_LOGIN_URL`
- 前端显示 SSO 登录按钮
- 打开 Popup 时自动拼接 Superset 登录 URL + bridge 跳转参数 + DF origin

**验证**：
- 访问 `/api/app-config`，确认返回包含 `"SSO_LOGIN_URL": "http://10.0.1.2:8088/login/"`
- 登录页面应显示 SSO 登录按钮

### 7.3 配置项总结

| 配置项 | 位置 | 是否新增 | 说明 |
|--------|------|----------|------|
| `SUPERSET_URL` | DF `.env` | 已有 | SSO 功能自动复用此配置 |
| `CustomSecurityManager` | Superset `superset_config.py` | 新增 | ~40 行代码 |

**对比原方案省略了**：
- ~~`SSO_PROVIDER_NAME`~~ — 不需要，使用 Superset 通用登录页
- ~~`DF_ALLOWED_ORIGINS`~~ — 不需要，DF origin 通过 URL 参数动态传递
- ~~`SSO_ENABLED`~~ — 不需要，由 `SUPERSET_ENABLED` + `SSO_LOGIN_URL` 自动推断

---

## 8. 登录后的 Token 生命周期

SSO 登录获取的 Superset JWT 与现有账密登录获取的 JWT 完全一致，生命周期管理**无需任何额外改动**：

| 阶段 | 处理方式 | 相关代码 |
|------|----------|----------|
| Token 存储 | Flask Session（HttpOnly cookie） | `auth_routes.py` → `sso_save_tokens()` |
| Token 使用 | 代理调用 Superset API 时从 Session 读取 | `catalog_routes.py` → `_require_auth()` |
| Token 过期检测 | 解析 JWT `exp` 字段，提前 60 秒视为过期 | `catalog_routes.py` → `_is_token_expired()` |
| Token 自动刷新 | 使用 refresh_token 调 Superset API | `catalog_routes.py` → `_try_refresh()` |
| 401 自动重试 | 捕获 Superset 401 → 刷新 token → 重试请求 | `catalog_routes.py` / `data_routes.py` |
| Session 有效期 | 365 天 | `app.py` → `PERMANENT_SESSION_LIFETIME` |
| 登出 | 清空 Flask Session | `auth_routes.py` → `logout()` |

---

## 9. 安全考虑

### 9.1 postMessage 安全

- **发送端**（Superset bridge）：使用 DF 通过 `df_origin` 参数传入的值作为 `targetOrigin`，浏览器会校验接收窗口的实际 origin 是否匹配
- **接收端**（DF 前端）：通过 `event.data.type === 'df-sso-auth'` 过滤消息
- **消息投递**：`postMessage` 只发送给 `window.opener`（即打开 Popup 的 DF 主窗口），其他窗口无法接收

### 9.2 df_origin 参数的安全性

问：如果攻击者伪造 `df_origin` 参数会怎样？

答：`postMessage(payload, targetOrigin)` 中的 `targetOrigin` 是一个**安全约束**，不是路由目标。消息始终发给 `window.opener`，`targetOrigin` 只决定"如果 opener 的 origin 不匹配就丢弃消息"。即使攻击者传入错误的 `df_origin`，消息也只会被丢弃（因为与 opener 的实际 origin 不匹配），不会发到攻击者的页面。

此外，bridge 端点需要有效的 Superset Session，未认证用户无法触发。

### 9.3 Token 保存端点安全

- `/api/auth/sso/save-tokens` 收到 token 后，调用 Superset `/api/v1/me` 进行**二次验证**
- Token 仅存储在 Flask Session（HttpOnly cookie），前端无法读取

### 9.4 CSRF 防护

- `sso_save_tokens` 端点使用 POST 方法 + `credentials: 'include'`，与现有 `login` 端点安全模型一致
- Flask Session 的 `SameSite=Lax` 策略已提供基本的 CSRF 保护

---

## 10. 边界情况与错误处理

| 场景 | 处理方式 |
|------|----------|
| 浏览器拦截 Popup | 前端提示"请允许弹出窗口"，停止 loading |
| 用户在 Popup 中手动关闭 | 轮询检测 `popup.closed`，清理监听器，恢复 UI |
| SSO 登录失败 | Superset/SSO 显示错误，Popup 不到达 bridge，最终用户关闭 Popup |
| Superset Session 过期（bridge 返回 401） | Popup 中显示"未登录"提示 |
| Token 验证失败（save-tokens 返回错误） | 前端显示错误信息，用户可重试 |
| Superset 未配置（SUPERSET_URL 为空） | SSO 按钮不显示，只显示访客入口 |
| postMessage 超时 | 可增加超时定时器（如 5 分钟），超时后清理并提示 |
| Superset 未配置 OAuth（无 SSO） | Popup 打开 Superset 登录页，用户看到普通登录表单，可手动关闭 |
| `next` 参数不生效 | 用户在 Popup 中手动访问 `/df-sso-bridge/?df_origin=...` 完成流程 |

---

## 11. 实现顺序（建议）

| 步骤 | 任务 | 依赖 |
|------|------|------|
| 1 | Superset 端：添加 CustomSecurityManager 和 bridge 端点 | 无 |
| 2 | 验证 bridge 端点（手动浏览器测试） | 步骤 1 |
| 3 | DF 后端：添加 `/api/auth/sso/save-tokens` 路由 | 无 |
| 4 | DF 后端：修改 `app-config` 返回值 + OPEN_ENDPOINTS | 无 |
| 5 | DF 前端：修改 `LoginView.tsx`（SSO 按钮 + Popup 逻辑） | 步骤 3, 4 |
| 6 | DF 前端：修改 `utils.tsx`、`dfSlice.tsx` | 步骤 5 |
| 7 | DF 前端：添加 i18n 翻译 | 步骤 5 |
| 8 | 端到端测试 | 全部 |

---

## 12. 测试计划

### 12.1 单元测试

| 测试项 | 预期 |
|--------|------|
| `sso_save_tokens` 缺少 token | 返回 400 |
| `sso_save_tokens` 无效 token | fallback 到 JWT 解析 |
| `sso_save_tokens` 有效 token | 正确写入 Session 并返回用户信息 |
| `app-config` 未配置 SUPERSET_URL | `SSO_LOGIN_URL` 为 null |
| `app-config` 已配置 SUPERSET_URL | `SSO_LOGIN_URL` 返回正确 URL |

### 12.2 集成测试

| 测试项 | 步骤 | 预期结果 |
|--------|------|----------|
| SSO 登录（企业微信扫码） | 点击 SSO 登录 → 扫码 → 等待 | 登录成功，显示用户名 |
| SSO 登录（账密） | 点击 SSO 登录 → 输入账密 → 提交 | 登录成功，显示用户名 |
| 原有账密登录 | 输入 Superset 用户名密码 → 登录 | 登录成功（不受影响） |
| 访客登录 | 点击"以访客身份继续" | 进入应用（不受影响） |
| SSO 登录后访问数据集 | SSO 登录 → 打开 Superset 数据集目录 | 正常加载数据集列表 |
| SSO 登录后 Token 刷新 | SSO 登录 → 等待 Token 过期 → 访问数据集 | 自动刷新 Token |
| Popup 被拦截 | 浏览器阻止 Popup | 显示友好提示 |
| 用户关闭 Popup | 加载后手动关闭 Popup | UI 恢复正常 |
| 登出后重新 SSO 登录 | 登出 → SSO 登录 | 登录成功 |

---

## 13. 后续扩展（可选）

- **Token 过期主动弹窗**：当 JWT 和 refresh_token 都过期时，前端弹出 SSO 重新登录弹窗
- **自动 SSO 登录**：如果检测到 SSO Session 仍然有效，自动打开隐藏 iframe 静默登录
- **多 SSO Provider 支持**：如果 Superset 配置了多个 OAuth Provider，LoginView 展示多个按钮
