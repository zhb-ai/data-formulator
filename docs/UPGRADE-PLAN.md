# Data Formulator 自定义版本升级计划

## 从 DF 0.6 Fork → DF 0.7 官方基准 + 模块化自定义功能

> 策略核心：以 DF 0.7 官方代码为基准，将 0.6 中的自定义功能以**最低侵入性**方式重新整合，建立可持续的上游同步机制。

---

## 一、整体架构策略

### 1.1 Git 工作流

```
microsoft/data-formulator (upstream)
    │
    ├── v0.7.0a1 tag
    │
    └── v0.8 (未来) ─────────────────────────────→
         │
         v
your-org/data-formulator (origin)
    │
    ├── main ← 始终跟踪 upstream/main
    ├── custom/release ← 你的发行版（main + 所有 feature 分支合并）
    │
    ├── feature/i18n-vite-plugin ← i18n（Vite 构建时翻译插件）
    ├── feature/superset-integration ← Superset 后端集成
    ├── feature/security ← 安全模块
    ├── feature/auth-sso ← 登录/SSO + SupersetCatalog
    ├── feature/model-management ← 服务端全局模型管理
    ├── feature/agent-cjk-compat ← Agent 中文/非 ASCII 兼容
    ├── feature/table-enhancements ← 表格追加/列类型修改
    ├── feature/report-enhancements ← 报告多语言 + 自定义规则
    └── feature/misc-improvements ← 日志级别 + UI 小改动
```

### 1.2 原则

1. **每个自定义功能一个独立 feature 分支**，方便单独维护和合并
2. **核心文件修改不超过 5 行**（app.py、vite.config.ts 等）
3. **自定义代码集中在独立目录**，不散落在官方代码中
4. **i18n 完全零侵入**，通过 Vite 构建插件实现
5. **每次上游更新**：fetch upstream → merge 到 main → 逐个 rebase feature 分支 → 合并到 release

---

## 二、前置准备

### Phase 0：初始化仓库与 Git 追踪

```bash
# 1. 克隆官方 0.7 代码（或直接使用你已下载的）
cd E:\superset\df0.7-alpha\data-formulator0.7-alpha

# 2. 初始化为你的仓库（如尚未做）
git init
git remote add origin <你的仓库地址>

# 3. 添加上游追踪
git remote add upstream https://github.com/microsoft/data-formulator.git
git fetch upstream

# 4. 基于 0.7 官方代码创建 main
git checkout -b main
git add .
git commit -m "feat: init from upstream v0.7.0-alpha1"
git push -u origin main
```

---

## 三、功能模块升级计划

### Phase 1：i18n 国际化（Vite 插件方式）

**侵入性：极低（仅修改 1 个配置文件 + 新增独立目录）**

#### 0.6 中的问题
- 使用 `react-i18next`，需要在每个组件中 `import { useTranslation }` 并调用 `t()`
- 修改了几十个 view 文件，导致每次上游更新都有大量冲突
- 需要安装 3 个 npm 依赖：`i18next`, `react-i18next`, `i18next-browser-languagedetector`

#### 0.7 新方案：Vite 构建时翻译插件

**原理**：在 Vite 构建过程中，通过 AST 解析 TSX/JSX 文件，将匹配的英文字符串自动替换为目标语言。翻译只发生在内存中，**不修改任何源文件**。

#### 需要创建的文件

```
src/
└── i18n/                              # 翻译模块（独立目录）
    ├── vite-plugin-i18n.ts            # Vite 翻译插件
    ├── translate.ts                   # 翻译核心逻辑
    ├── extract-strings.ts             # 字符串提取工具（辅助开发）
    └── locales/
        ├── zh.json                    # 中文翻译字典（扁平化 key-value）
        └── ... (其他语言)
```

#### 需要修改的文件

| 文件 | 修改内容 | 行数 |
|------|---------|------|
| `vite.config.ts` | 添加 1 行 import + 1 行 plugin 注册 | +2 行 |
| `package.json` | 无需额外依赖（Vite 插件用原生 AST 或已有的 SWC） | 0 行 |

#### 翻译字典格式

将 0.6 中分散的 7 个 JSON 文件合并为一个扁平字典。格式：

```json
{
  "Data Formulator": "Data Formulator",
  "Loading...": "加载中...",
  "Upload": "上传",
  "Save": "保存",
  "Explore data with visualizations, powered by AI agents.": "用 AI Agent 驱动可视化探索数据。",
  ...
}
```

> key = 源码中的英文原文，value = 目标语言翻译

#### 插件工作方式

```
源文件 (.tsx)          Vite transform()            输出 (内存中)
─────────────         ──────────────────          ────────────────
>Upload Data<    →    匹配字典 "Upload Data"  →   >上传数据<
label="Settings" →    匹配字典 "Settings"     →   label="设置"
title="Help"     →    匹配字典 "Help"         →   title="帮助"
```

#### 实施步骤

1. 从 0.6 的 `en/*.json` + `zh/*.json` 生成扁平化翻译字典
2. 编写 Vite 插件（优先简单字符串匹配版，后续可升级为 AST 版）
3. 在 `vite.config.ts` 中注册插件
4. 通过环境变量 `VITE_LANG=zh` 控制是否启用翻译
5. 验证构建产物中的翻译效果

#### 语言切换方式

- **构建时切换**：`VITE_LANG=zh npm run build` → 生成中文版
- **运行时切换**（可选增强）：构建时将所有语言字典打包，前端 JS 运行时动态替换

#### 0.6 → 0.7 翻译字典迁移

0.6 中有 7 个分类 JSON 文件（common, chart, encoding, messages, model, navigation, upload），
需要提取其中的**英文原文**作为字典 key，对应的中文作为 value。

可用脚本自动完成：
```js
// 伪代码：将嵌套 JSON 转为扁平 key-value
// { "app": { "save": "Save" } } → 提取 value "Save"
// 然后在中文 JSON 中找对应路径 → { "Save": "保存" }
```

#### 处理 0.7 新增字符串

0.7 新增了以下组件/视图，需要补充翻译：

