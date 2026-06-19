"""
Agent EKF - MCP + Ollama 智能日志分析助手

基于 EFK (Elasticsearch + Filebeat + Kibana) + Vector 日志平台,
通过 MCP 工具查询 Elasticsearch 中的路由器 syslog 日志,
结合 Ollama LLM 进行智能分析并输出报告。

工作模式 (两阶段):
  Phase 1: 调用 MCP 工具采集日志数据
  Phase 2: LLM 生成事件列表 + 代码生成总结和建议

使用:
  python agent_ekf.py
"""

import asyncio
import json
import os
import re
import ssl

import httpx
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# === 配置 ===
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://localhost:9443/mcp")
CA_CERT_PATH = os.getenv("CA_CERT_PATH", "certs/server.crt")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://8.160.166.64:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")


def make_ssl_factory(ca_path: str):
    """创建带自定义 CA 证书的 httpx 客户端工厂"""
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


async def call_mcp_tool(session, tool_name: str, arguments: dict = None) -> str:
    """调用 MCP 工具并返回 JSON 文本结果"""
    args = arguments or {}
    result = await session.call_tool(tool_name, args)
    text = ""
    for c in result.content:
        if hasattr(c, "text"):
            text += c.text
    return text


def clean_thinking(text: str) -> str:
    """剥离 Ollama Qwen3 输出中的思考过程，只保留最终答案"""
    if '</think>' in text:
        parts = text.split('</think>')
        text = parts[-1]
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<think>', '', text)
    # 清理 markdown 格式
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'^#{1,4}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # 清理多余空行
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines).strip()


def ask_ollama(system_prompt: str, user_msg: str) -> str:
    """调用 Ollama ChatOllama 并返回清洗后的文本"""
    llm = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        temperature=0.3,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ]
    response = llm.invoke(messages)
    answer = response.content or "(无回答)"
    return clean_thinking(answer)


def parse_ospf_logs(ospf_data: str) -> list[str]:
    """从 MCP 返回的 JSON 中提取 OSPF 日志文本"""
    try:
        data = json.loads(ospf_data)
        if isinstance(data, dict) and "logs" in data:
            return [entry.get("log", "") for entry in data["logs"] if isinstance(entry, dict)]
    except Exception:
        pass
    # fallback: 按行拆分
    return [line for line in ospf_data.splitlines() if line.strip()]


def generate_summary_and_suggestions(ospf_data: str) -> str:
    """根据日志数据生成总结和建议（代码生成，不依赖 LLM）"""
    logs = parse_ospf_logs(ospf_data)

    # 统计事件
    full_events = [e for e in logs if "to FULL" in e]
    down_events = [e for e in logs if "to DOWN" in e]
    errors = [e for e in logs if "ERRRCV" in e or "ERR" in e.split("%")[-1] if "ADJCHG" not in e]

    # 生成总结
    summary = []
    if full_events and down_events:
        summary.append(f"- {len(full_events)} 个 OSPF 邻居关系成功建立（FULL），"
                       f"随后 {len(down_events)} 个邻居关系中断（DOWN）。")
        summary.append("- 需要进一步确认接口状态变化的原因，"
                       "是否为计划内的维护或出现了网络故障。")
    elif full_events:
        summary.append(f"- {len(full_events)} 个 OSPF 邻居关系成功建立，网络状态正常。")
    elif down_events:
        summary.append(f"- {len(down_events)} 个 OSPF 邻居关系中断，网络存在不稳定因素。")
    else:
        summary.append(f"- 共采集到 {len(logs)} 条 OSPF 相关日志，需关注日志趋势。")

    # 生成建议
    suggestions = []
    if down_events:
        # 提取接口名
        intf_match = re.search(r'on\s+(\S+)', down_events[0])
        intf = intf_match.group(1) if intf_match else "相关接口"
        suggestions.append(f"- 检查 {intf} 接口的物理连接和配置。")
        suggestions.append("- 查看相关设备的接口状态和日志，确认是否存在故障或配置变更。")
    suggestions.append("- 监控后续的邻居状态变化，确保网络稳定。")
    if errors:
        suggestions.append("- 核查 OSPF 邻居双方的协议配置是否一致。")

    # 组装
    result = "总结：\n" + "\n".join(summary)
    result += "\n\n建议：\n" + "\n".join(suggestions)
    result += "\n\n如果需要更详细的分析或后续监控，请告知！"
    return result


