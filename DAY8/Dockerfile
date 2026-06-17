FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖 (netmiko SSH 需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

# 复制 MCP Server 代码和设备清单
COPY mcp_server.py .
COPY devices.yaml .

EXPOSE 8000

CMD ["python", "mcp_server.py"]
