# AIOps DAY7 作业 —— RagFlow RAG 知识库搭建与智能问答

## 一、作业背景

DAY5 使用 vLLM 部署基座模型，DAY6 使用 LlamaFactory 微调 Qwen3-4B。DAY7 进入 **RAG（检索增强生成）** 领域：

- 部署 **RagFlow v0.26.0** 开源 RAG 引擎（Docker Compose 编排 5 大服务）
- 复用 DAY6 微调的 **Qwen3-4B** 作为 LLM 后端（vLLM :8000）
- 额外部署 **bge-m3** Embedding 模型（vLLM :8001）完成文档向量化
- 上传个人知识库 Markdown 文档，RagFlow 自动完成 **切片 → Embedding → 索引**
- 通过 HTTP API 创建聊天助手，实现**基于知识库的精准问答**

> **核心思路**：RAG = 检索（Retrieval）+ 生成（Generation）。先从知识库中检索相关文档片段，再交给 LLM 生成回答，既保证准确性又避免幻觉。

## 二、实验环境

| 项目 | 配置 |
|------|------|
| 云平台 | 阿里云 GPU 实例 |
| 公网 IP | `8.160.166.64` |
| 操作系统 | Alibaba Cloud Linux 3 (OpenAnolis Edition) |
| GPU | NVIDIA A10（24564 MiB VRAM） |
| Python | 3.11（源码编译安装） |
| RagFlow | v0.26.0（Docker Compose 部署） |
| LLM 后端 | vLLM + Qwen3-4B-Instruct 微调模型（DAY6 产出） |
| Embedding 后端 | vLLM + BAAI/bge-m3（ModelScope 下载） |
| 向量数据库 | Elasticsearch 8.11.3 |
| 对象存储 | MinIO（pgsty/minio） |
| 关系数据库 | MySQL 8.0.39 |
| 缓存 | Valkey/Redis 8 |
| Docker 镜像源 | 华为云（RagFlow）+ Docker Hub 加速器（其余服务） |

## 三、项目结构

### 本地文件

```
homework/6.AIOps/DAY7/
├── README.md              # 本文档（详细实验说明）
├── knowledge_base.md      # 个人知识库文档（16个知识点，约3KB）
├── setup_ragflow.sh       # 服务器 RagFlow 一键部署脚本
└── test_ragflow.py        # 客户端 API 测试脚本（7步端到端）
```

### 服务器端结构

```
/opt/ragflow/                          # RagFlow 源码
├── docker/
│   ├── docker-compose.yml             # 主编排文件（含 profiles）
│   ├── docker-compose-base.yml        # 基础设施编排（ES/MySQL/MinIO/Redis）
│   ├── service_conf.yaml.template     # 服务配置模板
│   └── .env                           # 环境变量（端口/密码/镜像）

/AIOPS2026/                            # DAY5/6 遗留环境
├── .venv-vllm/                        # vLLM 虚拟环境
└── .venv/                             # 客户端虚拟环境

/data/
├── modelscope/models/
│   ├── Qwen/Qwen3-4B-Instruct-2507/   # 基座模型（DAY5）
│   └── BAAI/bge-m3/                   # Embedding 模型（DAY7 下载）
└── fine_tune/llama_factory/qwen3/     # DAY6 微调产出

Docker 容器（5个）:
├── docker-ragflow-cpu-1   → RagFlow 主服务   :80, :443, :9380-9384
├── docker-es01-1          → Elasticsearch     :1200
├── docker-mysql-1         → MySQL             :5455
├── docker-minio-1         → MinIO             :9000, :9001
└── docker-redis-1         → Redis             :6379

宿主机进程（2个）:
├── vLLM Chat Server       → :8000  (llama_factory_qwen3_finetune, GPU 70%)
└── vLLM Embed Server      → :8001  (bge-m3, GPU 20%)
```

## 四、系统架构

### 4.1 RAG 数据流