async def main():
    print(f"{'='*60}")
    print(f"  EFK 日志分析 Agent")
    print(f"  MCP Server: {MCP_SERVER_URL}")
    print(f"  Ollama: {OLLAMA_MODEL} @ {OLLAMA_BASE_URL}")
    print(f"{'='*60}\n")

    factory = make_ssl_factory(CA_CERT_PATH)

    async with streamablehttp_client(MCP_SERVER_URL, httpx_client_factory=factory) as (rs, ws, _sid):
        async with ClientSession(rs, ws) as session:
            await session.initialize()
            print("MCP 连接成功!\n")

            # 列出可用工具
            tools_result = await session.list_tools()
            print(f"可用 MCP 工具 ({len(tools_result.tools)} 个):")
            for t in tools_result.tools:
                desc = t.description or ""
                print(f"  - {t.name}: {desc[:60]}...")

            # 获取用户问题
            default_question = "帮我分析最近30分钟内关于OSPF的日志，给我一个分析报告"
            user_input = input(f"\n请输入问题 (回车使用默认: {default_question}): ").strip()
            question = user_input if user_input else default_question

            print(f"\n模型问：{question}")
            print("-" * 40)

            # ---- Phase 1: 采集数据 ----
            print("\n[Phase 1] 采集日志数据...\n")

            stats_data = await call_mcp_tool(session, "get_log_stats", {"minutes": 30})
            print(f"  get_log_stats(30min) -> OK ({len(stats_data)} chars)")

            ospf_data = await call_mcp_tool(session, "get_ospf_logs", {"minutes": 30})
            print(f"  get_ospf_logs(30min) -> OK ({len(ospf_data)} chars)")

            keyword = "OSPF"
            for kw in ["OSPF", "BGP", "SSH", "interface", "ACL", "EIGRP"]:
                if kw.lower() in question.lower():
                    keyword = kw
                    break
            search_data = await call_mcp_tool(session, "search_logs", {
                "keyword": keyword, "minutes": 30, "limit": 50
            })
            print(f"  search_logs('{keyword}', 30min) -> OK ({len(search_data)} chars)")

            # ---- Phase 2: LLM 生成事件列表 ----
            print(f"\n[Phase 2] 调用 Ollama 分析...\n")

            system_prompt = (
                "你是网络运维日志分析助手。\n"
                "请基于以下OSPF日志，输出简洁的事件列表。\n"
                "严格要求：纯文本，不要markdown，不要加粗，不要分隔线。\n"
                "只输出事件列表，不要输出总结、建议或其他内容。\n"
                "格式示例：\n"
                "在最近的30分钟内，关于OSPF的日志显示了以下情况：\n"
                "1. 在HH:MM:SS，邻居X.X.X.X在XXX接口上状态由AAA变为BBB，表示邻居关系建立完成。\n"
                "2. 在HH:MM:SS，邻居X.X.X.X在XXX接口上状态由AAA变为BBB，表示邻居关系中断。\n"
            )

            user_msg = f"以下是OSPF相关日志：\n{ospf_data}\n\n请输出事件列表，不要加总结和建议。"

            events_text = ask_ollama(system_prompt, user_msg)

            # ---- Phase 3: 代码生成总结和建议 ----
            summary_text = generate_summary_and_suggestions(ospf_data)

            # 输出完整报告
            print(events_text)
            print()
            print(summary_text)
            print(f"\n{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
