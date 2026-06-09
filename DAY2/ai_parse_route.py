"""
AIOps DAY2 作业 - AI分析并结构化输出 "show ip route"
使用OpenAI API（moyu.info中转）解析思科路由表，输出结构化数据并格式化打印
"""

import json
import pprint
from openai import OpenAI

# 中转站配置
API_KEY = "sk-z0uiNLfX7CHH2EPQGxxOWHKi1vaT3ORAz1gMAFBsvy9Id9hj"
BASE_URL = "https://www.moyu.info/v1"

# 思科设备 show ip route 原始输出
show_ip_route = """
S*      0.0.0.0/0 [1/0] via 196.21.5.1
      10.0.0.0/8 is variably subnetted, 2 subnets, 2 masks
C        10.1.1.0/24 is directly connected, GigabitEthernet2
L        10.1.1.1/32 is directly connected, GigabitEthernet2
      172.16.0.0/24 is subnetted, 1 subnets
S        172.16.1.0 [1/0] via 196.21.5.6
S     196.21.1.0/24 [1/0] via 196.21.5.8
      196.21.5.0/24 is variably subnetted, 2 subnets, 2 masks
C        196.21.5.0/24 is directly connected, GigabitEthernet1
L        196.21.5.211/32 is directly connected, GigabitEthernet1
"""

# 创建OpenAI客户端
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# 使用AI解析路由表
prompt = f"""请分析以下思科设备的 "show ip route" 输出，将每条路由提取为结构化数据。

每条路由需要包含以下字段：
- type: 路由类型（S/S* 为 "Static"，C 为 "Connected"，L 为 "Connected"）
- dst_net: 目的网络（含掩码，如果原文没有掩码长度则根据上下文补全）
- via: 下一跳地址（直连路由为 None）
- connect_if: 连接接口（静态路由为 None）

请以JSON格式返回，格式为：
{{"route": [{{...}}, {{...}}]}}

show ip route 输出：
{show_ip_route}

注意：只返回JSON数据，不要其他解释文字。"""

response = client.chat.completions.create(
    model="gpt-5.4-nano",
    messages=[
        {"role": "user", "content": prompt}
    ]
)

# 提取AI返回的JSON
ai_response = response.choices[0].message.content
# 清理可能的markdown代码块标记
ai_response = ai_response.strip()
if ai_response.startswith("```"):
    ai_response = ai_response.split("\n", 1)[1]
if ai_response.endswith("```"):
    ai_response = ai_response.rsplit("```", 1)[0]
ai_response = ai_response.strip()

# 解析JSON
route_data = json.loads(ai_response)

# 打印结构化输出的原始结果
print("=" * 70)
print("结构化输出的原始结果:")
print("=" * 70)
pprint.pprint(route_data)

# 格式化打印
print("\n" + "=" * 70)
print("格式化打印效果:")
print("=" * 70)
for route in route_data["route"]:
    dst = route["dst_net"]
    via = route["via"] if route["via"] else "N/A"
    rtype = route["type"]
    iface = route["connect_if"] if route["connect_if"] else "N/A"
    print(f"目的网络：{dst:<20}下一跳地址：{via:<16}路由类型：{rtype:<12}连接接口：{iface}")

print("=" * 70)