```
                          ┌─────────────────────────────────────────────────┐
                          │              阿里云 GPU 服务器 8.160.166.64       │
                          │                                                 │
┌──────────────┐  上传    │  ┌───────────────────────────────────────────┐  │
│ knowledge_   │ ───────→ │  │           RagFlow RAG 引擎 (:80/:9380)    │  │
│ base.md      │  HTTP    │  │                                           │  │
│ (16个知识点)  │  API     │  │  ① 文档解析 (DeepDOC Layout Recognize)   │  │
└──────────────┘          │  │  ② 智能切片 (Naive Chunking, 512 tokens)  │  │
                          │  │  ③ 向量化 ──────→ vLLM bge-m3 (:8001)    │  │
                          │  │  ④ 存储索引 ────→ Elasticsearch (:1200)  │  │
                          │  └───────────────┬───────────────────────────┘  │
                          │                  │                              │
                          │                  │ 用户提问                      │
                          │                  ▼                              │
                          │  ┌───────────────────────────────────────────┐  │
                          │  │          Chat Assistant 聊天助手           │  │
                          │  │                                           │  │
                          │  │  ⑤ 向量检索 ────→ Elasticsearch (:1200)  │  │
                          │  │  ⑥ Prompt 组装  (system + knowledge + query)│ │
                          │  │  ⑦ LLM 生成 ──→ vLLM Qwen3-4B (:8000)   │  │
                          │  │  ⑧ 附带引用   ([ID:n] 标注来源)           │  │
                          │  └───────────────┬───────────────────────────┘  │
                          └──────────────────┼──────────────────────────────┘
                                             │
┌──────────────┐  POST    JSON 响应          │
│ test_ragflow │ ←───────────────────────────┘
│ .py          │  /api/v1/chat/completions
└──────────────┘
```

### 4.2 GPU 显存分配

```
NVIDIA A10 (24564 MiB 总计)
┌───────────────────────────────────────────────────────┐
│  vLLM Chat Server (Qwen3-4B)        ~17.2 GiB (70%)  │
├───────────────────────────────────────────────────────┤
│  vLLM Embed Server (bge-m3)          ~4.9 GiB (20%)  │
├───────────────────────────────────────────────────────┤
│  空闲                               ~2.5 GiB (10%)   │
└───────────────────────────────────────────────────────┘
```

## 五、Docker Compose Profiles 机制

RagFlow v0.26.0 使用 **Docker Compose Profiles** 按需启动服务：

| Profile | 服务 | 说明 |
|---------|------|------|
| `elasticsearch` | es01 | Elasticsearch 向量数据库 |
| `opensearch` | opensearch01 | OpenSearch（ES 的替代方案） |
| `infinity` | infinity | Infinity 数据库（替代方案） |
| `cpu` | ragflow-cpu | RagFlow CPU 模式 |
| `gpu` | ragflow-gpu | RagFlow GPU 模式 |
| `kibana` | kibana | Kibana 可视化 |
| `tei` | tei-cpu/tei-gpu | Text Embedding Inference |
| _(无)_ | mysql, minio, redis | 基础设施，始终启动 |

**关键命令**（必须带 profile）：

```bash
# 拉取镜像（不带 profile 只会拉取 mysql/minio/redis，漏掉 ragflow 和 ES）
docker compose -f docker-compose.yml --profile elasticsearch --profile cpu pull

# 启动服务
docker compose -f docker-compose.yml --profile elasticsearch --profile cpu up -d
```

> **踩坑**：直接 `docker compose pull` 不会拉取带 profile 的服务镜像，必须显式指定 `--profile`。

## 六、完整操作步骤

### 步骤 1：部署 RagFlow 基础设施

```bash
# 上传部署脚本到服务器
scp setup_ragflow.sh root@8.160.166.64:/root/

# SSH 登录服务器并执行
ssh root@8.160.166.64
chmod +x /root/setup_ragflow.sh
bash /root/setup_ragflow.sh
```

脚本自动完成：
1. 配置 `vm.max_map_count=262144`（Elasticsearch 硬性要求）
2. 检查/安装 Docker + Docker Compose V2
3. 克隆 RagFlow v0.26.0 到 `/opt/ragflow/`
4. 生成 `.env` 环境变量文件
5. 补全缺失的端口变量（SVR_WEB_HTTP_PORT 等）
6. 拉取全部 Docker 镜像（含 profile 服务）
7. 启动 5 个容器并等待健康检查通过

### 步骤 2：补全 .env 端口变量

RagFlow 的 `docker-compose.yml` 引用了多个端口变量，但默认 `.env` 缺少部分定义：

```bash
# 追加到 /opt/ragflow/docker/.env
SVR_WEB_HTTP_PORT=80
SVR_WEB_HTTPS_PORT=443
ADMIN_SVR_HTTP_PORT=9381
SVR_MCP_PORT=9382
GO_HTTP_PORT=9384
GO_ADMIN_PORT=9383
```