| 新组件 | 预估新增字符串数 |
|--------|----------------|
| `ChartGallery.tsx` | ~10-15 |
| `ChartRenderService.tsx` | ~5 |
| `SimpleChartRecBox.tsx` | ~5-10 |
| `ChatThreadView.tsx` | ~10-15 |
| `DataThreadCards.tsx` | ~10 |
| `ChartGallery` 相关 | ~10 |
| `tokens.ts` (调色板名称) | ~5 |
| 工作区保存/加载相关 UI | ~10-15 |

**合计预估**：60-80 个新增翻译条目

---

### Phase 2：Superset 集成（后端模块化注入）

**侵入性：低（app.py 增加约 5 行扩展注册代码）**

#### 需要复制的目录/文件

| 来源 (0.6) | 目标 (0.7) | 说明 |
|------------|-----------|------|
| `py-src/data_formulator/superset/` | 原样复制 | 整个目录，6 个文件 |
| `src/views/SupersetCatalog.tsx` | 原样复制 | 前端 Superset 目录组件 |

#### 需要适配的变更

| 变更项 | 详情 |
|--------|------|
| `app.py` 中的 blueprint 注册 | 0.7 使用 `_register_blueprints()` 函数式注册，需在其中添加 Superset 条件注册 |
| `app.py` 中的 CLI 参数 | 需要添加 `--superset-url` 参数到 0.7 的 `parse_args()` |
| `app.py` 中的 app-config | 需在 `get_app_config()` 返回中添加 `SUPERSET_ENABLED`、`SSO_LOGIN_URL` |
| `dfSlice.tsx` 中的 ServerConfig | 需添加 `SUPERSET_ENABLED` 和 `SSO_LOGIN_URL` 字段 |
| `session` 机制 | 0.7 移除了 flask session，使用 browser identity；Superset 的 SSO 认证需要适配 |

#### 推荐的 app.py 修改方式

在 0.7 的 `_register_blueprints()` 函数末尾添加扩展注入点：

```python
def _register_blueprints():
    # ... 官方原有的 blueprint 注册 ...

    # === 自定义扩展注入点 ===
    _register_custom_extensions()


def _register_custom_extensions():
    """Register custom extensions (Superset, etc.) if configured."""
    superset_url = os.environ.get('SUPERSET_URL', '') or app.config['CLI_ARGS'].get('superset_url', '')
    if superset_url:
        from data_formulator.superset.auth_routes import auth_bp
        from data_formulator.superset.catalog_routes import catalog_bp
        from data_formulator.superset.data_routes import superset_data_bp
        from data_formulator.superset.auth_bridge import SupersetAuthBridge
        from data_formulator.superset.superset_client import SupersetClient
        from data_formulator.superset.catalog import SupersetCatalog

        app.config['SUPERSET_URL'] = superset_url
        app.config['SUPERSET_ENABLED'] = True

        bridge = SupersetAuthBridge(superset_url)
        app.extensions["superset_bridge"] = bridge
        superset_client = SupersetClient(superset_url)
        app.extensions["superset_client"] = superset_client
        catalog_ttl = int(os.environ.get('CATALOG_CACHE_TTL', '300'))
        catalog = SupersetCatalog(superset_client, cache_ttl=catalog_ttl)
        app.extensions["superset_catalog"] = catalog

        app.register_blueprint(auth_bp)
        app.register_blueprint(catalog_bp)
        app.register_blueprint(superset_data_bp)
```

#### 关键适配：Session → Identity

0.6 的 Superset 认证依赖 Flask session（`session['superset_user']`），
0.7 改用了 browser identity（`getBrowserId()`）。

**适配方案**：
- 后端 Superset 认证路由继续使用 Flask session 存储 SSO token（独立于 0.7 的 identity 机制）
- 前端 SupersetCatalog 组件通过 `/api/auth/me` 独立获取认证状态
- 不修改 0.7 的 identity 系统

---

### Phase 3：安全模块

**侵入性：极低（独立模块，纯后端）**

#### 需要复制的文件

| 来源 (0.6) | 目标 (0.7) | 说明 |
|------------|-----------|------|
| `py-src/data_formulator/security/` | 原样复制 | query_validator.py + __init__.py |

#### 需要适配的变更

- 0.7 使用了新的 sandbox 机制（`sandbox/local_sandbox.py`, `sandbox/docker_sandbox.py`），安全模块的 query 验证可能需要与新 sandbox 集成
- 检查 `query_validator.py` 的调用点，确保在 0.7 的 agent 路由中正确引用

#### 集成方式

在 agent 路由中按需导入：
```python
# 在 agent_routes.py 或相关路由中
try:
    from data_formulator.security.query_validator import validate_query
except ImportError:
    validate_query = None  # 安全模块未安装时跳过
```

---

### Phase 4：登录/SSO 视图

**侵入性：中等（需要条件渲染到 App.tsx）**

#### 需要复制的文件

| 来源 (0.6) | 目标 (0.7) | 说明 |
|------------|-----------|------|
| `src/views/LoginView.tsx` | 复制并适配 | 需要适配 0.7 的 identity 系统 |

#### 0.6 中的问题

LoginView 在 0.6 中被硬编码到 `App.tsx` 中：
```tsx
// 0.6 App.tsx 中
if (supersetEnabled && !authUser) {
    return <LoginView />;
}
```

这导致 `App.tsx` 有较大侵入性修改。

#### 0.7 新方案：条件式懒加载

```tsx
// 在 App.tsx 中仅添加 1 个条件加载块
const LoginView = React.lazy(() => import('../views/LoginView'));

// 在 App 组件内
{serverConfig?.SUPERSET_ENABLED && !authUser && (
    <Suspense fallback={<CircularProgress />}>
        <LoginView onLogin={handleLogin} />
    </Suspense>
)}
```

#### 关键适配

| 项目 | 0.6 | 0.7 适配 |
|------|-----|---------|
| 认证状态存储 | `dfSlice.tsx` 中的 `AuthUser` + `sessionId` | 创建独立的 `authSlice.tsx` 或使用 React Context |
| 认证 API | `/api/auth/login`, `/api/auth/me` | 保持不变，独立于 0.7 的 identity 系统 |
| 会话恢复 | Flask session cookie | Superset SSO token 存储在 Flask session，前端通过 `/api/auth/me` 检查 |

