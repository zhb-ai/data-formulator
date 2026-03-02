# DF（Data Formulator）Python 环境启动指南（非 Docker）

> 适用于：`e:\GPT\superset` 当前项目结构  
> 目标：不使用 Docker，直接在 Python 虚拟环境中启动 DF，并可按需接入任意 AI 模型服务。  
> 本指南默认本地开发；生产请参考非 Docker 部署文档并使用独立内部 token。

---

## 1. 适用目录与启动目标

你当前涉及两个仓库：

- `\data-formulator`：Data Formulator 修改后的源码
- `\superset-df-integration`：Gateway 集成层

推荐启动顺序（非 Docker）：

1. 创建 `api-keys.env`，填入模型配置（一次性操作）
2. 启动 Data Formulator
3. （可选）启动 Gateway 后端/前端做联调

---

## 2. 前置要求

- Python 3.11+
- PowerShell（Windows）
- Node.js 18+（仅在你需要启动 `gateway-frontend` 时）
- （可选）Superset：`http://localhost:8088`

建议先声明工作目录变量，后续命令统一使用：

```powershell
$WORKSPACE = "e:\GPT\superset"
```

---

## 3. 启动 DF

```powershell
cd $WORKSPACE\data-formulator

# 1) 创建并激活 Conda 环境（首次）
conda create -n data-formulator python=3.11
conda activate data-formulator

# 2) 安装本地源码（开发模式，首次或代码有改动时执行）
pip install -e .

# 3) 启动 DF
python -m data_formulator --port 5000
```

访问：`http://127.0.0.1:5000`

> 如果 5000 被占用：`python -m data_formulator --port 5001`

---

## 4. 配置模型（核心）

DF 启动时会自动加载 `data-formulator/api-keys.env`。**所有模型的 API Key 仅存在服务端，不会发送到浏览器前端。**

前端打开后，模型选择面板会自动显示所有已配置的模型，并以绿色（可连接）/ 红色（无法连接）标识连通状态。

### 4.1 配置文件位置

```
data-formulator/
└── api-keys.env          ← 放这里，DF 自动加载，优先级最高
```

> 这个文件已在 `.gitignore` 中，不会被提交到 Git。

### 4.2 配置格式说明

每个模型服务商用一组独立的环境变量配置，**变量名前缀可以自由命名**（只要全大写即可），不需要改任何代码。

| 变量名 | 必填 | 说明 |
|---|---|---|
| `{NAME}_ENABLED` | ✅ | `true` 表示启用此服务商 |
| `{NAME}_ENDPOINT` | ✅ | 调用类型：OpenAI 兼容填 `openai`；内置厂商（anthropic/gemini 等）可省略 |
| `{NAME}_API_KEY` | ✅ | 该服务商的 API 密钥 |
| `{NAME}_API_BASE` | 视情况 | API 地址（官方 OpenAI 可省略，其他一般都要填） |
| `{NAME}_API_VERSION` | ❌ | 仅 Azure 需要 |
| `{NAME}_MODELS` | ✅ | 模型名称，多个用英文逗号分隔 |

### 4.3 当前配置（DeepSeek + Qwen）

```ini
# data-formulator/api-keys.env

# DeepSeek（OpenAI 兼容格式）
DEEPSEEK_ENABLED=true
DEEPSEEK_ENDPOINT=openai
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODELS=deepseek-chat

# 阿里云百炼 / Qwen（OpenAI 兼容格式）
QWEN_ENABLED=true
QWEN_ENDPOINT=openai
QWEN_API_KEY=你的阿里云API密钥
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODELS=qwen3-omni-flash
```

### 4.4 添加更多模型服务商（无需改代码）

只要服务商支持 OpenAI 兼容接口（`/v1/chat/completions`），照下面格式追加即可，**前缀名随意取**：

**示例：添加 Moonshot（月之暗面）**

```ini
MOONSHOT_ENABLED=true
MOONSHOT_ENDPOINT=openai
MOONSHOT_API_KEY=sk-你的moonshot密钥
MOONSHOT_API_BASE=https://api.moonshot.cn/v1
MOONSHOT_MODELS=moonshot-v1-8k,moonshot-v1-32k
```