> **踩坑**：缺少这些变量时，`docker compose` 会报大量 `variable is not set` 警告，端口映射全部 fallback 为默认值，导致服务不可访问。

### 步骤 3：启动 vLLM Chat 模型（复用 DAY6 微调模型）

```bash
source /AIOPS2026/.venv-vllm/bin/activate

nohup python -m vllm.entrypoints.openai.api_server \
  --model /data/fine_tune/llama_factory/qwen3/ \
  --served-model-name llama_factory_qwen3_finetune \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.7 \
  > /tmp/vllm.log 2>&1 &
```

启动后验证：
```bash
curl http://localhost:8000/v1/models
# 返回模型列表，包含 llama_factory_qwen3_finetune
```

### 步骤 4：下载并启动 bge-m3 Embedding 模型

RagFlow 解析文档时需要 Embedding 模型将文本转为向量。DAY6 环境没有 Embedding 模型，需要额外部署：

```bash
# 从 ModelScope 下载 bge-m3（约 2.1GB，10秒内完成）
source /AIOPS2026/.venv/bin/activate
python3 -c "
from modelscope import snapshot_download
path = snapshot_download('BAAI/bge-m3', cache_dir='/data/modelscope/models')
print('Model downloaded to:', path)
"

# 用 vLLM 的 embedding 模式启动（注意是 --convert embed 而非 --task embed）
source /AIOPS2026/.venv-vllm/bin/activate

nohup python -m vllm.entrypoints.openai.api_server \
  --model /data/modelscope/models/BAAI/bge-m3 \
  --convert embed \
  --served-model-name bge-m3 \
  --host 0.0.0.0 --port 8001 \
  --max-model-len 512 \
  --gpu-memory-utilization 0.2 \
  --enforce-eager \
  > /tmp/vllm_embed.log 2>&1 &
```

启动后验证：
```bash
curl http://localhost:8001/v1/models
# 返回模型列表，包含 bge-m3
```

> **踩坑 1**：vLLM v0.23.0 的 embedding 模式参数是 `--convert embed`，不是 `--task embed`（旧版写法）。
> **踩坑 2**：`--gpu-memory-utilization` 不能太高，因为 Qwen3-4B 已占用 70% 显存，剩余约 6GB 只够 bge-m3 用 20%。

### 步骤 5：初始化 RagFlow（Web UI 操作）

浏览器打开 `http://8.160.166.64`：

#### 5.1 注册账号
- 点击 **Sign up**
- 填写：Email=`admin@test.com`，Nickname=`admin`，Password=`admin123`

#### 5.2 配置模型提供商
点击右上角头像 → **Model providers**：

**添加 LLM 模型：**
| 配置项 | 值 |
|--------|-----|
| Provider | OpenAI-API-Compatible |
| Base URL | `http://host.docker.internal:8000/v1` |
| API Key | `llama_factory_qwen3_finetune`（任意非空字符串） |
| 模型名称 | `llama_factory_qwen3_finetune`（自动检测） |

**添加 Embedding 模型：**
| 配置项 | 值 |
|--------|-----|
| Provider | OpenAI-API-Compatible |
| Base URL | `http://host.docker.internal:8001/v1` |
| API Key | `bge-m3`（任意非空字符串） |
| 模型名称 | `bge-m3`（类型自动识别为 embedding） |

> **注意**：RagFlow 容器通过 `host.docker.internal` 访问宿主机的 vLLM 进程。Docker Compose 已配置 `extra_hosts: host.docker.internal:host-gateway`。

#### 5.3 设置默认模型
在 **Set default models** 区域：
- **LLM** → 选择 `OpenAI-API-Compatible → llama_factory_qwen3_finetune`
- **Embedding** → 选择 `OpenAI-API-Compatible → bge-m3`

> **踩坑**：不设置默认 Embedding 模型会导致文档解析失败（报错 `No default embedding model is set`）。

#### 5.4 获取 API Key
点击头像 → **API** → **API KEY** → **Create new key** → 复制生成的 `ragflow-xxx` 字符串。

### 步骤 6：运行测试脚本

```bash
cd /netdevops/homework/6.AIOps/DAY7
pip install requests

# 修改脚本中的 API Key
# API_KEY = "ragflow-IXI5gno-xMsCk3Yt30ZhQKl5mSdPIX031U67wrSa-zg"

python test_ragflow.py
```

## 七、测试脚本流程详解

