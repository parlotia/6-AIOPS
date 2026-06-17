"""
MCP Server - 网络设备信息 MCP 工具封装

将以下三个函数封装为 MCP (Model Context Protocol) 工具:
  1. get_all_devices_name()                  - 获取所有网络设备名称
  2. get_ios_ospf_neighbor_info(device_name) - 获取指定设备的 OSPF 邻居信息
  3. get_ip_route_info(device_name)          - 获取指定设备的 IP 路由表

使用 FastMCP + streamable-http 传输协议，通过 Nginx HTTPS 反向代理对外提供服务。
"""

import json
import os
import yaml
from mcp.server.fastmcp import FastMCP
from netmiko import ConnectHandler

# ==============================================================================
# 初始化 MCP Server
# ==============================================================================
mcp = FastMCP(
    "network-tools",
    host="0.0.0.0",
    port=8000,
    streamable_http_path="/mcp",
)

# 设备清单 YAML 路径
DEVICES_YAML = os.getenv("DEVICES_YAML", "devices.yaml")


# ==============================================================================
# 辅助函数
# ==============================================================================
def qyt_netmiko_send_command(ip, username, password, platform, command):
    """
    封装 Netmiko SSH 命令执行。
    通过 SSH 连接到指定设备并执行命令，返回命令输出字符串。
    """
    conn = ConnectHandler(
        device_type=platform,
        host=ip,
        username=username,
        password=password,
        timeout=15,
    )
    output = conn.send_command(command)
    conn.disconnect()
    return output.strip()


def _find_device(device_name: str) -> dict:
    """根据设备名称查找设备配置"""
    for dev in get_all_devices_name():
        if dev["name"].upper() == device_name.upper():
            return dev
    return {}


# ==============================================================================
# 基础函数 (作业要求)
# ==============================================================================
def get_all_devices_name() -> list:
    """
    获取所有设备的名称。

    返回: 字典列表, 每个字典包含:
      'name', 'platform', 'ip', 'username', 'password'

    示例返回值:
      [
        {'name': 'C8Kv1', 'platform': 'cisco_ios', 'ip': '10.10.1.201',
         'username': 'admin', 'password': 'Cisc0123'},
        {'name': 'C8Kv2', 'platform': 'cisco_ios', 'ip': '10.10.1.202',
         'username': 'admin', 'password': 'Cisc0123'}
      ]
    """
    with open(DEVICES_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("devices", [])


# ==============================================================================
# MCP Tool 1: 获取所有设备名称
# ==============================================================================
@mcp.tool()
def mcp_get_all_devices_name() -> str:
    """
    获取所有网络设备的基本信息。
    返回包含设备名称、平台类型、IP 地址等信息的 JSON 列表。
    """
    devices = get_all_devices_name()
    result = []
    for dev in devices:
        result.append({
            "name": dev["name"],
            "platform": dev["platform"],
            "ip": dev["ip"],
        })
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==============================================================================
# MCP Tool 2: 获取指定设备的 OSPF 邻居信息
# ==============================================================================
@mcp.tool()
def get_ios_ospf_neighbor_info(device_name: str) -> str:
    """
    获取指定设备的 OSPF 邻居状态信息。

    参数:
      device_name: 设备名称 (如 C8Kv1、C8Kv2)

    通过 SSH 执行 'show ip ospf neighbor' 命令，返回 OSPF 邻居表。
    如果未找到设备, 返回 '设备未找到'。
    """
    dev = _find_device(device_name)
    if not dev:
        return "设备未找到"

    output = qyt_netmiko_send_command(
        dev["ip"], dev["username"], dev["password"],
        dev["platform"], "show ip ospf neighbor"
    )

    # 解析 OSPF 邻居表
    neighbors = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0] not in ("", "Neighbor") and not parts[0].startswith("-"):
            try:
                neighbors.append({
                    "neighbor_id": parts[0],
                    "priority": parts[1],
                    "state": parts[2],
                    "dead_time": parts[3],
                    "address": parts[4],
                    "interface": parts[5] if len(parts) > 5 else "",
                })
            except IndexError:
                pass

    return json.dumps({
        "device": dev["name"],
        "ip": dev["ip"],
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
        "raw_output": output,
    }, ensure_ascii=False, indent=2)


# ==============================================================================
# MCP Tool 3: 获取指定设备的 IP 路由表信息
# ==============================================================================
@mcp.tool()
def get_ip_route_info(device_name: str) -> str:
    """
    获取指定设备的 IP 路由表信息。

    参数:
      device_name: 设备名称 (如 C8Kv1、C8Kv2)

    通过 SSH 执行 'show ip route' 命令，返回完整路由表。
    如果未找到设备, 返回 '设备未找到'。
    """
    dev = _find_device(device_name)
    if not dev:
        return "设备未找到"

    output = qyt_netmiko_send_command(
        dev["ip"], dev["username"], dev["password"],
        dev["platform"], "show ip route"
    )

    # 解析路由条目
    routes = []
    in_table = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Gateway of last resort"):
            in_table = True
            continue
        if not in_table:
            continue
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            route_code = parts[0]
            if route_code in ("C", "L", "S", "R", "O", "D", "B", "E1", "E2", "IA"):
                routes.append(stripped)

    return json.dumps({
        "device": dev["name"],
        "ip": dev["ip"],
        "route_count": len(routes),
        "routes": routes,
        "raw_output": output,
    }, ensure_ascii=False, indent=2)


# ==============================================================================
# 入口
# ==============================================================================
if __name__ == "__main__":
    print("Starting MCP Network Tools Server (streamable-http on :8000/mcp)...")
    mcp.run(transport="streamable-http")
