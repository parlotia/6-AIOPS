#!/usr/bin/env python3
# -*- coding=utf-8 -*-
"""
AIOps DAY4 作业 - 测试Ollama Agent (OpenAI Agents SDK)
使用阿里云GPU服务器上部署的Ollama服务，通过OpenAI兼容API调用qwen3模型
"""
# ~~~~~~~~~~~~~准备并且设置环境变量~~~~~~~~~~~~~~~~
from agents import set_tracing_disabled, Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel

# ~~~~~~~~~~~~~~~非OpenAI需要关闭Tracing~~~~~~~~~~~~~~~~
# 禁用所有Tracing, 使用非OpenAI服务必须要禁用Tracing
set_tracing_disabled(True)

# ~~~~~~~~~~~~~~~使用ollama~~~~~~~~~~~~~~~~~~
external_client = AsyncOpenAI(
    api_key="ollama",
    base_url="http://8.160.165.24:11434/v1/",
)

agent = Agent(
    name="Assistant",
    # ~~~~~~~~~~~~~使用Ollama的模型 ~~~~~~~~~~~~~~
    model=OpenAIChatCompletionsModel(
        model="qwen3:0.6b",
        openai_client=external_client,
    ),
)


async def main():
    result = await Runner.run(agent, "天空为什么是蓝色的?")
    return result.final_output


if __name__ == "__main__":
    import time
    import asyncio

    start_time = time.time()
    final_result = asyncio.run(main())

    # 处理qwen3的</think>输出
    result_split = final_result.split("</think>")
    if len(result_split) > 1:
        print(result_split[1])
    else:
        print(final_result)

    end_time = time.time()
    print(f"\n运行时间: {end_time - start_time:.2f} 秒")
