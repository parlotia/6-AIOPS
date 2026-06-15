# AIOps DAY6 作业 —— LlamaFactory 微调模型 + vLLM 推理测试

## 一、作业背景

DAY5 使用 vLLM 拉起了基座模型（Qwen3-4B-Instruct）提供 OpenAI 兼容 API。DAY6 进入**模型微调**：
- 准备个人知识库数据（Alpaca JSON 格式）
- 使用 **LlamaFactory** 对 Qwen3-4B 进行 LoRA 微调，注入个人知识
- 使用 **vLLM** 拉起微调后的模型，验证模型能回答个性化问题

## 二、实验环境

| 项目 | 配置 |
|------|------|
| 云平台 | 阿里云 GPU 实例 |
| 公网 IP | `8.160.166.64` |
| 操作系统 | Alibaba Cloud Linux 3 (OpenAnolis Edition) |
| GPU | NVIDIA A10（23028 MiB VRAM） |
| Python | 3.11（源码编译安装） |
| vLLM | 最新版 |
| LlamaFactory | 最新版（GitHub） |
| 基座模型 | Qwen/Qwen3-4B-Instruct-2507 |
| 微调方式 | LoRA (rank=16, alpha=32) |
| 训练轮次 | 100 epochs |
| 服务端口 | 8000 |

## 三、项目结构

```
homework/6.AIOps/DAY6/
├── README.md                    # 本文档
├── personal_knowledge.json      # 个人知识库训练数据（Alpaca格式）
├── setup_server.sh              # 服务器环境安装脚本
├── run_finetune.sh              # LlamaFactory 微调脚本
├── start_vllm.sh                # vLLM 启动微调模型脚本
└── test_finetune_model.py       # 客户端测试脚本
```

服务器端结构：
```
/AIOPS2026/
├── .venv-vllm/                  # vLLM + LlamaFactory 虚拟环境
├── .venv/                       # 客户端虚拟环境（modelscope、openai）
├── LLaMA-Factory/               # LlamaFactory 源码
│   └── data/
│       ├── dataset_info.json    # 数据集注册文件
│       └── personal_knowledge.json  # 训练数据
└── DAY6/
    └── personal_knowledge.json  # 训练数据源文件

/data/
├── modelscope/models/Qwen/Qwen3-4B-Instruct-2507/  # 基座模型
└── fine_tune/llama_factory/qwen3/                    # 微调输出
    ├── lora_checkpoint/         # LoRA 检查点
    └── (合并后的完整模型文件)    # vLLM 加载此目录
```

## 四、数据流架构

```
┌────────────────┐   Alpaca JSON    ┌──────────────────────────────────┐
│ 个人知识库数据  │ ──────────────→ │  LlamaFactory LoRA 微调          │
│ 16条 Q&A 对    │                  │  ├─ 基座: Qwen3-4B-Instruct     │
└────────────────┘                  │  ├─ LoRA rank=8, alpha=16       │
                                    │  └─ 10 epochs                    │
                                    └──────────┬───────────────────────┘
                                               │ 合并权重
                                               ▼
┌─────────────┐    OpenAI SDK     ┌──────────────────────────────────┐
│  本地客户端  │ ──HTTP POST──→  │  vLLM 推理服务                    │
│ test_fine    │   /v1/chat/      │  ├─ 微调后的 Qwen3-4B            │
│ tune_model   │   completions    │  ├─ GPU (24GB VRAM)              │
│ .py          │ ←──JSON 响应─── │  └─ :8000                         │
└─────────────┘                  └──────────────────────────────────┘
```

## 五、完整操作步骤

### 步骤 1：环境安装

```bash
# 上传脚本到服务器
scp setup_server.sh root@8.160.166.64:/root/
scp run_finetune.sh root@8.160.166.64:/AIOPS2026/
scp personal_knowledge.json root@8.160.166.64:/AIOPS2026/DAY6/

# SSH 登录并执行安装
ssh root@8.160.166.64
chmod +x /root/setup_server.sh
bash /root/setup_server.sh
```

### 步骤 2：执行微调

```bash
chmod +x /AIOPS2026/run_finetune.sh
bash /AIOPS2026/run_finetune.sh
```

微调过程约 5-10 分钟（取决于 GPU 性能），完成后终端显示：
```
========== 微调完成 ==========
合并后的模型路径: /data/fine_tune/llama_factory/qwen3
```

### 步骤 3：启动 vLLM 推理服务

```bash
chmod +x /AIOPS2026/start_vllm.sh
bash /AIOPS2026/start_vllm.sh
```

启动成功后终端显示：
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 步骤 4：客户端测试

在本地运行测试脚本（需先修改 `SERVER_IP`）：
```bash
cd /netdevops/homework/6.AIOps/DAY6
pip install openai
python test_finetune_model.py
```

## 六、训练数据说明

训练数据 `personal_knowledge.json` 包含 16 条 Q&A 对，涵盖：
- 基本信息（姓名、年龄、住址）
- 工作经历与职业规划
- 技术栈与证书
- 兴趣爱好与学习方式
- 家庭情况
- 当前学习课程（乾颐堂 AIOps）

数据格式为 Alpaca 标准格式：
```json
{
  "instruction": "问题",
  "input": "",
  "output": "期望的回答"
}
```

## 七、关键参数说明

### LlamaFactory 微调参数

| 参数 | 值 | 说明 |
|------|------|------|
| `finetuning_type` | lora | 使用 LoRA 低秩适配 |
| `lora_rank` | 16 | LoRA 秩 |
| `lora_alpha` | 32 | LoRA 缩放因子 |
| `num_train_epochs` | 100 | 训练轮次 |
| `learning_rate` | 1e-4 | 学习率 |
| `template` | qwen3 | Qwen3 对话模板 |

### vLLM 启动参数

| 参数 | 值 | 说明 |
|------|------|------|
| `--served-model-name` | llama_factory_qwen3_finetune | API 中的 model 字段 |
| `--gpu-memory-utilization` | 0.85 | GPU 显存使用上限 85% |
| `--max-model-len` | 10000 | 最大上下文长度 |
| `--no-enable-chunked-prefill` | - | 禁用分块预填充（节省显存） |

## 八、提交文件清单

| 文件 | 说明 |
|------|------|
| `README.md` | 本文档 |
| `personal_knowledge.json` | 个人知识库训练数据 |
| `setup_server.sh` | 服务器环境安装脚本 |
| `run_finetune.sh` | LlamaFactory 微调脚本 |
| `start_vllm.sh` | vLLM 启动脚本 |
| `test_finetune_model.py` | 客户端测试脚本 |

## 九、截图清单（需手动完成）

| 截图 | 内容 |
|------|------|
| 1 | LlamaFactory 微调训练日志（显示 loss 下降） |
| 2 | vLLM 启动成功（`Application startup complete`） |
| 3 | 客户端运行 `test_finetune_model.py` 的输出结果 |
| 4 | （可选）`nvidia-smi` 显示 GPU 显存占用 |