#### 推荐：创建独立的 authSlice.tsx

```
src/
└── extensions/
    └── auth/
        ├── authSlice.ts       # 独立的 Redux slice，管理 AuthUser 状态
        ├── LoginView.tsx       # 登录视图（从 0.6 迁移）
        └── AuthProvider.tsx    # 认证状态 Provider
```

这样 `dfSlice.tsx` 完全不需要修改。

---

### Phase 5：前端 SupersetCatalog

**侵入性：低（独立组件 + App.tsx 中条件导入）**

#### 需要复制的文件

| 来源 (0.6) | 目标 (0.7) |
|------------|-----------|
| `src/views/SupersetCatalog.tsx` | `src/extensions/superset/SupersetCatalog.tsx` |

#### 集成方式

在 `App.tsx` 或相关视图中条件渲染：
```tsx
const SupersetCatalog = React.lazy(() => import('../extensions/superset/SupersetCatalog'));
```

#### 需要适配的变更

- 0.6 的 SupersetCatalog 依赖 dfSlice 中的 `supersetEnabled` 状态
- 0.7 改为从 `authSlice`（新建）获取
- 数据加载逻辑可能需要适配 0.7 新的 datalake 模块

---

### Phase 6：模型管理系统（0.6 commit `f9d6e5d` + `eb431ca`）

**侵入性：中（需适配 0.7 新 agent 架构）**
**Git 分支：`feature/model-management`**

#### 为什么需要这个功能

0.6 官方的模型配置完全由前端管理：用户必须在浏览器 UI 中逐个添加模型的 endpoint、API key 等信息。这在生产部署中有严重问题：

1. **API 密钥暴露**：用户能在浏览器 DevTools 中看到所有模型的 API key
2. **无法集中管理**：每个用户都需要手动配置，无法由管理员统一预配置
3. **部署不便**：Docker / 多人共享环境下，每人都要重复配置

`model_registry.py` 实现了**服务端全局模型配置**：管理员通过环境变量预配置模型，前端自动加载可用模型列表（不含敏感信息），用户无需手动输入。

#### 0.6 中涉及的文件

| 文件 | 变更内容 | 行数 |
|------|---------|------|
| `py-src/.../model_registry.py` | **全新文件**：从环境变量加载模型配置，支持 openai/azure/anthropic/gemini/ollama 及自定义 provider | +113 行 |
| `py-src/.../agent_routes.py` | 添加 `/api/agent/check-available-models` 返回全局模型列表；调用模型时优先使用 registry 中的凭据 | ~128 行改动 |
| `py-src/.../agents/client_utils.py` | 添加日志级别控制、模型兼容性检测 | ~95 行改动 |
| `src/app/dfSlice.tsx` | 新增 `globalModels: ModelConfig[]`、`globalModelsLoading: boolean` 状态 + `fetchGlobalModels` thunk | +61 行 |
| `src/app/store.ts` | 调整 persist 白名单 | +6 行 |
| `src/views/ModelSelectionDialog.tsx` | 重构 UI：分"全局模型"（服务端配置）和"本地模型"（用户自行添加）两个区域 | ~342 行改动 |
| `src/views/DataFormulator.tsx` | 启动时自动拉取全局模型列表 | +15 行 |

#### 0.6 → 0.7 的关键差异

| 项目 | 0.6 | 0.7 |
|------|-----|-----|
| `model_registry.py` | 存在 | **不存在**，0.7 无此功能 |
| `agent_routes.py` | 大量自定义修改 | 0.7 也有大量重构（统一 DataAgent 入口） |
| `ModelConfig.is_global` 字段 | 存在 | 不存在 |
| `dfSlice` 中 `globalModels` | 存在 | 不存在 |

#### 0.7 非侵入方案

**后端**：`model_registry.py` 作为独立模块，放入 `py-src/data_formulator/extensions/` 目录。

```python
# py-src/data_formulator/extensions/model_registry.py
# 直接从 0.6 复制，无需修改
```

在 `_register_custom_extensions()` 中加载（复用 Phase 2 的注入点，不额外修改 app.py）：

```python
def _register_custom_extensions():
    # ... Superset 注册代码 ...

    # 全局模型注册
    from data_formulator.extensions.model_registry import model_registry
    app.extensions["model_registry"] = model_registry
```

agent 路由的全局模型查询接口，以独立 Blueprint 注册：

```python
# py-src/data_formulator/extensions/model_routes.py
from flask import Blueprint, jsonify
model_ext_bp = Blueprint('model_ext', __name__)

@model_ext_bp.route('/api/agent/global-models', methods=['GET'])
def get_global_models():
    from flask import current_app
    registry = current_app.extensions.get("model_registry")
    return jsonify(registry.list_public() if registry else [])
```

**前端**：全局模型状态放入独立的 `extensions/models/modelSlice.ts`，不修改 `dfSlice.tsx`。

```
src/extensions/models/
├── modelSlice.ts           # globalModels 状态 + fetchGlobalModels thunk
└── GlobalModelBadge.tsx    # 模型列表中显示"全局"标记的小组件
```

`ModelSelectionDialog.tsx` 的改动较大，需要在 0.7 版本的基础上重新适配。建议以 0.7 的 `ModelSelectionDialog.tsx` 为基准，仅添加全局模型的显示逻辑。

#### 侵入官方文件

| 文件 | 修改 |
|------|------|
| `app.py` | 0 行（复用 Phase 2 的注入点） |
| `src/app/store.ts` | +2 行（注册 modelSlice） |
| `src/views/ModelSelectionDialog.tsx` | ~30 行（添加全局模型列表渲染，其余逻辑在 modelSlice 中） |

---

### Phase 7：Agent 中文/非 ASCII 增强（0.6 commits `c1abb77` + `39749b7` + `70e56a9`）

**侵入性：中（涉及 0.7 重构后的 agent 文件）**
**Git 分支：`feature/agent-cjk-compat`**

