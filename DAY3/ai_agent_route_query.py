"""
AIOps DAY3 作业 - OpenAI Agent Function Call(函数调用)查询路由表
使用Netmiko真实采集路由器 show ip route，通过AI Function Call自动判断
去往目标IP应该经过哪台路由器以及下一跳地址
"""

import json
from netmiko import ConnectHandler
from openai import OpenAI

# ============================================================
# 设备清单
# ============================================================
DEVICES = {
    "C8Kv1": {
        "device_type": "cisco_ios",
        "host": "10.10.1.201",
        "username": "admin",
        "password": "Cisc0123",
    },
    "C8Kv2": {
        "device_type": "cisco_ios",
        "host": "10.10.1.202",
        "username": "admin",
        "password": "Cisc0123",
    },
}

# ============================================================
# OpenAI 中转站配置
# ============================================================
API_KEY = "sk-z0uiNLfX7CHH2EPQGxxOWHKi1vaT3ORAz1gMAFBsvy9Id9hj"
BASE_URL = "https://www.moyu.info/v1"
MODEL = "gpt-4.1-nano"

# ============================================================
# Agent 工具函数
# ============================================================


def get_all_devices_name() -> str:
    """获取所有设备的名称和管理IP地址"""
    result = []
    for name, info in DEVICES.items():
        result.append({"device_name": name, "ip": info["host"]})
    return json.dumps(result, ensure_ascii=False)


def get_device_ip_route(device_name: str) -> str:
    """通过Netmiko SSH登录指定设备，采集 show ip route 原始输出"""
    if device_name not in DEVICES:
        return json.dumps({"error": f"设备 {device_name} 不存在"}, ensure_ascii=False)

    device_info = DEVICES[device_name]
    try:
        print(f"  [Netmiko] 正在连接 {device_name} ({device_info['host']})...")
        conn = ConnectHandler(**device_info)
        output = conn.send_command("show ip route")
        conn.disconnect()
        print(f"  [Netmiko] {device_name} 路由表采集完成")
        return json.dumps(
            {"device_name": device_name, "route_table": output},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"error": f"连接 {device_name} 失败: {str(e)}"},
            ensure_ascii=False,
        )


# ============================================================
# OpenAI Function Call 工具定义
# ============================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_all_devices_name",
            "description": "获取所有网络设备的名称和管理IP地址列表",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_ip_route",
            "description": "通过SSH登录指定设备，获取该设备的 show ip route 路由表原始输出",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_name": {
                        "type": "string",
                        "description": "设备名称，如 C8Kv1、C8Kv2",
                    }
                },
                "required": ["device_name"],
            },
        },
    },
]

# 函数名到实际函数的映射
FUNCTION_MAP = {
    "get_all_devices_name": get_all_devices_name,
    "get_device_ip_route": get_device_ip_route,
}


# ============================================================
# 主流程
# ============================================================
def main():
    # 创建OpenAI客户端
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    # 用户提问
    user_question = (
        "帮我查一下去往172.16.1.10这台服务器，"
        "我应该通过哪台路由器去抵达，并告诉我抵达的下一跳地址"
    )

    print("=" * 70)
    print(f"用户提问: {user_question}")
    print("=" * 70)

    # 初始化对话消息
    messages = [
        {
            "role": "system",
            "content": (
                "你是一名网络工程师助手。你可以通过工具函数查询网络设备信息和路由表，"
                "帮助用户分析网络路径。请先获取设备列表，再逐一查询路由表进行分析。"
            ),
        },
        {"role": "user", "content": user_question},
    ]

    # Agent循环：持续处理直到AI给出最终回答
    while True:
        print("\n[Agent] 正在请求AI分析...")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        # 如果AI没有调用工具，说明已得出结论
        if not assistant_message.tool_calls:
            print("\n" + "=" * 70)
            print("AI 最终回答:")
            print("=" * 70)
            print(assistant_message.content)
            print("=" * 70)
            break

        # 处理工具调用
        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"\n[Agent] AI调用函数: {func_name}({func_args})")

            # 执行对应函数
            func = FUNCTION_MAP[func_name]
            if func_args:
                result = func(**func_args)
            else:
                result = func()

            print(f"[Agent] 函数返回: {result[:200]}{'...' if len(result) > 200 else ''}")

            # 将函数结果返回给AI
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    print(f"\n使用模型: {MODEL}")


if __name__ == "__main__":
    main()