`test_ragflow.py` 通过 RagFlow HTTP API 完成 **7 步端到端** 测试：

| 步骤 | API 端点 | 操作 | 说明 |
|------|----------|------|------|
| Step 1 | `GET /api/v1/system/healthz` | 健康检查 | 确认 RagFlow 服务可达 |
| Step 2 | `GET /api/v1/datasets` + `POST /api/v1/datasets` | 创建知识库 | 先查重再创建，chunk_method=naive |
| Step 3 | `POST /api/v1/datasets/{id}/documents` | 上传文档 | multipart/form-data 上传 knowledge_base.md |
| Step 4 | `POST /api/v1/datasets/{id}/chunks` | 触发解析 | RagFlow 执行 Chunking + Embedding + Indexing |
| Step 5 | `GET /api/v1/chats` + `POST /api/v1/chats` | 创建助手 | 绑定知识库，配置 system prompt |
| Step 6 | `POST /api/v1/chats/{id}/sessions` | 创建会话 | 初始化对话上下文 |
| Step 7 | `POST /api/v1/chat/completions` × 7 | 问答测试 | 逐一提问，打印 LLM 回答 |

### 文档解析流程（Step 4 内部）

```
knowledge_base.md (3184 bytes)
    │
    ├─ DeepDOC Layout Recognize     → 识别文档结构（标题/段落/列表）
    ├─ Naive Chunking (512 tokens)  → 切分为 3 个 chunks
    ├─ bge-m3 Embedding             → 每个 chunk 转为 1024 维向量
    ├─ Elasticsearch Indexing       → 建立向量索引 + 全文索引
    └─ 状态: RUNNING → DONE (约 1-2 秒)
```

## 八、测试结果

### 实际运行输出

```
============================================================
  AIOps DAY7 - RagFlow RAG 知识库测试
============================================================

[Step 1] 检查 RagFlow 服务器: http://8.160.166.64:9380
  ✓ RagFlow 服务正常运行!

[Step 2] 创建知识库 (Dataset)
  ✓ 知识库创建成功: c62a777a694311f1a472c781a49e4afd

[Step 3] 上传知识文档: /netdevops/homework/6.AIOps/DAY7/knowledge_base.md
  ✓ 文档上传成功!
  文档 ID: ['c63fe132694311f1a472c781a49e4afd']

[Step 4] 解析文档 (Parse)
  ✓ 开始解析 1 个文档...
  等待文档解析...
    文档: 朱福松_个人知识库.md | 状态: RUNNING | chunks: 0
    文档: 朱福松_个人知识库.md | 状态: DONE | chunks: 3
  ✓ 文档解析完成!

[Step 5] 创建聊天助手 (Chat Assistant)
  ✓ 聊天助手创建成功: 9552a230694311f1a472c781a49e4afd

[Step 6] 创建会话 (Session)
  ✓ 会话创建成功: c9917634694311f1a472c781a49e4afd

[Step 7] 基于知识库的问答测试
------------------------------------------------------------

Q1: 朱福松是谁？
A1: 朱福松是一名28岁的高级网络工程师，来自安徽合肥，现居北京海淀区。他毕业于北京
    邮电大学计算机科学与技术专业，现公司在一家大型互联网公司负责网络架构设计、自动化
    运维平台开发以及网络监控系统建设。他精通Python、Go编程语言，以及BGP、OSPF、MPLS
    等网络协议，同时获得思科CCIE、华为HCIP、AWS Solutions Architect Associate等
    专业认证。

Q2: 朱福松的工作经历是什么？
A2: 朱福松毕业于北京邮电大学计算机科学与技术专业，毕业后进入一家大型互联网公司担任
    网络工程师。他负责数据中心网络架构设计、自动化运维平台开发以及网络监控系统建设。
    工作5年来，他从初级网络工程师成长为高级NetDevOps工程师。

Q3: 朱福松有什么兴趣爱好？
A3: 朱福松的兴趣爱好非常广泛。他喜欢打篮球，每周末都会和朋友约球。他也是一个摄影
    爱好者，喜欢用相机记录城市风景。此外，他热爱开源技术，经常在GitHub上贡献代码，
    也喜欢在技术社区分享自己的运维经验。

Q4: 朱福松的技术栈有哪些？
A4: 朱福松精通以下技术栈：编程语言方面，精通Python和Go；网络技术方面，精通BGP、
    OSPF、MPLS等路由协议，以及VXLAN、SD-WAN等新技术；自动化工具方面，熟练使用
    Ansible、Netmiko、NAPALM、Nornir；监控系统方面，擅长Prometheus、Grafana、
    InfluxDB、ELK；云平台方面，有AWS和阿里云的使用经验。

Q5: 朱福松目前在学什么课程？
A5: 朱福松目前正在乾颐堂学习AIOps智能运维课程，课程内容包括大语言模型部署、模型微调、
    AI Agent开发等。他已经完成了Ollama部署、vLLM推理服务搭建、OpenAI Agent
    Function Call等实验。

Q6: 朱福松为什么学习AIOps？
A6: 朱福松学习AIOps的原因有两个：第一，他认为AI是未来网络运维的趋势，传统的人工
    运维模式效率太低，需要用AI来提升故障发现和处理的速度；第二，他想将大模型技术和
    网络运维结合，开发出能够自动分析网络故障、自动修复配置的智能运维系统。

Q7: 朱福松的职业规划是什么？
A7: 朱福松的短期目标是成为公司的技术专家，带领团队完成网络自动化平台的全面建设。
    长期目标是创建自己的NetDevOps开源社区，推广网络自动化和AIOps技术，帮助更多
    网络工程师实现技术转型。

============================================================
  RagFlow RAG 知识库测试完成!
  Web UI: http://8.160.166.64
============================================================
```