#### 为什么需要这些功能

Data Formulator 默认假设表名和列名都是英文 ASCII 字符。但在中文环境下：

1. **中文表名/列名**：用户上传的 CSV/Excel 通常有中文列名如 `"销售额"`、`"日期"`。SQL 查询中使用未转义的中文标识符会导致语法错误
2. **JSON 序列化 Unicode 转义**：Python 的 `json.dumps()` 默认将中文编码为 `\uXXXX`，LLM 收到的 prompt 中全是转义字符，严重影响理解和生成质量
3. **纯文本模型发送图片**：部分国产模型（如 deepseek-chat）不支持 vision/图像输入，发送包含 base64 图像的 prompt 会报错

#### 0.6 中涉及的文件（3 个功能合并）

**功能 A：非 ASCII 标识符支持**

| 文件 | 变更内容 |
|------|---------|
| `py-src/.../agent_routes.py` | 表名清理函数保留 Unicode 字符；SQL prompt 中要求双引号包裹非 ASCII 表名/列名；SQL 失败时自动回退到 Python agent | +227 行 |
| `py-src/.../agents/agent_sql_data_rec.py` | prompt 中增加非 ASCII 标识符处理说明 | +5 行 |
| `py-src/.../agents/agent_sql_data_transform.py` | 同上 | +20 行 |
| `py-src/.../data_loader/external_data_loader.py` | 数据加载器中 Unicode 表名处理 | +8 行 |

**功能 B：ensure_ascii=False**

| 文件 | 变更内容 |
|------|---------|
| `py-src/.../agents/agent_exploration.py` | `json.dumps(..., ensure_ascii=False)` | 2 行 |
| `py-src/.../agents/agent_py_data_transform.py` | 同上 | 4 行 |
| `py-src/.../agents/agent_sql_data_transform.py` | 同上 | 4 行 |

**功能 C：纯文本模型图像输入检测**

| 文件 | 变更内容 |
|------|---------|
| `py-src/.../agents/client_utils.py` | 检测模型是否支持图像输入；纯文本模型请求失败时自动移除 image block 后重试 | +73 行 |
| `src/views/DataLoadingThread.tsx` | 前端显示"此模型可能不支持图像输入"警告 | +14 行 |

#### 0.6 → 0.7 的文件映射

0.7 对 agent 系统做了大幅重构，0.6 中的多个文件在 0.7 中已合并或改名：

| 0.6 文件 | 0.7 对应文件 | 状态 |
|----------|------------|------|
| `agent_sql_data_rec.py` | `agent_data_rec.py`（不再区分 sql/py） | 已合并 |
| `agent_sql_data_transform.py` | `agent_data_transform.py` | 已合并 |
| `agent_py_data_transform.py` | `agent_data_transform.py` | 已合并 |
| `agent_exploration.py` | **已删除**（功能合并到 `data_agent.py`） | 已删除 |
| `client_utils.py` | `client_utils.py`（仍存在，但结构有变） | 需适配 |
| `agent_routes.py` | `agent_routes.py`（仍存在，但路由结构大改） | 需适配 |

> 0.7 的 `data_agent.py` 中已有 1 处 `ensure_ascii=False`（第 211 行），但未全面覆盖。

#### 0.7 非侵入方案

这些改动本质是 **bug fix / 兼容性修复**，无法做到零侵入，但可以最小化改动范围：

**方案 A：非 ASCII 标识符 —— 作为 monkey-patch 模块**

```python
# py-src/data_formulator/extensions/cjk_compat.py
"""
CJK / non-ASCII compatibility patches for agent prompts and SQL generation.
"""

def patch_table_name_sanitizer():
    """Override the default table name sanitizer to preserve Unicode chars."""
    import data_formulator.agent_routes as routes
    original = getattr(routes, '_sanitize_table_name', None)
    if original:
        def unicode_safe_sanitize(name: str) -> str:
            import re
            cleaned = re.sub(r'[^\w\u4e00-\u9fff\u3400-\u4dbf]', '_', name)
            return cleaned.strip('_') or 'unnamed_table'
        routes._sanitize_table_name = unicode_safe_sanitize

def patch_ensure_ascii():
    """Ensure all json.dumps in agent modules use ensure_ascii=False."""
    # 如果 0.7 的 data_agent.py 还有遗漏的 json.dumps，在此处补丁
    pass
```

在 `_register_custom_extensions()` 中调用：

```python
from data_formulator.extensions.cjk_compat import patch_table_name_sanitizer, patch_ensure_ascii
patch_table_name_sanitizer()
patch_ensure_ascii()
```

**方案 B：SQL prompt 增强 —— 修改 prompt 模板文件**

如果 0.7 将 prompt 提取为独立的模板文件（需确认），可以直接替换 prompt 模板。否则需要在对应 agent 文件中修改 prompt 字符串，涉及侵入：

| 文件 | 需修改位置 | 改动量 |
|------|-----------|--------|
| `agent_data_rec.py` | prompt 中加入 "Use double quotes for non-ASCII identifiers" | +2 行 |
| `agent_data_transform.py` | 同上 | +2 行 |
| `data_agent.py` | 确保所有 `json.dumps` 使用 `ensure_ascii=False` | ~3 行 |

**方案 C：图像输入检测 —— 封装为中间件**

```python
# py-src/data_formulator/extensions/vision_compat.py
"""
Auto-detect and handle non-vision models receiving image content.
"""

def strip_image_blocks(messages: list) -> list:
    """Remove image_url content blocks from messages for text-only models."""
    cleaned = []
    for msg in messages:
        if isinstance(msg.get("content"), list):
            msg = {**msg, "content": [
                block for block in msg["content"]
                if not (isinstance(block, dict) and block.get("type") == "image_url")
            ]}
        cleaned.append(msg)
    return cleaned

def safe_completion(client, messages, **kwargs):
    """Try completion; on image-related failure, retry without images."""
    try:
        return client.chat.completions.create(messages=messages, **kwargs)
    except Exception as e:
        if "image" in str(e).lower() or "vision" in str(e).lower():
            cleaned = strip_image_blocks(messages)
            return client.chat.completions.create(messages=cleaned, **kwargs)
        raise
```

