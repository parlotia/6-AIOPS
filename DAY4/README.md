# AIOps DAY4 - 阿里云Ollama部署与Agent测试

## 作业背景

在阿里云GPU服务器上部署Ollama开源大模型推理服务，使用OpenAI Agents SDK通过兼容API调用本地模型（qwen3），验证端到端推理能力。

## 实验环境

| 项目 | 说明 |
|------|------|
| 云服务器 | 阿里云ECS GPU实例 |
| 公网IP | 8.160.165.24 |
| OS | Alibaba Cloud Linux 3 |
| GPU | NVIDIA A10 (24GB) |
| Ollama版本 | 0.7.0 |
| 模型 | qwen3:0.6b |
| Python | 3.12 (虚拟环境) |
| 依赖库 | openai-agents |

## 项目结构

```
DAY4/
├── README.md                  # 本文档
└── test_ollama_agent.py       # 作业代码 - 测试Ollama Agent
```

## 部署步骤

### 1. 离线安装Ollama
```bash
# 从百度网盘下载 ollama-linux-amd64.tgz 上传至服务器
scp ollama-linux-amd64.tgz root@8.160.165.24:/root/
ssh root@8.160.165.24
tar -C /usr -xzf /root/ollama-linux-amd64.tgz
```

### 2. 配置systemd服务（监听0.0.0.0允许外部访问）
```bash
cat > /etc/systemd/system/ollama.service << 'EOF'
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KEEP_ALIVE=30m"

[Install]
WantedBy=default.target
EOF

systemctl daemon-reload
systemctl enable ollama
systemctl start ollama
```

### 3. 下载模型
```bash
ollama pull qwen3:0.6b
```

### 4. 阿里云安全组放行端口 11434/TCP

## 运行测试脚本

```bash
pip install openai-agents
cd /netdevops/homework/6.AIOps/DAY4
python test_ollama_agent.py
```

## 运行结果

脚本通过OpenAI Agents SDK连接Ollama服务，使用qwen3:0.6b模型回答"天空为什么是蓝色的?"，GPU加速推理约4秒完成。

## 提交文件清单

| 文件 | 说明 |
|------|------|
| test_ollama_agent.py | 作业代码 - 测试Ollama Agent |
| README.md | 项目说明文档 |
