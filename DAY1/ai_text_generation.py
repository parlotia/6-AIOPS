"""
AIOps DAY1 作业 - 使用国内中转站访问OpenAI API进行文本生成
中转站: moyu.info
"""

import os
from openai import OpenAI

# 设置API Key和中转站地址
API_KEY = "sk-z0uiNLfX7CHH2EPQGxxOWHKi1vaT3ORAz1gMAFBsvy9Id9hj"
BASE_URL = "https://www.moyu.info/v1"

# 创建OpenAI客户端（通过中转站访问）
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# 发送请求 - 问一个网络工程相关的问题
response = client.chat.completions.create(
    model="gpt-5.4-nano",
    messages=[
        {"role": "user", "content": "请简要解释一下什么是BGP协议，以及它在互联网中的作用？"}
    ]
)

# 打印AI生成的回答
print("=" * 60)
print("问题: 请简要解释一下什么是BGP协议，以及它在互联网中的作用？")
print("=" * 60)
print(f"\nAI回答:\n{response.choices[0].message.content}")
print("\n" + "=" * 60)
print(f"使用模型: {response.model}")
print(f"Token用量: {response.usage}")
print("=" * 60)
