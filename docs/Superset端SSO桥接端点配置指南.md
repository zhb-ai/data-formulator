# Superset 端配置指南：Data Formulator SSO 桥接端点

## 1. 背景

Data Formulator（以下简称 DF）需要通过 Superset 的 SSO 登录来获取 Superset JWT，以便调用 Superset REST API。

由于 DF 和 Superset 部署在不同的内网 IP 上（跨域），DF 无法直接读取 Superset 的 Session/Cookie。因此需要在 Superset 中添加一个小型桥接端点，在用户通过 SSO 登录 Superset 后，将 Session 转换为 JWT 并通过浏览器的 `postMessage` 传回 DF。

## 2. 工作原理

```
DF 前端                          Superset
  │                                │
  │  ① window.open(弹窗)           │
  │ ──────────────────────────────>│  /login/?next=/df-sso-bridge/?df_origin=...
  │                                │
  │                                │  ② 用户在 Superset 完成 SSO 登录（账密/企微扫码）
  │                                │
  │                                │  ③ 登录成功后 Superset 内部重定向到:
  │                                │     /df-sso-bridge/?df_origin=http://DF地址
  │                                │
  │                                │  ④ bridge 端点：
  │                                │     - 检查 Session（用户已登录）
  │                                │     - 颁发 JWT access_token + refresh_token
  │                                │     - 返回 HTML，执行 postMessage 将 token 发给 DF
  │                                │     - 自动关闭弹窗
  │  ⑤ 收到 postMessage            │
  │<───────────────────────────────│
  │                                │
  │  ⑥ DF 拿到 JWT，后续正常调用 Superset API
```

## 3. 需要做的事

**只需修改一个文件**：`superset_config.py`，在末尾追加以下代码，然后重启 Superset。

## 4. 完整代码

将以下代码追加到 `superset_config.py` 文件末尾：

```python
# =============================================================================
# Data Formulator SSO 桥接端点
# 用途：DF 通过弹窗打开 Superset 登录页，SSO 登录成功后跳转到此端点，
#       将 Superset Session 转换为 JWT，通过 postMessage 传回 DF 前端。
# =============================================================================

from superset.security import SupersetSecurityManager
from flask_appbuilder import expose
from flask import request, Response
from flask_login import current_user


class CustomSecurityManager(SupersetSecurityManager):

    @expose("/df-sso-bridge/", methods=["GET"])
    def df_sso_bridge(self):
        """
        Data Formulator SSO 桥接端点。

        当用户通过 SSO 登录 Superset 后，此端点：
        1. 为当前用户颁发 JWT access_token 和 refresh_token
        2. 通过 postMessage 将 token 发送给 DF 父窗口
        3. 自动关闭弹窗

        URL 参数:
            df_origin: DF 前端的 origin（如 http://10.0.1.1:5000），
                       由 DF 前端自动传入，用于 postMessage 的 targetOrigin 安全校验。
        """
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

## 5. 注意事项

### 5.1 如果已有 CustomSecurityManager

如果 `superset_config.py` 中**已经定义**了 `CustomSecurityManager`（或其他自定义 SecurityManager 类），不要重复创建新类，只需将 `df_sso_bridge` 方法添加到现有类中即可：

```python
# 假设已有:
class CustomSecurityManager(SupersetSecurityManager):
    # ... 现有的自定义方法 ...

    # 追加这个方法:
    @expose("/df-sso-bridge/", methods=["GET"])
    def df_sso_bridge(self):
        # ... 上面第 4 节中的完整方法体 ...
```

### 5.2 如果已有 CUSTOM_SECURITY_MANAGER_CLASS

如果已经设置了 `CUSTOM_SECURITY_MANAGER_CLASS`，确认它指向的是包含 `df_sso_bridge` 方法的那个类。不需要重复设置。

### 5.3 无需额外配置

- **不需要**在 Superset 中配置任何 DF 的地址
- **不需要**新增环境变量
- **不需要**修改 CORS 配置
- DF 的地址通过 URL 参数 `df_origin` 动态传入，无需硬编码

## 6. 验证步骤

部署后按以下步骤验证：

### 6.1 未登录状态测试

浏览器直接访问：

```
http://SUPERSET地址:端口/df-sso-bridge/
```

**预期**：返回 401 页面，显示"未登录，请关闭此窗口重试。"

### 6.2 已登录状态测试

1. 先通过 Superset 正常登录（SSO 或账密都行）
2. 在同一浏览器访问：

```
http://SUPERSET地址:端口/df-sso-bridge/?df_origin=http://test
```

**预期**：页面显示"正在完成登录..."，浏览器控制台（Console）中可以看到 `postMessage` 调用（因为没有 `window.opener`，页面会显示"登录成功，请关闭此窗口并返回 Data Formulator。"）

### 6.3 验证 JWT 有效性（可选）

在步骤 6.2 的页面上，打开浏览器开发者工具 → Network，查看页面源码中的 `access_token` 值，然后用它调用：

```bash
curl -H "Authorization: Bearer <access_token>" http://SUPERSET地址:端口/api/v1/me/
```

**预期**：返回当前登录用户的信息。

## 7. 安全说明

| 关注点 | 说明 |
|--------|------|
| **谁能访问 bridge 端点？** | 只有已通过 Superset 认证（有有效 Session）的用户，未登录返回 401 |
| **JWT 发给谁？** | 通过 `postMessage` 只发给 `window.opener`（即打开弹窗的 DF 页面） |
| **targetOrigin 安全性** | 使用 DF 传入的 `df_origin` 作为 `targetOrigin`，浏览器会校验接收窗口的实际 origin 是否匹配，不匹配则消息被丢弃 |
| **df_origin 被伪造？** | `postMessage` 始终发给 `window.opener`，`targetOrigin` 只是过滤条件。伪造只会导致消息被丢弃，不会泄露到第三方 |