#### 侵入官方文件

| 文件 | 修改 | 说明 |
|------|------|------|
| `agent_data_rec.py` | +2 行 | prompt 模板微调 |
| `agent_data_transform.py` | +2 行 | prompt 模板微调 |
| `data_agent.py` | ~3 行 | 补齐遗漏的 `ensure_ascii=False` |
| `client_utils.py` | +5 行 | 引入 vision_compat 的 `safe_completion` |
| `agent_routes.py` | +5 行 | 表名清理函数替换 |
| `DataLoadingThread.tsx` | +10 行 | 前端警告提示（仅条件显示，不改结构） |

合计约 **27 行**，全部是功能性修复，无结构性改动。

---

### Phase 8：表格功能增强（0.6 commits `488efc1` + `69086d6`）

**侵入性：中低**
**Git 分支：`feature/table-enhancements`**

#### 为什么需要这些功能

**功能 A：表格追加 & 流式摄入**（后端）

在实际数据工作流中，数据往往是增量到达的（如实时数据、分批导入）。官方只支持"上传整张新表"，不支持向已有表追加数据。本功能新增了两个 API 端点：

- `/api/tables/append-table`：向现有 DuckDB 表追加行
- `/api/tables/stream-ingest`：分块流式写入大量数据

**功能 B：列类型修改 + 表格显示优化**（前端）

用户上传 CSV 后，自动推断的列类型不一定准确（如 "001" 被推断为数字而非字符串）。本功能允许用户在表头右键菜单中手动修改列的数据类型。同时优化了表格显示：

- 数值列右对齐 + 千位分隔符
- 添加行号列（缩小宽度，支持行号跳转）
- 表头显示列序号

#### 0.6 中涉及的文件

**功能 A：表格追加 & 流式摄入**

| 文件 | 变更内容 |
|------|---------|
| `py-src/.../tables_routes.py` | 新增 `/append-table` 和 `/stream-ingest` 两个路由 | +122 行 |

**功能 B：列类型修改 + 表格显示优化**

| 文件 | 变更内容 |
|------|---------|
| `src/app/dfSlice.tsx` | 新增 `updateColumnType` reducer | +12 行 |
| `src/views/SelectableDataGrid.tsx` | 表头类型修改菜单、行号列、数值格式化、千位分隔符 | +223 行 |
| `src/views/DataView.tsx` | 列宽/布局调整 | +22 行 |
| `src/views/VisualizationView.tsx` | 类型修改后的图表联动 | +11 行 |

#### 0.7 非侵入方案

**功能 A：表格路由 —— 独立 Blueprint**

0.7 的 `tables_routes.py` 也有变更，但新增的追加/流式端点与官方无冲突（是纯新增的路由）。

最低侵入方案：将新增路由提取为独立 Blueprint：

```python
# py-src/data_formulator/extensions/table_ext_routes.py
from flask import Blueprint, request, jsonify
table_ext_bp = Blueprint('table_ext', __name__)

@table_ext_bp.route('/api/tables/append-table', methods=['POST'])
def append_table():
    # ... 从 0.6 tables_routes.py 中提取
    pass

@table_ext_bp.route('/api/tables/stream-ingest', methods=['POST'])
def stream_ingest():
    # ... 从 0.6 tables_routes.py 中提取
    pass
```

在 `_register_custom_extensions()` 中注册（不修改 tables_routes.py）。

**功能 B：列类型修改 —— 需少量侵入前端**

这个功能与 `SelectableDataGrid.tsx` 和 `dfSlice.tsx` 紧耦合，无法完全独立。推荐方案：

| 文件 | 改动 | 说明 |
|------|------|------|
| `src/app/dfSlice.tsx` | +12 行 | 在 reducers 末尾新增 `updateColumnType`，位置固定，升级时冲突概率极低 |
| `src/views/SelectableDataGrid.tsx` | ~50 行（精简版） | 只添加表头右键菜单 + 类型修改逻辑，不大幅重构原有渲染 |
| `src/views/DataView.tsx` | +10 行 | 行号列宽度和数值对齐样式 |

> 注意：0.6 中 `SelectableDataGrid.tsx` 有 +223 行改动，其中约 100 行是 i18n 相关（0.7 中通过 Vite 插件处理），实际需要迁移的纯功能代码约 120 行。

#### 侵入官方文件

| 文件 | 修改 |
|------|------|
| `app.py` | 0 行（复用注入点） |
| `dfSlice.tsx` | +12 行（末尾新增 reducer） |
| `SelectableDataGrid.tsx` | ~50 行 |
| `DataView.tsx` | +10 行 |

---

### Phase 9：报告生成增强（0.6 commits `82cbe2f` + `10a8317` + `be1710c`）

**侵入性：低**
**Git 分支：`feature/report-enhancements`**

#### 为什么需要这些功能

1. **多语言报告生成**：0.6 官方的报告 prompt 只生成英文。修改后支持根据前端语言设置生成对应语言的报告
2. **自定义规则**：允许用户在 Agent Rules 中配置报告生成的自定义规则（如"使用正式语气"、"突出数据异常"等）
3. **字体修复**：报告中"执行摘要"样式使用衬线体（serif），在中文环境下显示效果差，改为系统字体

#### 0.6 中涉及的文件

| 文件 | 变更内容 |
|------|---------|
| `py-src/.../agents/agent_report_gen.py` | prompt 中增加 `language` 和 `custom_rules` 参数 | +33 行 |
| `py-src/.../agent_routes.py` | 报告生成路由接收并传递 language/rules 参数 | +9 行 |
| `src/views/ReportView.tsx` | 前端传递语言偏好和自定义规则；执行摘要字体从 serif 改为系统字体 | ~34 行改动 |

#### 0.7 非侵入方案

0.7 中 `agent_report_gen.py` **仍然存在**且结构相似，侵入较小。

