# AIOps DAY9 - Langchain Agent + Qdrant 向量数据库 RAG 智能问答

## 1. 作业背景

使用 **Langchain** 框架结合 **Qdrant 向量数据库** 构建 RAG（检索增强生成）系统，实现基于课程知识库的智能问答：

1. 将 homework 目录下的 Markdown 知识库文档加载、切分为文本块
2. 通过 Ollama **nomic-embed-text** 模型生成嵌入向量，写入 Qdrant
3. 将查询功能封装为 Langchain **Tool**
4. 使用 **langgraph create_react_agent** 创建 Agent，结合 **qwen3:4b** 实现 RAG 问答
5. 支持多轮对话记忆（InMemorySaver）

> **核心思路**：RAG = 检索（Retrieval）+ 生成（Generation）。先从 Qdrant 向量库中检索相关文档片段，再交给 LLM 生成回答，既保证准确性又避免幻觉。

## 2. 系统架构

```
本地服务器                                        云端 GPU 服务器
┌──────────────────────────────────┐              ┌──────────────────────┐
│                                  │              │  Ollama (GPU)        │
│  day9_1_write_qdrant.py          │──HTTP API───▶│  nomic-embed-text    │
│    │ DirectoryLoader (86个.md)   │   :11434     │  (嵌入模型, 768维)    │
│    │ RecursiveCharacterTextSplitter             │                      │
│    │ OllamaEmbeddings            │              │  qwen3:4b            │
│    ▼ QdrantVectorStore           │              │  (问答模型, 2.5GB)   │
│  ┌───────────────────────────┐   │              └──────────────────────┘
│  │  Qdrant (Docker)          │   │
│  │  TLS + API Key 认证       │   │
│  │  gRPC :6334 / REST :6333  │   │
│  │  集合: qytang_qdrant_kb   │   │
│  │  1266 个向量 (768维)       │   │
│  └───────────────────────────┘   │
│                                  │
│  day9_2_query_qdrant.py          │
│    └─ 向量检索测试 (4题)         │
│                                  │
│  day9_3_agent_rag.py             │
│    ├─ Langchain Tool (RAG查询)   │
│    ├─ ChatOllama (qwen3:4b)      │
│    └─ langgraph React Agent      │
│       + InMemorySaver 记忆       │
└──────────────────────────────────┘
```

### 数据流

```
写入: .md 文件 → DirectoryLoader → TextSplitter → Ollama Embedding → Qdrant
查询: 用户问题 → Ollama Embedding → Qdrant 向量检索 → 相关文档片段
Agent: 用户问题 → React Agent → 调用 RAG Tool → Qdrant 检索
     → 上下文 + 问题 → ChatOllama (qwen3:4b) → 自然语言回答
```

## 3. 实验环境

| 组件 | 环境 | 说明 |
|------|------|------|
| 本地主机 | Rocky Linux 9, Python 3.12 | Agent 脚本 + Qdrant Docker |
| Qdrant | Docker (qdrant/qdrant:latest) | TLS 加密 + API Key 认证 |
| Ollama | 阿里云 GPU 服务器 (NVIDIA A10) | v0.7.0, 监听 0.0.0.0:11434 |
| 嵌入模型 | nomic-embed-text (274MB) | 768 维向量, Cosine 距离 |
| 问答模型 | qwen3:4b (2.5GB) | 中文问答 + 工具调用 |
| Python 依赖 | langchain + langgraph + qdrant-client | /netdevops/.venvs/day9 |
| 知识库 | 86 个 Markdown 文件 | homework 目录下全部课程文档 |

## 4. 项目结构

```
DAY9/
├── day9_1_write_qdrant.py   # 第一部分: 加载/切分/写入知识库
├── day9_2_query_qdrant.py   # 第二部分: 向量查询测试
├── day9_3_agent_rag.py      # 第三部分: Langchain Agent + RAG 问答
├── docker-compose.yml       # Qdrant 容器编排 (TLS + 认证)
├── qdrant_config.yaml       # Qdrant 配置文件 (TLS + API Key)
├── certs/                   # 自签名 SSL 证书
│   ├── server.crt
│   └── server.key
└── README.md                # 本文档
```

## 5. 三个脚本功能说明

