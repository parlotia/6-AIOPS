"""
Agent - MCP + LLM 智能网络运维助手

两阶段工作模式:
  Phase 1: 调用 MCP 工具采集设备数据
  Phase 2: 将数据 + 用户问题发送给 LLM 分析回答

作业要求的两个问题:
  Q1: C8Kv1的OSPF邻居信息是什么?
  Q2: 列出所有设备的OSPF路由信息?
"""

import asyncio
import json
import os
import re
import ssl

import httpx
from openai import AsyncOpenAI
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# === Config ===
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://localhost:9443/mcp")
CA_CERT_PATH = os.getenv("CA_CERT_PATH", "certs/server.crt")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://8.160.166.64:8000/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-4b-instruct")
MAX_TOKENS = 1024

# Strip thinking tags from LLM output (Qwen3 Instruct)
_THINK_OPEN = '<' + 'think' + '>'
_THINK_CLOSE = '</' + 'think' + '>'


def clean_output(text):
    """Remove thinking tags from LLM output."""
    while _THINK_OPEN in text:
        start = text.index(_THINK_OPEN)
        end_idx = text.find(_THINK_CLOSE, start)
        end = (end_idx + len(_THINK_CLOSE)) if end_idx >= 0 else len(text)
        text = text[:start] + text[end:]
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines).strip()


def make_ssl_factory(ca_path):
    """Create httpx client factory with custom CA cert."""
    def factory(headers=None, timeout=None, auth=None):
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(ca_path)
        kw = {"follow_redirects": True, "verify": ctx}
        if headers:
            kw["headers"] = headers
        if timeout:
            kw["timeout"] = timeout
        if auth:
            kw["auth"] = auth
        return httpx.AsyncClient(**kw)
    return factory


async def call_mcp_tool(session, tool_name, arguments=None):
    """调用 MCP 工具并返回文本结果 (自动剥离 raw_output)"""
    args = arguments or {}
    result = await session.call_tool(tool_name, args)
    text = ""
    for c in result.content:
        if hasattr(c, "text"):
            text += c.text
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data.pop("raw_output", None)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item.pop("raw_output", None)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return text


async def ask_llm(system_prompt, user_msg):
    """调用 LLM 并返回清理后的文本"""
    llm = AsyncOpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    response = await llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=MAX_TOKENS,
    )
    answer = response.choices[0].message.content or "(无回答)"
    return clean_output(answer)


# ==============================================================================
# Q1: 单设备 OSPF 邻居查询
# ==============================================================================
async def run_q1(session):
    """C8Kv1的OSPF邻居信息是什么?"""
    question = "C8Kv1的OSPF邻居信息是什么?"
    print(f"\n{'='*60}")
    print(f"问题 1/2: {question}")
    print(f"{'='*60}")

    # Phase 1: 采集
    print(f"\n[Phase 1] 采集数据...")
    data = await call_mcp_tool(session, "get_ios_ospf_neighbor_info", {"device_name": "C8Kv1"})
    print(f"  get_ios_ospf_neighbor_info(C8Kv1) -> OK ({len(data)} chars)")

    # Phase 2: 分析
    print(f"\n[Phase 2] 调用 LLM 分析...")
    system_prompt = (
        "你是一个专业的网络运维助手。"
        "请基于提供的实时设备数据回答问题。使用中文回答。"
    )
    user_msg = (
        f"## 实时设备数据\n### get_ios_ospf_neighbor_info\n{data}\n\n"
        f"## 问题\n{question}\n\n"
        "请按以下格式输出:\n"
        "- **邻居 ID**: xxx\n"
        "- **优先级**: x\n"
        "- **状态**: FULL/DR (解释含义)\n"
        "- **死亡时间**: xxx\n"
        "- **IP地址**: xxx\n"
        "- **接口**: xxx\n"
    )
    return await ask_llm(system_prompt, user_msg)


# ==============================================================================
# Q2: 多设备 OSPF 路由查询 (逐设备调 LLM，最后拼接)
# ==============================================================================
async def run_q2(session):
    """列出所有设备的OSPF路由信息"""
    question = "列出所有设备的OSPF路由信息? 注意我只关心OSPF路由, 不要显示其他无关路由和信息"
    print(f"\n{'='*60}")
    print(f"问题 2/2: {question}")
    print(f"{'='*60}")

    devices = ["C8Kv1", "C8Kv2"]

    # Phase 1: 逐设备采集路由数据
    print(f"\n[Phase 1] 采集数据...")
    route_data = {}
    for dev in devices:
        data = await call_mcp_tool(session, "get_ip_route_info", {"device_name": dev})
        route_data[dev] = data
        print(f"  get_ip_route_info({dev}) -> OK ({len(data)} chars)")

    # Phase 2: 逐设备调 LLM 分析 (避免小模型一次处理多设备时遗漏)
    print(f"\n[Phase 2] 逐设备调用 LLM 分析...")
    system_prompt = (
        "你是一个专业的网络运维助手。"
        "请基于提供的路由表数据，只列出OSPF路由(标识为'O'的条目)，过滤掉直连(C)、本地(L)、静态(S)等其他路由。"
        "使用中文回答，按以下格式输出:\n"
        "***设备 XXX OSPF 路由信息: ***\n"
        "路由条目 x.x.x.x/x\n"
        "距离: 110 开销: x\n"
        "下一跳: x.x.x.x (接口 xxx)\n"
        "更新时间: xx:xx:xx\n"
    )

    results = []
    for dev in devices:
        print(f"  分析 {dev} 路由...")
        user_msg = (
            f"## 设备 {dev} 路由表数据\n{route_data[dev]}\n\n"
            f"请只列出 {dev} 的OSPF路由(O标识)，过滤其他协议路由。"
        )
        answer = await ask_llm(system_prompt, user_msg)
        results.append(answer)
        print(f"  -> OK")

    # 拼接所有设备结果 + 说明
    final = "\n\n---\n\n".join(results)
    final += (
        "\n\n---\n\n"
        "***说明: ***\n"
        "1. OSPF路由标识为协议类型 'O'，其他协议（如直连 'C'、静态 'S'）已过滤。"
    )
    return final


# ==============================================================================
# 主入口
# ==============================================================================
async def main():
    print(f"连接 MCP Server: {MCP_SERVER_URL}")
    factory = make_ssl_factory(CA_CERT_PATH)

    async with streamablehttp_client(MCP_SERVER_URL, httpx_client_factory=factory) as (rs, ws, _sid):
        async with ClientSession(rs, ws) as session:
            await session.initialize()
            print("MCP 连接成功!\n")

            tools_result = await session.list_tools()
            print(f"可用 MCP 工具 ({len(tools_result.tools)} 个):")
            for t in tools_result.tools:
                print(f"  - {t.name}")

            # Q1
            answer1 = await run_q1(session)
            print(f"\n{'='*60}")
            print(f"回答:")
            print(f"{'='*60}")
            print(answer1)
            print(f"{'='*60}\n")

            # Q2
            answer2 = await run_q2(session)
            print(f"\n{'='*60}")
            print(f"回答:")
            print(f"{'='*60}")
            print(answer2)
            print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
