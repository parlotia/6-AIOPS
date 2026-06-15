#!/usr/bin/env python3
# -*- coding=utf-8 -*-
"""
AIOps DAY6 作业 - 使用LlamaFactory微调模型, 并用vLLM拉起来测试
"""
from openai import OpenAI
import re

client = OpenAI(
    api_key="llama_factory_qwen3_finetune",
    base_url="http://8.160.166.64:8000/v1/",
)

openai_model = "llama_factory_qwen3_finetune"

# ----------普通问题和回答----------
response = client.chat.completions.create(
    model=openai_model,
    temperature=0,
    messages=[
        {"role": "user", "content": "我的工作经历是什么？"},
    ],
)

content = response.choices[0].message.content
# 清理模型输出中的标签残留
content = re.sub(r'<[^>]+>', '', content)
print(content.strip())
