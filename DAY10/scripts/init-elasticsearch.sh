#!/usr/bin/env bash
# ES 初始化脚本 - 创建索引模板和预置索引
set -euo pipefail

ES_URL="${ES_URL:-http://localhost:9200}"
RESET_INDICES="${RESET_INDICES:-false}"

echo "等待 Elasticsearch 就绪..."
until curl -fsS "$ES_URL/_cluster/health" >/dev/null; do
  sleep 2
done
echo "Elasticsearch 已就绪"

indices=(logs-system-default logs-application-default logs-network-default logs-security-default logs-drain3-template-default logs-drain3-window-default logs-logai-result-default)

# 清理可能误创建的 data stream
for index in "${indices[@]}"; do
  if curl -fsS "$ES_URL/_data_stream/$index" >/dev/null 2>&1; then
    curl -s -X DELETE "$ES_URL/_data_stream/$index" >/dev/null || true
  fi
done

if [ "$RESET_INDICES" = "true" ]; then
  for index in "${indices[@]}"; do
    curl -s -X DELETE "$ES_URL/$index" >/dev/null || true
  done
fi

# 安装 ILM 策略
echo "安装 ILM 策略..."
curl -fsS -X PUT "$ES_URL/_ilm/policy/logs-poc-policy" \
  -H 'Content-Type: application/json' \
  --data-binary @elasticsearch/ilm/logs-ilm-policy.json >/dev/null

# 安装索引模板
echo "安装索引模板..."
curl -fsS -X PUT "$ES_URL/_index_template/logs-template" \
  -H 'Content-Type: application/json' \
  --data-binary @elasticsearch/index-templates/logs-template.json >/dev/null

curl -fsS -X PUT "$ES_URL/_index_template/drain3-template" \
  -H 'Content-Type: application/json' \
  --data-binary @elasticsearch/index-templates/drain3-template.json >/dev/null

curl -fsS -X PUT "$ES_URL/_index_template/logai-template" \
  -H 'Content-Type: application/json' \
  --data-binary @elasticsearch/index-templates/logai-template.json >/dev/null

# 创建预置索引
echo "创建预置索引..."
for index in "${indices[@]}"; do
  curl -fsS -X PUT "$ES_URL/$index" >/dev/null || true
done

echo "Elasticsearch 模板和索引已就绪"