| 文件 | 改动 | 说明 |
|------|------|------|
| `agent_report_gen.py` | +15 行 | 在 prompt 模板中增加 language 和 rules 注入点 |
| `agent_routes.py` | +5 行 | 报告路由增加参数传递 |
| `ReportView.tsx` | ~15 行 | 字体修改 + 传参（i18n 部分由 Vite 插件处理） |

合计约 **35 行**。

---

### Phase 10：日志与小改动（0.6 commits `eb431ca` + `4f41c04`）

**侵入性：极低**
**Git 分支：`feature/misc-improvements`**

#### 10.1 日志级别配置

**为什么需要**：生产环境需要灵活控制日志级别，便于排查问题。0.6 添加了 `LOG_LEVEL` 环境变量支持。

0.7 已有自己的日志配置（`configure_logging()` 函数），但写死为 `ERROR` 级别。仅需微调：

| 文件 | 改动 | 说明 |
|------|------|------|
| `app.py` | ~5 行 | 在 `configure_logging()` 中读取 `LOG_LEVEL` 环境变量 |
| `.env.template` | +1 行 | 添加 `LOG_LEVEL=INFO` 示例 |

#### 10.2 MessageSnackbar 重构

**为什么需要**：0.6 中 Snackbar 逻辑散落在 App.tsx 中，抽离为组件自包含更合理。

需先确认 0.7 中 MessageSnackbar 是否已有类似重构。如已重构则跳过。如未重构：

| 文件 | 改动 |
|------|------|
| `App.tsx` | -10 行（移出 snackbar 状态管理） |
| `MessageSnackbar.tsx` | +20 行（组件自管理状态） |

---

### Phase 11：其他杂项

| 项目 | 来源 | 操作 |
|------|------|------|
| `docs/` SSO 文档、开发文档、快速开始 | 0.6 | 直接复制到 `docs/` |
| `.env.template` 中的 Superset + LOG_LEVEL 配置 | 0.6 | 合并到 0.7 的 .env.template |
| `api-keys-example.env` | 0.6 | 直接复制 |
| `.gitignore` 补充项 | 0.6 | 合并 |
| `local_server.bat/sh` | 0.6 | 如有自定义修改，合并 |
| `embed/` 嵌入模式 | 0.6 | 评估是否仍需要 |
| API 端口 5000 → 5567 | 0.7 变更 | 使用 0.7 的默认端口 5567 |

---

## 四、依赖变更清单

### Python (pyproject.toml)

| 变更 | 说明 |
|------|------|
| `requires-python` 3.9 → 3.11 | 0.7 要求 Python 3.11+ |
| 新增 `connectorx>=0.4.5` | 0.7 新增数据连接器 |
| 新增 `pyarrow>=23.0.0` | 0.7 新增 |
| `exec_python_in_subprocess` → `sandbox` | CLI 参数重命名 |
| 新增 `[tool.uv]` | 0.7 使用 uv 管理开发依赖 |

### Node.js (package.json)

| 变更 | 说明 |
|------|------|
| 新增 `echarts ^6.0.0` | 0.7 新图表引擎 |
| 新增 `chart.js ^4.5.1` | 0.7 新图表引擎 |
| 新增 `gofish-graphics ^0.0.22` | 0.7 新图表引擎 |
| 新增 `canvas ^3.2.1` | 0.7 图表渲染 |
| 新增 `js-yaml ^4.1.1` | 0.7 配置解析 |
| ~~i18next 系列~~ | **不再需要**（使用 Vite 插件替代） |
| ~~validator~~ | 0.7 已移除（@types/validator 保留在 devDeps） |

---

## 五、冲突风险矩阵（完整版）

| 文件 | 冲突风险 | 修改行数 | 涉及 Phase | 说明 |
|------|---------|---------|-----------|------|
| `vite.config.ts` | 🟢 极低 | +2 行 | 1 | 仅添加 i18n 插件 |
| `pyproject.toml` | 🟢 极低 | 0 行 | - | 不修改 |
| `package.json` | 🟢 极低 | 0 行 | - | 不再需要 i18n 依赖 |
| `py-src/.../app.py` | 🟡 低 | +20 行 | 2,6 | 扩展注入点 + 日志级别 |
| `src/app/App.tsx` | 🟡 低 | +8 行 | 4,5 | 懒加载 LoginView + SupersetCatalog |
| `src/app/dfSlice.tsx` | 🟡 低 | +12 行 | 8 | 末尾新增 updateColumnType reducer |
| `src/app/store.ts` | 🟢 极低 | +2 行 | 6 | 注册 modelSlice |
| `src/views/ModelSelectionDialog.tsx` | 🟡 中 | ~30 行 | 6 | 全局模型列表显示 |
| `src/views/SelectableDataGrid.tsx` | 🟡 中 | ~50 行 | 8 | 列类型修改 + 行号 |
| `src/views/DataView.tsx` | 🟢 极低 | +10 行 | 8 | 布局微调 |
| `src/views/DataLoadingThread.tsx` | 🟢 极低 | +10 行 | 7 | 图像模型警告 |
| `src/views/ReportView.tsx` | 🟢 极低 | ~15 行 | 9 | 多语言 + 字体 |
| `agent_data_rec.py` | 🟢 极低 | +2 行 | 7 | prompt 微调 |
| `agent_data_transform.py` | 🟢 极低 | +2 行 | 7 | prompt 微调 |
| `data_agent.py` | 🟢 极低 | +3 行 | 7 | ensure_ascii |
| `client_utils.py` | 🟢 极低 | +5 行 | 7 | vision compat |
| `agent_report_gen.py` | 🟢 极低 | +15 行 | 9 | 多语言报告 |
| `agent_routes.py` | 🟡 低 | +10 行 | 7,9 | CJK + 报告参数 |
| `.env.template` | 🟢 极低 | +3 行 | 11 | LOG_LEVEL + Superset |
| `src/views/*.tsx`（其余） | 🟢 零 | 0 行 | - | i18n 通过 Vite 插件 |
| 所有 `extensions/` 新增文件 | 🟢 零 | - | 全部 | 纯新增，无冲突 |

**总计侵入官方文件的改动**：约 **170 行**（分散在 ~15 个文件中），远小于 0.6 的 15,000+ 行改动。

---

