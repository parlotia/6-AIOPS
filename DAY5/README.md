# AIOps DAY5 作业 —— ModelScope 下载模型 + vLLM 推理服务

## 一、作业背景

DAY4 使用 Ollama（独立二进制）快速体验了本地模型推理。DAY5 进入**推理服务化**：
- 通过 **ModelScope（魔塔社区）** 下载开源模型权重到本地
- 使用 **vLLM** 将模型启动为标准 OpenAI 兼容 HTTP API 服务
- 客户端通过 OpenAI SDK 调用，验证"本地权重 → 稳定 HTTP 服务"的闭环

## 二、实验环境

| 项目 | 配置 |
|------|------|
| 云平台 | 阿里云 GPU 实例 |
| 公网 IP | `8.160.176.138` |
| 操作系统 | Alibaba Cloud Linux 3 (OpenAnolis Edition) |
| GPU | NVIDIA A10（23028 MiB VRAM） |
| CUDA | 13.0（Driver 580.126.09） |
| Python | 3.11.7（**源码编译安装**，见踩坑记录） |
| vLLM | 0.22.0 |
| 模型 | Qwen/Qwen3-4B-Instruct-2507（7.6 GB，3 个 safetensors 分片） |
| 服务端口 | 8000 |
| GPU 占用 | ~19355 MiB / 23028 MiB（约 84%） |

## 三、项目结构

```
homework/6.AIOps/DAY5/
├── README.md                 # 本文档
└── test_vllm_qwen3.py        # 客户端测试脚本（OpenAI SDK 调用 vLLM）
```

服务器端结构：
```
/AIOPS2026/
├── .venv-vllm/               # vLLM 服务端虚拟环境
└── .venv/                    # 客户端虚拟环境（modelscope、openai）

/data/modelscope/
├── models/Qwen/Qwen3-4B-Instruct-2507/   # 模型权重目录
│   ├── config.json
│   ├── generation_config.json
│   ├── tokenizer.json / tokenizer_config.json
│   ├── model-00001-of-00003.safetensors
│   ├── model-00002-of-00003.safetensors
│   └── model-00003-of-00003.safetensors
└── cache/                    # ModelScope 下载缓存
```

## 四、数据流架构

```
┌─────────────┐    OpenAI SDK     ┌──────────────────────────────┐
│  本地客户端  │ ──HTTP POST──→  │  阿里云 GPU 服务器            │
│ test_vllm_   │   /v1/chat/      │  vLLM 0.22.0                 │
│ qwen3.py    │   completions    │  ├─ Qwen3-4B-Instruct-2507   │
│             │ ←──JSON 响应─── │  ├─ NVIDIA A10 (23GB)        │
└─────────────┘                  │  └─ :8000                     │
                                 └──────────────────────────────┘
```

## 五、完整操作步骤

### 步骤 1：安装 Python 3.11（源码编译）

> **⚠️ 踩坑**：Alibaba Cloud Linux 3 的 yum 只有 Python 3.6.8，Miniconda 下载链接失效。
> 最终从 npmmirror.com 下载 Python 3.11.7 源码编译。

```bash
# 安装编译依赖
yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel wget make

# 下载 Python 3.11.7 源码（npmmirror 镜像）
cd /usr/local/src
wget https://npmmirror.com/mirrors/python/3.11.7/Python-3.11.7.tgz
tar -xzf Python-3.11.7.tgz

# 编译安装（约 5-10 分钟）
cd Python-3.11.7
./configure --enable-optimizations --prefix=/usr/local/python3.11
make -j$(nproc)
make altinstall

# 验证
/usr/local/python3.11/bin/python3.11 --version
# Python 3.11.7
```

### 步骤 2：安装 uv（超快包管理器）

> **⚠️ 踩坑**：pip 安装 vLLM 的 2GB+ 依赖极其缓慢（~1MB/s），261MB 的 vLLM 主包从 PyPI 下载卡死。
> 阿里云镜像对大包 CDN 缓存不全，Docker pull vllm/vllm-openai 也失败。
> **解决方案**：使用 `uv`（Rust 编写），并行下载速度提升 10-100 倍。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv --version
# uv 0.11.21
```

### 步骤 3：创建虚拟环境 + 安装 vLLM

```bash
# 创建 vLLM 专用虚拟环境
/usr/local/python3.11/bin/python3.11 -m venv /AIOPS2026/.venv-vllm

# 用 uv 安装 vLLM（几分钟搞定，pip 需要 1 小时+）
export PATH=$HOME/.local/bin:$PATH
uv pip install vllm==0.22.0 \
  --python /AIOPS2026/.venv-vllm/bin/python \
  --index-url https://mirrors.aliyun.com/pypi/simple/ \
  --allow-insecure-host mirrors.aliyun.com

# 验证
source /AIOPS2026/.venv-vllm/bin/activate
which vllm        # /AIOPS2026/.venv-vllm/bin/vllm
vllm --version    # 0.22.0
```

### 步骤 4：创建客户端虚拟环境 + 安装 ModelScope

```bash
/usr/local/python3.11/bin/python3.11 -m venv /AIOPS2026/.venv
source /AIOPS2026/.venv/bin/activate
pip install openai modelscope
```

### 步骤 5：通过 ModelScope 下载模型

> **⚠️ 注意**：老师文档用 HuggingFace 下载到 `/data/huggingface/models/`，
> 国内环境用 ModelScope 下载到 `/data/modelscope/models/` 更稳定（实测 175 MB/s）。

```bash
# 创建目录
mkdir -p /data/modelscope/models /data/modelscope/cache