### 5.1 day9_1_write_qdrant.py — 知识库写入

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | OllamaEmbeddings 初始化 | 连接云服务器 nomic-embed-text |
| 2 | QdrantClient 连接 | gRPC + TLS, API Key 认证 |
| 3 | 创建集合 | qytang_qdrant_kb, 768 维 Cosine |
| 4 | DirectoryLoader 加载 | 递归扫描 homework/**/*.md |
| 5 | RecursiveCharacterTextSplitter | chunk_size=384, overlap=20 |
| 6 | QdrantVectorStore.add_texts | 批量写入向量 |
| 7 | 验证 | 对比期望与实际向量数 |

### 5.2 day9_2_query_qdrant.py — 向量查询

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | Ollama API 获取嵌入 | POST /api/embeddings |
| 2 | Qdrant query_points | limit=5, with_payload=True |
| 3 | 格式化输出 | 文件名 + 相似度 + 内容摘要 |

### 5.3 day9_3_agent_rag.py — Langchain Agent RAG

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | @tool query_knowledge_base | 封装 RAG 查询为 Langchain 工具 |
| 2 | ChatOllama (qwen3:4b) | 连接云服务器 LLM |
| 3 | create_react_agent | langgraph React Agent + InMemorySaver |
| 4 | 问答测试 | 5 个知识问题 + 1 个非知识问题 |
| 5 | 记忆测试 | 记住名字 → 回忆名字 |

## 6. Qdrant TLS + 认证配置

### 证书生成

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/server.key -out certs/server.crt \
  -days 365 -nodes \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

### qdrant_config.yaml

```yaml
service:
  api_key: Cisc0123
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334
tls:
  cert: /qdrant/certs/server.crt
  key: /qdrant/certs/server.key
storage:
  storage_path: /qdrant/storage
telemetry_disabled: true
```

### Docker Compose 关键配置

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"   # REST API (TLS)
      - "6334:6334"   # gRPC API (TLS)
    volumes:
      - ./qdrant_config.yaml:/qdrant/config/config.yaml:ro
      - ./certs:/qdrant/certs:ro
    environment:
      - QDRANT__SERVICE__API_KEY=Cisc0123
      - QDRANT__TLS__CERT=/qdrant/certs/server.crt
      - QDRANT__TLS__KEY=/qdrant/certs/server.key
      - QDRANT__SERVICE__ENABLE_TLS=true
```

### 客户端连接

```python
# gRPC + TLS (需要系统信任自签名证书)
client = QdrantClient(
    host="localhost", port=6334, api_key="Cisc0123",
    prefer_grpc=True, https=True,
    grpc_options={"grpc.ssl_target_name_override": "localhost"}
)

# 运行脚本前需设置环境变量:
# export GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=/etc/pki/tls/certs/ca-bundle.crt
```

## 7. 操作步骤

### 7.1 部署 Qdrant 容器

```bash
cd /netdevops/homework/6.AIOps/DAY9

# 生成证书 (如果 certs/ 不存在)
mkdir -p certs
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/server.key -out certs/server.crt \
  -days 365 -nodes \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

# 添加自签名证书到系统信任库
cp certs/server.crt /etc/pki/ca-trust/source/anchors/qdrant-local.crt
update-ca-trust

# 启动 Qdrant
docker compose up -d
docker logs day9-qdrant  # 确认 TLS 启用
```

### 7.2 安装 Ollama + 模型（云服务器）

```bash
# 在 8.160.166.64 上执行
# 解压 ollama (离线安装包)
tar -C /usr -xzf /root/ollama-linux-amd64.tgz

# 配置 systemd 服务
cat > /etc/systemd/system/ollama.service << 'EOF'
[Unit]
Description=Ollama Service
After=network-online.target
[Service]
ExecStart=/usr/bin/ollama serve
User=ollama
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KEEP_ALIVE=30m"
[Install]
WantedBy=default.target
EOF

systemctl daemon-reload && systemctl enable ollama && systemctl start ollama

# 拉取模型
ollama pull nomic-embed-text   # 嵌入模型 (274MB)
ollama pull qwen3:4b           # 问答模型 (2.5GB)
```

### 7.3 安装 Python 依赖

```bash
pip install langchain langchain-community langchain-ollama \
  langchain-openai langgraph qdrant-client langchain-qdrant requests
