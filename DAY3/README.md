# AIOps DAY3 - OpenAI Agent Function Call 查询路由表

## 作业背景

使用 OpenAI Function Call（工具调用）实现 AI Agent 自动查询网络设备路由表，通过 Netmiko SSH 真实采集路由器 `show ip route`，AI 自动判断去往目标IP应该经过哪台路由器及下一跳地址。

## 实验环境

| 项目 | 说明 |
|------|------|
| OS | Rocky Linux 9.7 |
| Python | 3.x (虚拟环境) |
| 依赖库 | openai, netmiko |
| 中转站 | moyu.info |
| Base URL | https://www.moyu.info/v1 |
| 模型 | gpt-4.1-nano |
| 路由器 | C8Kv1 (10.10.1.201), C8Kv2 (10.10.1.202) |

## 项目结构

```
DAY3/
├── README.md                  # 本文档
└── ai_agent_route_query.py    # 作业代码 - Agent Function Call查询路由
```

## 任务说明

1. 定义两个工具函数：`get_all_devices_name`（获取设备清单）和 `get_device_ip_route`（SSH采集路由表）
2. AI Agent 自动编排调用顺序：先获取设备列表，再逐一查询路由表
3. AI 根据路由表分析去往目标IP的最佳路径，返回经过的路由器和下一跳地址

## 运行步骤

```bash
pip install openai netmiko
cd /netdevops/homework/6.AIOps/DAY3
python ai_agent_route_query.py
```

## 提交文件清单

| 文件 | 说明 |
|------|------|
| ai_agent_route_query.py | 作业代码 - Agent Function Call |
| README.md | 项目说明文档 |