## 六、实施顺序与时间估算（完整版）

| 阶段 | 任务 | 预估时间 | 依赖 | Git 分支 |
|------|------|---------|------|---------|
| **Phase 0** | Git 仓库初始化 + upstream 追踪 | 0.5h | 无 | `main` |
| **Phase 1** | i18n Vite 插件 + 翻译字典迁移 | 2-3 天 | Phase 0 | `feature/i18n-vite-plugin` |
| **Phase 2** | Superset 后端集成 + 扩展注入点 | 1-2 天 | Phase 0 | `feature/superset-integration` |
| **Phase 3** | 安全模块迁移 | 0.5 天 | Phase 0 | `feature/security` |
| **Phase 4** | 登录/SSO + authSlice | 1-2 天 | Phase 2 | `feature/auth-sso` |
| **Phase 5** | SupersetCatalog 前端 | 0.5-1 天 | Phase 2, 4 | `feature/auth-sso` |
| **Phase 6** | 模型管理系统 | 1-2 天 | Phase 2 | `feature/model-management` |
| **Phase 7** | Agent CJK 兼容 + 图像检测 | 1-2 天 | Phase 0 | `feature/agent-cjk-compat` |
| **Phase 8** | 表格功能增强 | 1 天 | Phase 2 | `feature/table-enhancements` |
| **Phase 9** | 报告生成增强 | 0.5 天 | Phase 0 | `feature/report-enhancements` |
| **Phase 10** | 日志 + 小改动 | 0.5 天 | Phase 0 | `feature/misc-improvements` |
| **Phase 11** | 杂项 + 集成测试 + 文档 | 1 天 | 全部 | `custom/release` |
| | **合计** | **10-15 天** | | |

---

## 七、未来升级流程（0.8, 0.9, ...）

每次官方发布新版本时：

```bash
# 1. 获取上游更新
git fetch upstream
git checkout main
git merge upstream/main   # 或对应的 tag

# 2. 逐个 rebase feature 分支（按优先级排序）
git checkout feature/i18n-vite-plugin
git rebase main
# 冲突概率：极低（仅 vite.config.ts 1-2 行）

git checkout feature/superset-integration
git rebase main
# 冲突概率：低（app.py 扩展注入点）

git checkout feature/model-management
git rebase main
# 冲突概率：低（独立 Blueprint + store.ts 2行）

git checkout feature/agent-cjk-compat
git rebase main
# 冲突概率：中（agent 文件可能被官方重构）

git checkout feature/table-enhancements
git rebase main
# 冲突概率：低-中（dfSlice reducer 位置可能移动）

git checkout feature/report-enhancements
git rebase main
# 冲突概率：低

git checkout feature/auth-sso
git rebase main
# 冲突概率：低

git checkout feature/misc-improvements
git rebase main
# 冲突概率：极低

# 3. 重新构建 release 分支
git checkout custom/release
git reset --hard main
git merge feature/i18n-vite-plugin
git merge feature/superset-integration
git merge feature/model-management
git merge feature/agent-cjk-compat
git merge feature/table-enhancements
git merge feature/report-enhancements
git merge feature/auth-sso
git merge feature/security
git merge feature/misc-improvements

# 4. 补充新版本的翻译
# - 运行字符串提取工具，找出新增未翻译字符串
# - 更新 src/i18n/locales/zh.json

# 5. 测试 + 发布
npm run build
pip install -e .
# 验证所有功能正常
```

预计每次升级耗时：**1-3 天**（主要是补充翻译、适配 agent 变更和解决少量冲突）

---

## 八、自定义代码目录结构总览（完整版）

```
data-formulator/                          # 0.7 官方代码
├── src/
│   ├── i18n/                             # [自定义] i18n 模块
│   │   ├── vite-plugin-i18n.ts           #   Vite 翻译插件
│   │   ├── translate.ts                  #   翻译核心逻辑
│   │   ├── extract-strings.ts            #   字符串提取工具
│   │   └── locales/
│   │       └── zh.json                   #   中文翻译字典
│   │
│   ├── extensions/                       # [自定义] 所有扩展模块
│   │   ├── auth/
│   │   │   ├── authSlice.ts              #   认证状态管理
│   │   │   ├── LoginView.tsx             #   登录视图
│   │   │   └── AuthProvider.tsx          #   认证 Provider
│   │   ├── superset/
│   │   │   └── SupersetCatalog.tsx       #   Superset 数据集目录
│   │   └── models/
│   │       ├── modelSlice.ts             #   全局模型状态
│   │       └── GlobalModelBadge.tsx      #   全局模型标记组件
│   │
│   ├── app/                              # [官方] 少量修改
│   │   ├── App.tsx                       #   +8 行（懒加载扩展组件）
│   │   ├── dfSlice.tsx                   #   +12 行（updateColumnType）
│   │   ├── store.ts                      #   +2 行（注册 modelSlice）
│   │   └── ...
│   ├── views/                            # [官方] 少量修改
│   │   ├── ModelSelectionDialog.tsx       #   ~30 行（全局模型显示）
│   │   ├── SelectableDataGrid.tsx        #   ~50 行（列类型 + 行号）
│   │   ├── DataLoadingThread.tsx         #   +10 行（图像模型警告）
│   │   ├── ReportView.tsx                #   ~15 行（多语言 + 字体）
│   │   ├── DataView.tsx                  #   +10 行（布局微调）
│   │   └── ...                           #   其余不修改
│   ├── components/                       # [官方] 不修改
│   └── lib/                              # [官方] 不修改
│
├── py-src/data_formulator/
│   ├── extensions/                       # [自定义] 后端扩展
│   │   ├── __init__.py
│   │   ├── register.py                   #   统一扩展注册入口
│   │   ├── model_registry.py             #   服务端全局模型配置
│   │   ├── model_routes.py               #   全局模型 API Blueprint
│   │   ├── table_ext_routes.py           #   表格追加/流式摄入 Blueprint
│   │   ├── cjk_compat.py                 #   CJK/非 ASCII 兼容补丁
│   │   └── vision_compat.py              #   纯文本模型图像处理
│   ├── superset/                         # [自定义] Superset 集成
│   │   ├── auth_bridge.py
│   │   ├── auth_routes.py
│   │   ├── catalog.py
│   │   ├── catalog_routes.py
│   │   ├── data_routes.py
│   │   └── superset_client.py
│   ├── security/                         # [自定义] 安全模块
│   │   └── query_validator.py
│   │
│   ├── app.py                            # [官方] +20 行（注入点 + 日志）
│   ├── agents/
│   │   ├── agent_data_rec.py             # [官方] +2 行（CJK prompt）
│   │   ├── agent_data_transform.py       # [官方] +2 行（CJK prompt）
│   │   ├── data_agent.py                 # [官方] +3 行（ensure_ascii）
│   │   ├── client_utils.py               # [官方] +5 行（vision compat）
│   │   ├── agent_report_gen.py           # [官方] +15 行（多语言）
│   │   └── ...                           #   其余不修改
│   ├── agent_routes.py                   # [官方] +10 行（CJK + 报告）
│   └── ...                               #   其余不修改
│
├── vite.config.ts                        # [官方] +2 行（i18n 插件）
├── .env.template                         # [官方] +3 行（配置项）
└── docs/                                 # [自定义] 文档
    ├── UPGRADE-PLAN.md
    ├── 0.6修改记录.md
    ├── Superset端SSO桥接端点配置指南.md
    └── 快速开始.md
```

