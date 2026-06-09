# AIOps DAY2 - AI分析并结构化输出 show ip route

## 作业背景

使用 AI（OpenAI API）解析思科设备 `show ip route` 命令的原始输出，自动提取结构化路由信息并格式化打印。

## 实验环境

| 项目 | 说明 |
|------|------|
| OS | Rocky Linux 9.7 |
| Python | 3.x (虚拟环境) |
| 依赖库 | openai |
| 中转站 | moyu.info |
| Base URL | https://www.moyu.info/v1 |
| 模型 | gpt-5.4-nano |

## 项目结构

```
DAY2/
├── README.md              # 本文档
└── ai_parse_route.py      # 作业代码 - AI解析路由表
```

## 任务说明

1. 将思科设备 `show ip route` 输出作为输入发送给 AI
2. AI 解析后返回结构化 JSON 数据（包含 type/dst_net/via/connect_if 字段）
3. 格式化打印结构化结果

## 运行步骤

```bash
pip install openai
cd /netdevops/homework/6.AIOps/DAY2
python ai_parse_route.py
```

## 提交文件清单

| 文件 | 说明 |
|------|------|
| ai_parse_route.py | 作业代码 |
| README.md | 项目说明文档 |