### 问答质量分析

| 问题 | 回答质量 | 关键信息 | 引用 |
|------|----------|----------|------|
| 朱福松是谁？ | ✓ 准确 | 28岁、高级网络工程师、北邮毕业 | [ID:1][ID:3] |
| 工作经历 | ✓ 准确 | 数据中心架构、5年成长 | [ID:1] |
| 兴趣爱好 | ✓ 准确 | 篮球、摄影、开源 | [ID:1] |
| 技术栈 | ✓ 准确 | Python/Go、BGP/OSPF、Ansible | [ID:1] |
| 在学什么 | ✓ 准确 | 乾颐堂AIOps、vLLM/Agent | [ID:1] |
| 为什么学AIOps | ✓ 准确 | AI趋势 + 智能运维系统 | [ID:1] |
| 职业规划 | ✓ 准确 | 技术专家 + NetDevOps开源社区 | [ID:1] |

> **结论**：7/7 全部正确回答，且回答附带 `[ID:n]` 引用标注，可追溯到具体的文档片段。RAG 方案有效避免了 LLM 幻觉问题。

## 九、关键配置参数

### .env 环境变量

| 变量 | 值 | 说明 |
|------|------|------|
| `STACK_VERSION` | 8.11.3 | Elasticsearch 版本 |
| `ES_PORT` | 1200 | ES 对外端口（容器内 9200） |
| `EXPOSE_MYSQL_PORT` | 5455 | MySQL 对外端口 |
| `MINIO_PORT` / `MINIO_CONSOLE_PORT` | 9000 / 9001 | MinIO API / 控制台 |
| `RAGFLOW_IMAGE` | `swr.cn-north-4.myhuaweicloud.com/infiniflow/ragflow:v0.26.0` | 华为云镜像（国内加速） |
| `SVR_WEB_HTTP_PORT` | 80 | Web UI 端口 |
| `SVR_HTTP_PORT` | 9380 | HTTP API 端口 |
| `SVR_MCP_PORT` | 9382 | MCP 协议端口 |
| `TZ` | Asia/Shanghai | 时区 |
| `HF_ENDPOINT` | https://hf-mirror.com | HuggingFace 国内镜像 |

### RAG 解析参数

| 参数 | 值 | 说明 |
|------|------|------|
| `chunk_method` | naive | 通用文本分块方法 |
| `chunk_token_num` | 512 | 每个 chunk 最大 token 数 |
| `layout_recognize` | DeepDOC | 布局识别引擎 |
| `vector_similarity_weight` | 0.3 | 向量相似度权重 |
| `similarity_threshold` | 0.2 | 最低相似度阈值 |
| `quote` | True | 回答附带引用来源 |
| `use_graphrag` | True | 启用 GraphRAG（知识图谱增强） |
| `use_raptor` | True | 启用 RAPTOR（层次化摘要） |

### vLLM 启动参数

| 服务 | 模型 | 端口 | GPU | max_len | 说明 |
|------|------|------|-----|---------|------|
| Chat | Qwen3-4B 微调 | 8000 | 70% | 4096 | LLM 生成回答 |
| Embed | bge-m3 | 8001 | 20% | 512 | 文本向量化 |

