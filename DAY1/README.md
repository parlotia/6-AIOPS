# AIOps DAY1 - 国内中转站调用 OpenAI API

## 作业背景

通过国内 OpenAI API 中转站（无需翻墙），使用 Python OpenAI 官方库完成文本生成任务。

## 实验环境

| 项目 | 说明 |
|------|------|
| OS | Rocky Linux 9.7 |
| Python | 3.x (虚拟环境) |
| 依赖库 | openai |
| 中转站 | moyu.info |
| Base URL | https://www.moyu.info/v1 |
| 模型 | gpt-4.1-nano |

## 项目结构

```
DAY1/
├── README.md                  # 本文档
└── ai_text_generation.py      # 作业代码 - API调用文本生成
```

## 任务说明

1. 申请国内 OpenAI API 中转站秘钥（本次使用 moyu.info）
2. 使用 OpenAI Python 库通过中转站调用 API 进行文本生成
3. 对打印结果进行截图

## 运行步骤

```bash
# 1. 安装依赖
pip install openai

# 2. 运行代码
cd /netdevops/homework/6.AIOps/DAY1
python ai_text_generation.py
```

## 运行结果

```
============================================================
问题: 请简要解释一下什么是BGP协议，以及它在互联网中的作用？
============================================================

AI回答:
BGP（边界网关协议，Border Gateway Protocol）是一种用于互联网中不同自治系统（AS）
之间交换路由信息的核心协议。它属于路径向量协议，主要负责选择和维护到达不同网络目的地的最佳路径。

在互联网中，BGP的作用包括：
- 路由决策：帮助不同的网络识别最佳的数据传输路径
- 实现互联网的互联互通：确保全球范围内的数据包可以找到路线
- 控制流量和策略：网络管理员可以影响流量的走向
- 支持路由过滤与安全：过滤不合法的路由信息，增强网络安全

============================================================
使用模型: gpt-4.1-nano-2025-04-14
Token用量: completion_tokens=221, prompt_tokens=24, total_tokens=245
============================================================
```

## 知识点

- OpenAI Python 库支持通过 `base_url` 参数切换到任意兼容接口的中转服务
- 中转站实现原理：代理转发请求到 OpenAI 官方 API，国内用户无需翻墙
- `client.chat.completions.create()` 是标准的对话补全接口

## 提交文件清单

| 文件 | 说明 |
|------|------|
| ai_text_generation.py | 作业代码 |
| README.md | 项目说明文档 |
