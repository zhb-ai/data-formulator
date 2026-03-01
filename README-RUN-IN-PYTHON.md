# DF（Data Formulator）Python 环境启动指南（非 Docker）

> 适用于：`e:\GPT\superset` 当前项目结构  
> 目标：不使用 Docker，直接在 Python 虚拟环境中启动 DF，并可按需接入 LiteLLM / Gateway。  
> 本指南默认本地开发；生产请参考非 Docker 部署文档并使用独立内部 token。

---

## 1. 适用目录与启动目标

你当前涉及两个仓库：

- `\data-formulator`：Data Formulator 修改后的源码
- `\superset-df-integration`：Gateway 集成层

推荐启动顺序（非 Docker）：

1. 启动 LiteLLM Proxy（如需 AI 功能和密钥隔离）
2. 启动 Data Formulator（Python）
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

## 3. 启动 DF（最小可用，不接 LiteLLM）

先确认 DF 本体可运行。

```powershell
cd $WORKSPACE\data-formulator

# 1) 创建并激活 Conda 环境（推荐）
conda create -n data-formulator python=3.11
conda activate data-formulator

# 2) 安装本地源码（开发模式）
pip install -e .

# 3) 启动 DF
python -m data_formulator --port 5000
```

访问：

- `http://127.0.0.1:5000`

> 如果 5000 被占用，可改为：`python -m data_formulator --port 5001`

---

## 4. 推荐方式：DF + LiteLLM（非 Docker）

如果你不希望在浏览器端暴露真实厂商 Key，建议按此方案。

### 4.1 终端 A：启动 LiteLLM Proxy

```powershell
cd $WORKSPACE\superset-df-integration

# 首次安装（建议在单独 venv 内）
pip install "litellm[proxy]"

# 按你的实际情况填写
$env:QWEN_API_KEY="<你的QwenKey>"
$env:QWEN_API_BASE="http://<你的vllm地址>:8000/v1"
$env:DEEPSEEK_API_KEY="<你的DeepSeekKey>"
$env:LITELLM_MASTER_KEY="sk-litellm-master-local"

# 使用 runtime 配置，避免 Windows 下可能的编码问题
litellm --config "config\litellm_config.runtime.yaml" --host 127.0.0.1 --port 4000
```

健康检查（新开终端）：

```powershell
Invoke-WebRequest http://127.0.0.1:4000/health -UseBasicParsing
```

### 4.2 终端 B：启动 DF（指向 LiteLLM）

`OPENAI_API_KEY` 推荐按场景区分：

- 快速验证：可先使用 `LITELLM_MASTER_KEY`，方便快速联通
- 正式使用：改为 LiteLLM 生成的 `virtual/internal key`（最小权限，推荐）

```powershell
cd $WORKSPACE\data-formulator
conda activate data-formulator

$env:OPENAI_ENABLED="true"
$env:OPENAI_API_KEY="sk-litellm-master-local"
$env:OPENAI_API_BASE="http://127.0.0.1:4000/v1"
$env:OPENAI_MODELS="qwen3-14b,deepseek-chat"

python -m data_formulator --port 5000
```

访问：

- `http://127.0.0.1:5000`

---

## 5. 与 `superset-df-integration` 联调（可选）

如果你要让 Gateway 连接本地 DF，请检查：

`e:\GPT\superset\superset-df-integration\.env`

```ini
SUPERSET_URL=http://localhost:8088
DF_URL=http://127.0.0.1:5000

# Gateway AI 走 LiteLLM（可选但推荐）
LLM_API_KEY=sk-litellm-master-local
LLM_BASE_URL=http://127.0.0.1:4000/v1
LLM_MODEL=qwen3-14b
```

然后按需启动 Gateway：

```powershell
# 终端 C：Gateway 后端
cd $WORKSPACE\superset-df-integration\gateway-service
conda create -n gateway-service python=3.11
conda activate gateway-service
pip install -r requirements.txt
python run.py
```

```powershell
# 终端 D：Gateway 前端（开发模式）
cd $WORKSPACE\superset-df-integration\gateway-frontend
npm install
npm run dev
```

访问（开发模式）：

- Gateway 前端：`http://localhost:3001`
- DF：`http://127.0.0.1:5000`
- Superset：`http://localhost:8088`

---

## 6. 常见问题

### 6.1 Windows 下 LiteLLM 编码报错

若出现 `UnicodeDecodeError (gbk)`，请使用：

- `config/litellm_config.runtime.yaml`

不要用含非 ASCII 内容的配置文件。

### 6.2 端口冲突

```powershell
netstat -ano | findstr :5000
netstat -ano | findstr :4000
```

然后更换端口或结束冲突进程。

### 6.3 LiteLLM 只允许本机访问

保持：

```bash
--host 127.0.0.1
```

这是本地非 Docker 场景下的重要安全建议。

---

## 7. 停止服务与退出环境

- 停止 DF / LiteLLM：在对应终端按 `Ctrl+C`
- 退出虚拟环境：执行 `deactivate`

---

## 8. 一键回顾（最短路径）

1. `data-formulator` 建 Conda 环境 + `pip install -e .`
2. 启动 LiteLLM：`127.0.0.1:4000`
3. 设置 DF 的 `OPENAI_API_BASE=http://127.0.0.1:4000/v1`
4. `python -m data_formulator --port 5000`
5. 浏览器打开 `http://127.0.0.1:5000`

以上流程即可在 **不使用 Docker** 的前提下稳定运行 DF，并保留 AI 密钥隔离能力。
