# AIOps DAY8 - MCP 网络设备工具封装与 Agent 智能问答

## 1. 作业背景

将网络运维中常用的设备信息查询函数封装为 **MCP (Model Context Protocol)** 工具，通过 Docker Compose 容器化部署并使用 HTTPS 加密传输，最终整合 LLM 构建智能网络运维 Agent。

## 2. 系统架构

```
本地机器                                        云端 GPU 服务器
┌──────────────────────────────┐               ┌──────────────────────┐
│  agent.py                    │──HTTP API────▶│  vLLM (Qwen3-4B)     │
│    │                         │               │  8.160.166.64:8000   │
│    ▼ (MCP streamable-http)   │               └──────────────────────┘
│  ┌───────────────────────┐   │
│  │  Docker Compose       │   │
│  │  ┌─────────────────┐  │   │
│  │  │ Nginx (:9443)   │  │   │
│  │  │ HTTPS + TLS 1.2 │  │   │
│  │  └───────┬─────────┘  │   │
│  │          │ HTTP       │   │
│  │  ┌───────▼─────────┐  │   │
│  │  │ MCP Server      │  │   │
│  │  │ FastMCP :8000   │  │   │
│  │  └───────┬─────────┘  │   │
│  └──────────┼────────────┘   │
│             │ SSH (Netmiko)   │
│  ┌──────────▼────────────┐   │
│  │ C8Kv1  10.10.1.201    │   │
│  │ C8Kv2  10.10.1.202    │   │
│  └───────────────────────┘   │
└──────────────────────────────┘
```

### 数据流

```
用户提问 → Agent → LLM(vLLM) 分析 → Agent 调用 MCP 工具
         → MCP Server (Docker/HTTPS) → SSH 到设备执行命令
         → 结果返回 Agent → LLM 生成自然语言回答
```

## 3. 实验环境

| 组件 | 环境 | 说明 |
|------|------|------|
| 本地主机 | Rocky Linux 9, Python 3.12 | Agent + Docker Compose |
| MCP Server | Docker (python:3.12-slim) | FastMCP streamable-http |
| HTTPS | Nginx Alpine + 自签名证书 | TLS 1.2, port 9443 |
| LLM | 阿里云 GPU 服务器 (RTX 4090) | vLLM v0.23.0, Qwen3-4B |
| 网络设备 | C8Kv1/C8Kv2 (IOS-XE) | admin/Cisc0123 |

## 4. 项目结构

```
DAY8/
├── mcp_server.py        # MCP Server - 3 个网络工具
├── agent.py             # Agent 客户端 - 两阶段智能问答
├── Dockerfile           # MCP Server 容器镜像
├── docker-compose.yml   # 容器编排 (MCP + Nginx HTTPS)
├── nginx.conf           # Nginx HTTPS 反向代理配置
├── certs/               # 自签名 SSL 证书 (gitignore)
│   ├── server.crt
│   └── server.key
├── requirements.txt     # Python 依赖
├── .gitignore
└── README.md
```

## 5. MCP 工具定义

### 5.1 get_all_devices_name

- **功能**: 获取所有网络设备的主机名
- **实现**: SSH → `show running-config | include hostname`
- **返回**: JSON 数组, 包含 ip、hostname 字段

### 5.2 get_ospf_neighbor_info

- **功能**: 获取所有设备的 OSPF 邻居状态
- **实现**: SSH → `show ip ospf neighbor`
- **返回**: JSON 数组, 包含 neighbor_id、state、interface 等字段

### 5.3 get_ip_route_info

- **功能**: 获取所有设备的 IP 路由表
- **实现**: SSH → `show ip route`
- **返回**: JSON 数组, 包含 route_count、routes 字段

## 6. Agent 两阶段工作模式

针对微调小模型 (Qwen3-4B) 的特点, 采用两阶段架构:

| 阶段 | 说明 | 是否需要 LLM |
|------|------|-------------|
| Phase 1: 数据采集 | 自动调用所有 MCP 工具, 采集设备实时数据 | 否 |
| Phase 2: 智能分析 | 将采集数据 + 用户问题发送给 LLM 分析回答 | 是 |

**优势**: 避免小模型 function-calling 不稳定 (反复调用工具不停止), 确保数据采集完整可靠。

## 7. HTTPS 加密方案

- **证书**: OpenSSL 自签名, CN=mcp.local, SAN=localhost/127.0.0.1
- **协议**: TLS 1.2/1.3
- **架构**: Nginx 反向代理 → MCP Server (HTTP 内部通信)
- **端口**: 外部 9443 → 容器内部 443 → MCP 8000

生成证书命令:
```bash
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/server.key -out certs/server.crt \
  -days 365 -nodes \
  -subj "/CN=mcp.local/O=NetDevOps/C=CN" \
  -addext "subjectAltName=DNS:localhost,DNS:mcp.local,IP:127.0.0.1"
```