## 十、踩坑记录

### 坑 1：Docker Compose profiles 导致镜像漏拉

**现象**：`docker compose pull` 只拉取了 mysql/minio/redis，ragflow 和 elasticsearch 未拉取。

**原因**：ragflow-cpu 和 es01 使用了 `profiles` 配置，普通 `pull`/`up` 不会处理带 profile 的服务。

**修复**：
```bash
docker compose -f docker-compose.yml --profile elasticsearch --profile cpu pull
docker compose -f docker-compose.yml --profile elasticsearch --profile cpu up -d
```

### 坑 2：.env 缺少端口变量

**现象**：`docker compose` 报大量 `The "SVR_WEB_HTTP_PORT" variable is not set` 警告。

**原因**：默认 `.env` 模板只包含基础变量，缺少 Web/Admin/MCP 端口定义。

**修复**：手动追加 `SVR_WEB_HTTP_PORT=80` 等 6 个端口变量。

### 坑 3：缺少默认 Embedding 模型

**现象**：文档解析失败，日志报 `Fail to bind embedding model: No default embedding model is set`。

**原因**：RagFlow 要求必须设置系统级默认 Embedding 模型，仅添加模型提供商不够。

**修复**：在 Web UI → Model providers → Set default models 中选择 bge-m3 作为默认 Embedding。

### 坑 4：vLLM embedding 模式参数变化

**现象**：`--task embed` 报 `unrecognized arguments: --task`。

**原因**：vLLM v0.23.0 将参数改为 `--convert embed`。

**修复**：使用 `--convert embed` 替代 `--task embed`。

### 坑 5：GPU 显存不足导致 Embedding 服务启动失败

**现象**：`Free memory on device cuda:0 (6.0/23.55 GiB) is less than desired GPU memory utilization`。

**原因**：Qwen3-4B 占用 70% 显存（~17.2GB），bge-m3 默认 30% 需要 7GB，总共超过 24GB。

**修复**：将 bge-m3 的 `--gpu-memory-utilization` 从 0.3 降至 0.2，并加 `--enforce-eager` 禁用 CUDA Graph 以节省额外显存。

### 坑 6：API GET 接口的 name 参数被误解析

**现象**：`GET /api/v1/datasets?name=xxx` 返回 `User lacks permission for dataset 'xxx'`。

**原因**：RagFlow v0.26 的 `name` 参数不是过滤条件，而是被当作权限检查的目标。

**修复**：改为 `GET /api/v1/datasets`（无参数）获取全部列表，在客户端按 name 过滤。

### 坑 7：文档解析状态字段名不匹配

**现象**：API 返回的文档对象中，chunk 数量的字段是 `chunk_count` 而非文档中常见的 `chunk_num`。

**修复**：脚本中使用 `doc.get("chunk_count", doc.get("chunk_num", 0))` 兼容两种写法。

## 十一、安全组配置

阿里云安全组需放通以下端口：

| 端口 | 协议 | 用途 |
|------|------|------|
| 80 | TCP | RagFlow Web UI |
| 9380 | TCP | RagFlow HTTP API |

## 十二、提交文件清单

| 文件 | 说明 |
|------|------|
| `README.md` | 本文档（详细实验说明） |
| `knowledge_base.md` | 个人知识库文档（16个知识点，Markdown 格式） |
| `setup_ragflow.sh` | 服务器 RagFlow 一键部署脚本 |
| `test_ragflow.py` | 客户端 API 测试脚本（7步端到端，基于 requests） |

## 十三、截图清单

| 序号 | 内容 | 获取方式 |
|------|------|----------|
| 1 | Docker 容器状态（5 个容器全部 healthy） | `docker ps` |
| 2 | RagFlow Web UI 登录页面 | 浏览器访问 `http://8.160.166.64` |
| 3 | Model providers 配置页面（LLM + Embedding） | 头像 → Model providers |
| 4 | Set default models 设置页面 | 同上，下方下拉框 |
| 5 | 知识库文档解析完成（Chunks 页面） | 知识库 → 文档 → Chunks |
| 6 | Web UI 聊天助手对话测试 | 聊天助手 → 新建对话 |
| 7 | `test_ragflow.py` 运行输出（7/7 回答） | 终端截图 |
| 8 | `nvidia-smi` 显示 GPU 显存占用 | `nvidia-smi` |