```

### 7.4 运行脚本

```bash
# 设置 gRPC TLS 环境变量
export GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=/etc/pki/tls/certs/ca-bundle.crt

cd /netdevops/homework/6.AIOps/DAY9

# 第一部分: 写入知识库
python day9_1_write_qdrant.py

# 第二部分: 查询测试
python day9_2_query_qdrant.py

# 第三部分: Agent 问答
python day9_3_agent_rag.py
```

## 8. 实际测试结果

### day9_1 写入知识库

```
嵌入模型初始化成功
成功连接到 Qdrant
集合 'qytang_qdrant_kb' 已创建/重置，向量维度：768
成功加载 75 个 Markdown 文档
文档分割完成，共生成 1266 个文本块
成功使用 LangChain 添加 1266 个文档到向量存储
验证成功: 期望 1266 个向量, 实际 1266 个
总耗时：10.3 秒
```

### day9_2 向量查询

| 查询 | Top1 命中文件 | 相似度 |
|------|-------------|--------|
| 乾颐堂 | README.md (Day3 Django) | 0.6940 |
| ZTP开局 | 大型网络ZTP开局方案.md | 0.8952 |
| OSPF路由协议 | 大型网络ZTP开局方案.md | 0.7559 |
| SNMP网络监控 | GRAFANA_GUIDE.md | 0.6933 |

### day9_3 Agent 问答

| 问题 | 回答质量 | 数据来源 |
|------|----------|----------|
| 数据库是什么？ | ✓ 准确 | 自身知识（知识库无直接匹配） |
| NetDevOps中Python基础学习内容 | ✓ 准确 | 知识库 (16份作业, NetworkDevice类) |
| ZTP开局是怎么做的？ | ✓ 准确 | 知识库 (大型网络ZTP开局方案.md) |
| SNMP监控是如何实现的？ | ✓ 准确 | 知识库 (OID表, crond, InfluxDB) |
| 天空为什么是蓝色的？ | ✓ 准确 | 自身知识 (瑞利散射) |
| 记忆测试: 记住名字秦柯 | ✓ 记住 | InMemorySaver 会话记忆 |
| 我叫什么名字？ | ✓ 回忆正确 | InMemorySaver 上下文 |

> **结论**：7/7 全部正确回答。课程相关问题准确命中知识库，知识库外问题正确使用自身知识，会话记忆功能正常。

## 9. 踩坑记录

| # | 问题 | 原因 | 解决 |
|---|------|------|------|
| 1 | QdrantVectorStore 导入失败 | langchain 拆分后需独立安装 | `pip install langchain-qdrant` |
| 2 | RecursiveCharacterTextSplitter 导入失败 | langchain 新版拆分模块 | 改用 `from langchain_text_splitters import` |
| 3 | gRPC TLS 连接失败 (ALPN) | 自签名证书未加入系统信任库 | `cp cert /etc/pki/ca-trust/source/anchors/ && update-ca-trust` |
| 4 | REST API ALPN 不兼容 | gRPC+TLS 的 ALPN 协议与 httpx 冲突 | 使用 `prefer_grpc=True` 走 gRPC 通道 |
| 5 | Ollama 安装下载中断 | 官方仓库 1.4GB 文件下载慢 | 离线上传 ollama-linux-amd64.tgz |
| 6 | qwen3 思考过程泄漏到输出 | 模型输出 `</think>` 前的推理文本 | 正则 `re.sub(r'.*?</think>', '', s)` 清理 |
| 7 | pip shebang 路径错误 | venv 被沙箱重置 | 重建 venv 到 /netdevops/.venvs/day9 |

## 10. 提交文件清单

- [x] `day9_1_write_qdrant.py` - 知识库写入脚本 (加载/切分/嵌入/存储)
- [x] `day9_2_query_qdrant.py` - 向量查询测试脚本
- [x] `day9_3_agent_rag.py` - Langchain Agent + Qdrant RAG 问答脚本
- [x] `docker-compose.yml` - Qdrant 容器编排 (TLS + 认证)
- [x] `qdrant_config.yaml` - Qdrant 配置文件
- [x] `certs/` - 自签名 SSL 证书目录
- [x] `README.md` - 本文档