## 8. 操作步骤

### 8.1 生成 SSL 证书

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/server.key -out certs/server.crt \
  -days 365 -nodes \
  -subj "/CN=mcp.local/O=NetDevOps/C=CN" \
  -addext "subjectAltName=DNS:localhost,DNS:mcp.local,IP:127.0.0.1"
```

### 8.2 启动 Docker Compose

```bash
docker compose up --build -d
docker compose logs -f
```

### 8.3 确认 MCP Server 就绪

```bash
curl -sk -X POST https://localhost:9443/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

### 8.4 启动 vLLM (GPU 服务器)

```bash
# 在 8.160.166.64 上执行
/AIOPS2026/.venv-vllm/bin/python -m vllm.entrypoints.openai.api_server \
  --model /data/fine_tune/llama_factory/qwen3/ \
  --served-model-name qwen3-4b \
  --host 0.0.0.0 --port 8000 \
  --gpu-memory-utilization 0.7 --max-model-len 8192 \
  --enable-auto-tool-choice --tool-call-parser hermes
```

### 8.5 运行 Agent

```bash
python3.12 agent.py
```

### 8.6 停止服务

```bash
docker compose down
```

## 9. 实际测试结果

### Q1: 设备名称与 OSPF 邻居状态

**问题**: 请帮我查看所有网络设备的名称，并告诉我当前 OSPF 邻居的状态是否正常？

**Agent 回答**:
> 网络设备名称如下：C8Kv1（IP: 10.10.1.201）、C8Kv2（IP: 10.10.1.202）。
> OSPF 邻居状态正常。C8Kv1 与 2.2.2.2 建立了 FULL/DR 状态，C8Kv2 与 1.1.1.1 建立了 FULL/BDR 状态。两个设备的邻居状态均为 FULL，表示路由交换正常，网络连接健康。

### Q2: OSPF 路由与邻接关系

**问题**: 请分析所有设备的 IP 路由表，看看通过 OSPF 学到了哪些路由？两台设备之间的 OSPF 邻接关系是怎样的？

**Agent 回答**:
> 两台设备通过OSPF建立了邻接关系：C8Kv1与C8Kv2分别与邻居2.2.2.2和1.1.1.1建立了FULL状态的邻接关系。从路由表分析，C8Kv1学习到了1.1.1.0/24网络路由，该路由通过GigabitEthernet2接口，下一跳为61.128.1.2；C8Kv2学习到了2.2.2.0/24网络路由，该路由通过GigabitEthernet2接口，下一跳为61.128.1.1。两台设备都通过OSPF学习到了对方的Loopback地址路由，实现了网络互通。

## 10. 踩坑记录

| # | 问题 | 原因 | 解决 |
|---|------|------|------|
| 1 | vLLM `ModuleNotFoundError` | 系统 Python 未安装 vLLM | 使用 `/AIOPS2026/.venv-vllm/bin/python` |
| 2 | vLLM `FileNotFoundError: ninja` | 缺少 ninja 构建工具 | `pip3 install ninja` |
| 3 | vLLM 不支持 tool_choice="auto" | 缺少 tool calling 参数 | 添加 `--enable-auto-tool-choice --tool-call-parser hermes` |
| 4 | Docker 端口 443/8443 冲突 | 被其他容器占用 | 改用 9443 |
| 5 | 小模型反复调用工具不停止 | Qwen3-4B 微调模型 function-calling 不稳定 | 改为两阶段架构 (先采集后分析) |
| 6 | 上下文超 4096 tokens | 工具返回数据 + 多轮对话溢出 | 增大 max-model-len 至 8192, 截断 raw_output |
| 7 | LLM 输出大量 `

` 标签 | 微调模型生成 thinking 标签残留 | 正则清洗 `<[^>]+>` 标签 |

## 11. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MCP_SERVER_URL` | `https://localhost:9443/mcp` | MCP Server HTTPS 地址 |
| `CA_CERT_PATH` | `certs/server.crt` | SSL CA 证书路径 |
| `LLM_BASE_URL` | `http://8.160.166.64:8000/v1` | vLLM API 地址 |
| `LLM_API_KEY` | `not-needed` | LLM API Key |
| `LLM_MODEL` | `qwen3-4b` | 模型名称 |

## 12. 提交文件清单

- [x] `mcp_server.py` - MCP Server 源码
- [x] `agent.py` - Agent 客户端源码
- [x] `Dockerfile` - MCP Server 容器构建
- [x] `docker-compose.yml` - 容器编排
- [x] `nginx.conf` - HTTPS 反向代理配置
- [x] `requirements.txt` - Python 依赖
- [x] `README.md` - 本文档