**示例：添加 Groq（超高速推理）**

```ini
GROQ_ENABLED=true
GROQ_ENDPOINT=openai
GROQ_API_KEY=gsk_你的groq密钥
GROQ_API_BASE=https://api.groq.com/openai/v1
GROQ_MODELS=llama-3.3-70b-versatile,mixtral-8x7b-32768
```

**示例：添加 OpenAI 官方**

```ini
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-你的openai密钥
OPENAI_MODELS=gpt-4o,gpt-4o-mini
```

> `openai` 是内置厂商，省略 `OPENAI_ENDPOINT` 和 `OPENAI_API_BASE`（使用官方地址）。

**示例：内网自建 / vLLM / Ollama 等**

```ini
# vLLM 自建
VLLM_ENABLED=true
VLLM_ENDPOINT=openai
VLLM_API_KEY=any-key
VLLM_API_BASE=http://你的vllm地址:8000/v1
VLLM_MODELS=Qwen2.5-72B-Instruct

# Ollama 本地（内置厂商）
OLLAMA_ENABLED=true
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODELS=llama3.2,qwen2.5
```

**示例：Anthropic Claude（内置厂商）**

```ini
ANTHROPIC_ENABLED=true
ANTHROPIC_API_KEY=sk-ant-你的密钥
ANTHROPIC_MODELS=claude-3-5-sonnet-20241022,claude-3-haiku-20240307
```

**示例：Google Gemini（内置厂商）**

```ini
GEMINI_ENABLED=true
GEMINI_API_KEY=AIza你的密钥
GEMINI_MODELS=gemini-2.0-flash,gemini-1.5-pro
```

**示例：Azure OpenAI（内置厂商）**

```ini
AZURE_ENABLED=true
AZURE_API_KEY=你的azure密钥
AZURE_API_BASE=https://你的资源名.openai.azure.com
AZURE_API_VERSION=2025-04-01-preview
AZURE_MODELS=gpt-4o,gpt-4o-mini
```

### 4.5 同一服务商配置多组接入点

如果你需要同一厂商的两个不同账号/地区，直接用不同前缀即可：

```ini
DEEPSEEK_PROD_ENABLED=true
DEEPSEEK_PROD_ENDPOINT=openai
DEEPSEEK_PROD_API_KEY=sk-生产账号密钥
DEEPSEEK_PROD_API_BASE=https://api.deepseek.com
DEEPSEEK_PROD_MODELS=deepseek-chat

DEEPSEEK_TEST_ENABLED=true
DEEPSEEK_TEST_ENDPOINT=openai
DEEPSEEK_TEST_API_KEY=sk-测试账号密钥
DEEPSEEK_TEST_API_BASE=https://api.deepseek.com
DEEPSEEK_TEST_MODELS=deepseek-reasoner
```

### 4.6 配置生效

修改 `api-keys.env` 后，**重启 DF** 即可生效：

```powershell
# Ctrl+C 停止当前 DF，然后重启
python -m data_formulator --port 5000
```

重启后，浏览器打开模型选择面板，所有配置的模型都会显示（含连通状态）。

---

## 5. （可选）通过 LiteLLM Proxy 中转

如果你希望通过统一网关中转所有模型请求（例如做日志审计、限速、多租户），也可以继续使用 LiteLLM Proxy，然后在 `api-keys.env` 里只配置一个 `OPENAI_*` 指向本地代理：

```ini
# 走 LiteLLM Proxy
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-litellm-master-key-2024
OPENAI_API_BASE=http://127.0.0.1:4000/v1
OPENAI_MODELS=deepseek-chat,qwen3-omni-flash
```

启动 LiteLLM Proxy：

```powershell
cd $WORKSPACE\superset-df-integration
pip install "litellm[proxy]"
litellm --config "config\litellm_config.runtime.yaml" --host 127.0.0.1 --port 4000
```