**自定义代码统计**：
- 纯新增文件（extensions/ + i18n/ + docs/）：~20 个文件
- 修改官方文件：~15 个文件，合计约 170 行
- 对比 0.6：修改官方文件 40+ 个，合计 15,000+ 行

---

## 九、风险与注意事项

1. **Vite 插件的精确度**：简单字符串匹配可能误翻译变量名或代码。建议初版限制翻译范围（只翻译 JSX 文本和特定属性），后续迭代升级为 AST 版本。

2. **0.7 的 Identity 系统**：0.7 用 `getBrowserId()` 替代了 session，Superset SSO 需要在这个基础上叠加认证层，而非替换它。

3. **0.7 新增的 datalake 模块**：Superset 的数据加载可能需要适配 0.7 的 workspace/datalake 机制，而非直接写入 DuckDB。

4. **Python 版本**：0.7 要求 3.11+，确保生产环境满足要求。

5. **端口变更**：0.7 默认端口从 5000 改为 5567，需要更新部署配置。

6. **Agent 文件映射**：0.7 对 agent 做了大幅重构，0.6 中被修改的文件与 0.7 的对应关系如下（升级时务必参照）：

    | 0.6 文件 | 0.7 对应 | 状态 |
    |----------|---------|------|
    | `agent_sql_data_rec.py` | `agent_data_rec.py` | 合并，不再区分 sql/py |
    | `agent_sql_data_transform.py` | `agent_data_transform.py` | 合并 |
    | `agent_py_data_transform.py` | `agent_data_transform.py` | 合并 |
    | `agent_py_data_rec.py` | `agent_data_rec.py` | 合并 |
    | `agent_exploration.py` | `data_agent.py` 或已删除 | 功能整合 |
    | `agent_py_concept_derive.py` | 已删除 | 0.7 移除 |
    | `agent_concept_derive.py` | 已删除 | 0.7 移除 |
    | `agent_data_clean.py` | 已删除 | 0.7 移除 |
    | `model_registry.py` | 不存在 | 0.7 无此功能 |
    | `db_manager.py` | 已删除 | 0.7 用 datalake/ 替代 |
    | `py_sandbox.py` | `sandbox/` 模块 | 拆分为目录 |

7. **模型管理系统**：0.7 目前无全局模型管理功能。如果官方未来版本加入类似功能，可能需要评估是继续使用自定义版还是切换到官方实现。

---

## 十、验证清单

完成升级后，逐项验证：

### 基础功能
- [ ] 数据上传（CSV/TSV/JSON/Excel）
- [ ] 图表生成（Vega-Lite + 0.7 新增的 ECharts/Chart.js）
- [ ] AI 对话与数据探索
- [ ] 0.7 新功能：ChartGallery、datalake 持久化、workspace 保存/加载

### i18n（Phase 1）
- [ ] `VITE_LANG=zh npm run build` 后 UI 全部显示中文
- [ ] 英文构建无翻译残留
- [ ] 0.7 新增组件（ChartGallery 等）也被翻译

### Superset 集成（Phase 2-5）
- [ ] `--superset-url` / `SUPERSET_URL` 参数正常工作
- [ ] SSO 登录流程正常
- [ ] 数据集目录加载正常
- [ ] LoginView 条件渲染正确（未配置 Superset 时不显示）

### 安全模块（Phase 3）
- [ ] query_validator 在 0.7 的 sandbox 机制下正常工作

### 模型管理（Phase 6）
- [ ] 环境变量配置的全局模型在前端可见
- [ ] 全局模型的 API key 不暴露到前端
- [ ] 用户本地添加的模型与全局模型共存
- [ ] 使用全局模型执行数据转换正常

### Agent CJK 兼容（Phase 7）
- [ ] 中文表名的 SQL 查询正常执行
- [ ] 中文列名在数据转换 prompt 中正确显示（非 \uXXXX）
- [ ] 纯文本模型（如 deepseek-chat）发送含图片请求时自动回退
- [ ] 前端显示"模型可能不支持图像"警告

### 表格增强（Phase 8）
- [ ] `/api/tables/append-table` 端点正常工作
- [ ] `/api/tables/stream-ingest` 端点正常工作
- [ ] 表头右键可修改列类型
- [ ] 行号列正确显示
- [ ] 数值列右对齐 + 千位分隔符

### 报告生成（Phase 9）
- [ ] 中文环境下生成中文报告
- [ ] 自定义规则正确传递到报告 prompt
- [ ] 执行摘要字体显示正常

### 其他（Phase 10-11）
- [ ] `LOG_LEVEL` 环境变量生效
- [ ] 构建：`npm run build` + `pip install -e .` 正常
- [ ] 生产：`data_formulator` 命令正常启动
