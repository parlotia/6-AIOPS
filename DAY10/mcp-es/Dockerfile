FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

COPY es_queries.py server.py ./

ENV ES_URL=http://day10-elasticsearch:9200

EXPOSE 8765

HEALTHCHECK --interval=15s --timeout=5s --retries=8 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect(('127.0.0.1',8765)); s.close()"

CMD ["python", "server.py"]