健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:4000/health -UseBasicParsing
```

---

## 6. 与 `superset-df-integration` 联调（可选）

检查 `e:\GPT\superset\superset-df-integration\.env`：

```ini
SUPERSET_URL=http://localhost:8088
DF_URL=http://127.0.0.1:5000
LLM_API_KEY=你的密钥
LLM_BASE_URL=http://127.0.0.1:4000/v1
LLM_MODEL=deepseek-chat
```

启动 Gateway：

```powershell
# 终端 C：Gateway 后端
cd $WORKSPACE\superset-df-integration\gateway-service
conda activate gateway-service
python run.py

# 终端 D：Gateway 前端（开发模式）
cd $WORKSPACE\superset-df-integration\gateway-frontend
npm run dev
```

访问：

- Gateway 前端：`http://localhost:3001`
- DF：`http://127.0.0.1:5000`
- Superset：`http://localhost:8088`

---

## 7. 常见问题

### 7.1 前端模型面板打开后显示"无法连接"（红色）

这是正常现象——模型已配置，但连接测试失败。按以下步骤排查：

**① 直接调用后端接口查看详细状态**

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/agent/check-available-models" `
  -Method POST -Body '{"token":1}' -ContentType "application/json" `
  -UseBasicParsing | Select-Object -ExpandProperty Content
```

返回示例：
```json
[
  {
    "id": "global-deepseek-deepseek-chat",
    "endpoint": "openai",
    "model": "deepseek-chat",
    "status": "disconnected",
    "error": "Connection timeout"
  }
]
```

`status: "disconnected"` + `error` 字段会告诉你具体原因。

**② 常见错误原因**

| 现象 | 原因 |
|---|---|
| `Connection timeout` / `Connection refused` | 网络不通，或 API 地址填错 |
| `401 Unauthorized` | API Key 错误或已过期 |
| 返回 `[]`（空数组） | `api-keys.env` 没被读到，检查文件路径和 `_ENABLED=true` |
| 重启后仍无变化 | 文件可能有 BOM 或编码问题，用 UTF-8（无 BOM）保存 |

### 7.2 配置了模型但前端列表为空

```powershell
# 确认 DF 读到了配置
Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/agent/check-available-models" `
  -Method POST -Body '{"token":1}' -ContentType "application/json" `
  -UseBasicParsing | Select-Object -ExpandProperty Content
```

- 返回 `[]`：`api-keys.env` 未被加载。确认文件在 `data-formulator/api-keys.env`，且对应 `{NAME}_ENABLED=true`，然后**重启 DF**。
- 返回有内容但前端不显示：强制刷新浏览器（`Ctrl+Shift+R`）。

### 7.3 Windows 下 PowerShell 设环境变量后无效

推荐直接用 `api-keys.env` 文件，不要用临时环境变量。若一定要用临时变量：

```powershell
# PowerShell
$env:DEEPSEEK_ENABLED = "true"
$env:DEEPSEEK_API_KEY  = "sk-..."
```

```cmd
:: CMD（Conda 激活后默认）
set DEEPSEEK_ENABLED=true
set DEEPSEEK_API_KEY=sk-...
```

> `$env:` 语法只在 PowerShell 中有效；Conda 激活后是 cmd.exe，应使用 `set`。

### 7.4 端口冲突

```powershell
netstat -ano | findstr :5000
netstat -ano | findstr :4000
```

改端口或结束冲突进程后重试。

### 7.5 Windows 下 LiteLLM 编码报错

若出现 `UnicodeDecodeError (gbk)`，使用：

```
config/litellm_config.runtime.yaml
```

不要使用含非 ASCII 内容的配置文件。

---

## 8. 停止服务与退出环境

- 停止 DF：在对应终端按 `Ctrl+C`
- 退出虚拟环境：`conda deactivate`

---

## 9. 一键回顾（最短路径）

1. `conda create -n data-formulator python=3.11 && conda activate data-formulator`
2. `cd data-formulator && pip install -e .`
3. 创建 `data-formulator/api-keys.env`，填入至少一个模型（见第 4 节）
4. `python -m data_formulator --port 5000`
5. 浏览器打开 `http://127.0.0.1:5000`，点击模型选择按钮，绿色的即可使用
