"""Elasticsearch MCP 服务（Streamable HTTP）。

完全使用上课代码，额外添加 search_logs 工具供 Agent 搜索原始日志。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

import es_queries


mcp = FastMCP(
    "logai-es",
    host="0.0.0.0",
    port=8765,
)


def _run_json_tool(tool_name: str, fn: Callable[[], Any]) -> str:
    try:
        payload = fn()
    except Exception as exc:
        payload = {
            "ok": False,
            "tool": tool_name,
            "error": str(exc),
        }
    return json.dumps(payload, ensure_ascii=False)


def _safe_size(value: int | str, default: int = 10, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, 1), maximum)


# ---------------------------------------------------------------------------
# 老师代码: MCP Resources
# ---------------------------------------------------------------------------

@mcp.resource(
    "logai://help",
    name="logai-query-help",
    description="AIOps2026 LogAI/Elasticsearch MCP 查询说明，列出日志、异常事件和 evidence pack 资源 URI。",
)
def logai_query_help() -> str:
    return "\n".join(
        [
            "# AIOps2026 LogAI MCP 资源",
            "",
            "本 MCP 供日志与告警 RCA Agent 查询 Elasticsearch 中的日志异常、规则聚合和事件证据包。",
            "Agent 应先读取本 help，再按任务选择资源或工具；不要猜测其他 URI。",
            "",
            "## 资源 URI 模板",
            "",
            "- `logai://summary`：查看 logs-* 索引文档量和原始日志总量。",
            "- `logai://rules`：聚合 anomaly_type 与 severity 分布。",
            "- `logai://anomalies/top/{size}`：按异常分数列出 Top 事件。",
            "- `logai://anomalies/severity/{severity}/{size}`：按严重级别列出异常。",
            "- `logai://anomaly/{event_id}`：读取单个异常事件完整文档。",
            "- `logai://evidence/{event_id}`：为异常事件生成 evidence pack。",
            "",
            "## 工具",
            "",
            "- `search_logs(keyword, minutes, limit)`：按关键字搜索原始日志。",
            "- `get_ospf_logs(minutes)`：获取 OSPF 相关日志。",
            "- `get_log_stats(minutes)`：获取日志统计摘要。",
            "",
            "## 排查建议",
            "",
            "- 日志查询先看 `logai://summary` 和 `logai://rules`。",
            "- 告警 RCA 先定位事件 ID，再读取 `logai://evidence/{event_id}`。",
            "- 输出时必须说明查询窗口、事件 ID、设备、对象、状态和不确定性。",
        ]
    )


@mcp.resource(
    "logai://summary",
    name="logai-pipeline-summary",
    description="读取 logs-* 索引文档量与原始日志总量。",
)
def logai_pipeline_summary_resource() -> str:
    return get_pipeline_summary()


@mcp.resource(
    "logai://rules",
    name="logai-anomaly-rules",
    description="读取异常规则类型与严重级别聚合统计。",
)
def logai_anomaly_rules_resource() -> str:
    return aggregate_anomaly_rules()


@mcp.resource(
    "logai://anomalies/top/{size}",
    name="logai-top-anomalies",
    description="按异常分数读取 Top N 异常事件。",
)
def logai_top_anomalies_resource(size: str) -> str:
    return list_top_anomalies(_safe_size(size))


@mcp.resource(
    "logai://anomalies/severity/{severity}/{size}",
    name="logai-anomalies-by-severity",
    description="按严重级别读取异常事件。",
)
def logai_anomalies_by_severity_resource(severity: str, size: str) -> str:
    return list_anomalies_by_severity(severity, _safe_size(size))


@mcp.resource(
    "logai://anomaly/{event_id}",
    name="logai-anomaly-detail",
    description="读取单个异常事件完整文档。",
)
def logai_anomaly_detail_resource(event_id: str) -> str:
    return get_anomaly_detail(event_id)


@mcp.resource(
    "logai://evidence/{event_id}",
    name="logai-evidence-pack",
    description="读取单个异常事件的 RCA evidence pack。",
)
def logai_evidence_pack_resource(event_id: str) -> str:
    return build_evidence_pack(event_id)


# ---------------------------------------------------------------------------
# 老师代码: MCP Tools (异常检测相关)
# ---------------------------------------------------------------------------

@mcp.tool()
def get_pipeline_summary() -> str:
    """获取 logs-* 各索引文档数量与原始日志总数。"""
    return _run_json_tool("get_pipeline_summary", es_queries.get_pipeline_summary)


@mcp.tool()
def aggregate_anomaly_rules() -> str:
    """聚合 anomaly_type 与 severity 分布（规则触发统计）。"""
    return _run_json_tool("aggregate_anomaly_rules", es_queries.aggregate_anomaly_rules)


@mcp.tool()
def list_top_anomalies(size: int = 5) -> str:
    """按 anomaly_score 倒序列出 Top 异常事件。size 默认 5。"""
    return _run_json_tool("list_top_anomalies", lambda: es_queries.list_top_anomalies(size=size))


@mcp.tool()
def list_anomalies_by_severity(severity: str, size: int = 100) -> str:
    """按严重度列出异常：severity 为 high 或 medium，按分数倒序。"""
    return _run_json_tool(
        "list_anomalies_by_severity",
        lambda: es_queries.list_anomalies_by_severity(severity=severity, size=size),
    )


@mcp.tool()
def get_anomaly_detail(event_id: str) -> str:
    """按异常事件 ID 获取完整文档。"""
    return _run_json_tool("get_anomaly_detail", lambda: es_queries.get_anomaly_detail(event_id))


@mcp.tool()
def build_evidence_pack(anomaly_event_id: str) -> str:
    """为指定异常事件生成 evidence pack（含模板样本与窗口统计）。"""
    return _run_json_tool(
        "build_evidence_pack",
        lambda: es_queries.build_evidence_pack(anomaly_event_id),
    )


# ---------------------------------------------------------------------------
# 额外工具: 原始日志搜索 (供 Agent 分析使用)
# ---------------------------------------------------------------------------

def _format_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+08:00")


@mcp.tool()
def search_logs(keyword: str = "", minutes: int = 30, limit: int = 100) -> str:
    """搜索最近 N 分钟内的原始日志。

    参数:
      keyword: 搜索关键字 (如 OSPF, SSH, BGP, interface 等)，为空则返回全部日志
      minutes: 时间范围，最近多少分钟，默认 30
      limit: 返回最大条数，默认 100

    返回: JSON 格式的日志列表。
    """
    es = es_queries.get_es()
    now = datetime.now(timezone(timedelta(hours=8)))
    start = now - timedelta(minutes=minutes)

    must_clauses = [
        {"range": {"@timestamp": {"gte": _format_time(start), "lte": _format_time(now)}}}
    ]
    if keyword:
        must_clauses.append({
            "query_string": {
                "query": f"*{keyword}*",
                "fields": ["message", "normalized_message", "*"]
            }
        })

    query = {
        "size": limit,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {"bool": {"must": must_clauses}}
    }

    try:
        resp = es.search(index="logs-network-default,logs-security-default,logs-system-default,logs-application-default", body=query)
    except Exception as e:
        return json.dumps({"error": f"ES 查询失败: {str(e)}"}, ensure_ascii=False)

    hits = resp.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    results = []
    for hit in hits.get("hits", []):
        src = hit["_source"]
        results.append({
            "timestamp": src.get("@timestamp", ""),
            "message": src.get("message", ""),
            "log_level": src.get("log", {}).get("level", ""),
            "host": src.get("host", {}).get("name", ""),
            "service": src.get("service", {}).get("name", ""),
        })

    return json.dumps({
        "total_hits": total,
        "returned": len(results),
        "time_range": f"{start.strftime('%H:%M:%S')} ~ {now.strftime('%H:%M:%S')}",
        "keyword": keyword or "(全部)",
        "logs": results,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_ospf_logs(minutes: int = 30) -> str:
    """获取最近 N 分钟内的 OSPF 相关日志。

    参数:
      minutes: 时间范围，默认 30 分钟

    返回: OSPF 邻居状态变化、接口状态等日志。
    """
    es = es_queries.get_es()
    now = datetime.now(timezone(timedelta(hours=8)))
    start = now - timedelta(minutes=minutes)

    query = {
        "size": 200,
        "sort": [{"@timestamp": {"order": "asc"}}],
        "query": {
            "bool": {
                "must": [
                    {"range": {"@timestamp": {"gte": _format_time(start), "lte": _format_time(now)}}},
                    {
                        "query_string": {
                            "query": "OSPF OR ospf OR OSPF-5 OR OSPF-4 OR OSPF-3 OR neighbor OR adjacency OR LOADING OR FULL OR DR OR BDR",
                            "fields": ["message", "normalized_message", "*"]
                        }
                    }
                ]
            }
        }
    }

    try:
        resp = es.search(index="logs-network-default", body=query)
    except Exception as e:
        return json.dumps({"error": f"ES 查询失败: {str(e)}"}, ensure_ascii=False)

    hits = resp.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    results = []
    for hit in hits.get("hits", []):
        src = hit["_source"]
        results.append({
            "timestamp": src.get("@timestamp", ""),
            "log": src.get("message", ""),
            "severity": src.get("log", {}).get("level", ""),
        })

    return json.dumps({
        "total_ospf_logs": total,
        "time_range": f"{start.strftime('%H:%M:%S')} ~ {now.strftime('%H:%M:%S')}",
        "logs": results,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_log_stats(minutes: int = 60) -> str:
    """获取最近 N 分钟内的日志统计摘要。

    参数:
      minutes: 时间范围，默认 60 分钟

    返回: 日志总数、按严重级别分布、按数据集分布等统计。
    """
    es = es_queries.get_es()
    now = datetime.now(timezone(timedelta(hours=8)))
    start = now - timedelta(minutes=minutes)

    query = {
        "size": 0,
        "query": {
            "range": {"@timestamp": {"gte": _format_time(start), "lte": _format_time(now)}}
        },
        "aggs": {
            "log_level_count": {
                "terms": {"field": "log.level", "size": 20}
            },
            "dataset_count": {
                "terms": {"field": "event.dataset", "size": 20}
            },
            "service_count": {
                "terms": {"field": "service.name", "size": 20}
            },
            "logs_over_time": {
                "date_histogram": {
                    "field": "@timestamp",
                    "fixed_interval": "5m"
                }
            }
        }
    }

    try:
        resp = es.search(
            index="logs-network-default,logs-security-default,logs-system-default,logs-application-default",
            body=query
        )
    except Exception as e:
        return json.dumps({"error": f"ES 查询失败: {str(e)}"}, ensure_ascii=False)

    total = resp.get("hits", {}).get("total", {}).get("value", 0)
    aggs = resp.get("aggregations", {})

    level_dist = [
        {"level": b["key"], "count": b["doc_count"]}
        for b in aggs.get("log_level_count", {}).get("buckets", [])
    ]
    dataset_dist = [
        {"dataset": b["key"], "count": b["doc_count"]}
        for b in aggs.get("dataset_count", {}).get("buckets", [])
    ]
    service_dist = [
        {"service": b["key"], "count": b["doc_count"]}
        for b in aggs.get("service_count", {}).get("buckets", [])
    ]
    timeline = [
        {"time": b["key_as_string"], "count": b["doc_count"]}
        for b in aggs.get("logs_over_time", {}).get("buckets", [])
    ]

    return json.dumps({
        "total_logs": total,
        "time_range": f"{start.strftime('%Y-%m-%d %H:%M:%S')} ~ {now.strftime('%Y-%m-%d %H:%M:%S')}",
        "log_level_distribution": level_dist,
        "dataset_distribution": dataset_dist,
        "service_distribution": service_dist,
        "timeline_5min": timeline,
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("Starting LogAI ES MCP Server (streamable-http on :8765)...")
    mcp.run(transport="streamable-http")
