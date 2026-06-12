#!/usr/bin/env python3
# -*- coding=utf-8 -*-
"""
AIOps DAY5 作业 - 测试vLLM (OpenAI兼容API)
通过ModelScope下载模型，使用vLLM拉起模型，并通过OpenAI兼容接口进行测试
"""
from openai import OpenAI

client = OpenAI(api_key="vllm",
                base_url="http://8.160.176.138:8000/v1/",
                )
openai_model = "qwen3-4b"

response = client.chat.completions.create(
    model=openai_model,
    messages=[
        {"role": "system", "content": "你是一个聪明的助手。"},

        # --------------------------------普通问题和回答--------
        {"role": "user", "content": "天空为什么是蓝色的?"}
    ],
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)

print(response.choices[0].message.content)