# 下载模型（约 30 秒，175 MB/s）
source /AIOPS2026/.venv/bin/activate
python3 -c "
from modelscope import snapshot_download
model_id = 'Qwen/Qwen3-4B-Instruct-2507'
local_dir = snapshot_download(
    model_id=model_id,
    cache_dir='/data/modelscope/cache',
    local_dir='/data/modelscope/models/Qwen/Qwen3-4B-Instruct-2507',
)
print('下载完成:', local_dir)
"

# 验证
ls /data/modelscope/models/Qwen/Qwen3-4B-Instruct-2507/
du -sh /data/modelscope/models/Qwen/Qwen3-4B-Instruct-2507/
# 7.6G
```

### 步骤 6：启动 vLLM 推理服务

```bash
cd /AIOPS2026
source /AIOPS2026/.venv-vllm/bin/activate
export PYTORCH_ALLOC_CONF=expandable_segments:True

vllm serve "/data/modelscope/models/Qwen/Qwen3-4B-Instruct-2507" \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name qwen3-4b \
  --gpu-memory-utilization 0.85 \
  --max-model-len 10000 \
  --tensor-parallel-size 1 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --reasoning-parser qwen3
```

启动成功后终端会显示：
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

| 参数 | 说明 |
|------|------|
| `--port 8000` | 服务端口 |
| `--served-model-name qwen3-4b` | OpenAI API 中的 `model` 字段 |
| `--gpu-memory-utilization 0.85` | GPU 显存使用上限 85% |
| `--max-model-len 10000` | 最大上下文长度 |
| `--enable-auto-tool-choice` | 启用工具调用解析 |
| `--tool-call-parser hermes` | 使用 Hermes 格式解析 tool_calls |
| `--reasoning-parser qwen3` | Qwen3 thinking 与 content 分离 |

### 步骤 7：客户端测试

本地运行测试脚本：
```bash
python test_vllm_qwen3.py
```

或通过 curl 测试：
```bash
curl http://8.160.176.138:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-4b",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 200
  }'
```

## 六、踩坑记录

### 坑 1：系统 Python 版本太低

| 问题 | 说明 |
|------|------|
| 现象 | Alibaba Cloud Linux 3 自带 Python 3.6.8，vLLM 需要 Python ≥ 3.9 |
| 尝试 | Miniconda 下载（清华/阿里云镜像均返回空文件） |
| 解决 | 从 npmmirror.com 下载 Python 3.11.7 源码编译，安装到 `/usr/local/python3.11/` |

### 坑 2：pip 安装 vLLM 极慢

| 问题 | 说明 |
|------|------|
| 现象 | vLLM 依赖总量超过 2GB（torch 530MB、vllm 261MB、cuDNN 366MB、flashinfer 360MB、triton 201MB 等），pip 从 PyPI 下载速度仅 ~1MB/s |
| 尝试 | 阿里云镜像（元数据快但大包 CDN 仍走 PyPI，261MB 的 vllm 轮子卡死）、Docker pull vllm/vllm-openai（连接失败） |
| 解决 | 安装 `uv`（Rust 包管理器），并行下载 + 更快 CDN，几分钟装完 |

### 坑 3：Qwen3 模型默认开启 thinking 模式

| 问题 | 说明 |
|------|------|
| 现象 | API 返回的 `content` 字段为 `null`，回答内容出现在 `reasoning` 字段 |
| 原因 | Qwen3 系列模型默认启用 thinking/reasoning 模式 |
| 解决 | 客户端请求添加 `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` |

### 坑 4：模型路径与老师文档不同

| 问题 | 说明 |
|------|------|
| 现象 | 老师文档模型路径是 `/data/huggingface/models/...` |
| 原因 | 老师从 HuggingFace 下载，我们从 ModelScope 下载 |
| 解决 | vLLM 启动时使用 ModelScope 路径 `/data/modelscope/models/Qwen/Qwen3-4B-Instruct-2507` |

### 坑 5：阿里云安全组放行端口

| 问题 | 说明 |
|------|------|
| 现象 | 外网无法访问 8000 端口 |
| 解决 | 阿里云控制台 → 安全组 → 添加入方向规则：TCP 8000 端口，授权对象 0.0.0.0/0 |

## 七、提交文件清单

| 文件 | 说明 |
|------|------|
| `README.md` | 本文档 |
| `test_vllm_qwen3.py` | 客户端测试脚本 |

## 八、截图清单（需手动完成）

| 截图 | 内容 |
|------|------|
| 1 | `nvidia-smi` 显示 GPU 型号和显存占用 |
| 2 | vLLM 启动终端（`Application startup complete`） |
| 3 | `ss -tlnp \| grep 8000` 端口监听 |
| 4 | 客户端运行 `test_vllm_qwen3.py` 的输出结果 |
| 5 | ModelScope 下载完成的终端输出 |
