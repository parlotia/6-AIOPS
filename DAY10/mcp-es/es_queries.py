"""Elasticsearch 查询封装，供 MCP 工具调用。"""

from __future__ import annotations

import os
from typing import Any

from elasticsearch import Elasticsearch


ES_URL = os.getenv("ES_URL", "http://day10-elasticsearch:9200")
ANOMALY_INDEX = "logs-logai-result-default"
DRAIN3_INDEX = "logs-drain3-template-default"
RAW_INDEX_PREFIX = "logs-"


def get_es() -> Elasticsearch:
    return Elasticsearch(ES_URL, request_timeout=60)


def get_pipeline_summary() -> dict[str, Any]:
    """各 logs-* 索引文档数量。"""
    es = get_es()
    indices = [
        "logs-application-default",
        "logs-network-default",
        "logs-security-default",
        "logs-system-default",
        DRAIN3_INDEX,
        "logs-drain3-window-default",
        ANOMALY_INDEX,
    ]
    counts: dict[str, int] = {}
    for index in indices:
        if es.indices.exists(index=index):
            counts[index] = int(es.count(index=index)["count"])
        else:
            counts[index] = 0
    raw_keys = [
        "logs-application-default",
        "logs-network-default",
        "logs-security-default",
        "logs-system-default",
    ]
    return {
        "indices": counts,
        "total_raw": sum(counts.get(k, 0) for k in raw_keys),
    }


def aggregate_anomaly_rules() -> dict[str, Any]:
    """按 anomaly_type / severity 聚合异常规则触发次数。"""
    es = get_es()
    if not es.indices.exists(index=ANOMALY_INDEX):
        return {"total": 0, "types": [], "severity": []}
    body = {
        "size": 0,
        "aggs": {
            "types": {"terms": {"field": "anomaly_type", "size": 10}},
            "severity": {"terms": {"field": "severity", "size": 10}},
        },
    }
    resp = es.search(index=ANOMALY_INDEX, body=body)
    total = resp["hits"]["total"]["value"]
    types = [
        {"key": b["key"], "count": b["doc_count"]}
        for b in resp["aggregations"]["types"]["buckets"]
    ]
    severity = [
        {"key": b["key"], "count": b["doc_count"]}
        for b in resp["aggregations"]["severity"]["buckets"]
    ]
    return {"total": total, "types": types, "severity": severity}


_ANOMALY_SOURCE_FIELDS = [
    "anomaly_score",
    "anomaly_type",
    "severity",
    "reason",
    "drain3.template_id",
    "drain3.template",
    "evidence",
    "host.name",
    "service.name",
    "event.dataset",
    "window_start",
    "window_end",
]


def _parse_anomaly_hit(hit: dict[str, Any]) -> dict[str, Any]:
    src = hit["_source"]
    return {
        "id": hit["_id"],
        "anomaly_score": src.get("anomaly_score"),
        "anomaly_type": src.get("anomaly_type"),
        "severity": src.get("severity"),
        "reason": src.get("reason"),
        "template_id": src.get("drain3", {}).get("template_id"),
        "template": src.get("drain3", {}).get("template"),
        "evidence": src.get("evidence", {}),
        "host": src.get("host", {}).get("name"),
        "service": src.get("service", {}).get("name"),
        "dataset": src.get("event", {}).get("dataset"),
        "window_start": src.get("window_start"),
        "window_end": src.get("window_end"),
    }


def list_top_anomalies(size: int = 5) -> list[dict[str, Any]]:
    """按 anomaly_score 倒序返回 Top 异常。"""
    return list_anomalies_by_severity(severity=None, size=size)


def list_anomalies_by_severity(
    severity: str | None = None,
    size: int = 100,
) -> list[dict[str, Any]]:
    """按严重度筛选异常；severity 为 None 时返回全部（按分数倒序）。"""
    es = get_es()
    if not es.indices.exists(index=ANOMALY_INDEX):
        return []
    query: dict[str, Any] = {"match_all": {}}
    if severity:
        query = {"term": {"severity": severity}}
    body = {
        "size": size,
        "query": query,
        "sort": [{"anomaly_score": "desc"}],
        "_source": _ANOMALY_SOURCE_FIELDS,
    }
    resp = es.search(index=ANOMALY_INDEX, body=body)
    return [_parse_anomaly_hit(hit) for hit in resp["hits"]["hits"]]


def get_anomaly_detail(event_id: str) -> dict[str, Any]:
    """按 ID 获取完整异常文档。"""
    es = get_es()
    doc = es.get(index=ANOMALY_INDEX, id=event_id)
    return {"id": doc["_id"], "source": doc["_source"]}


def build_evidence_pack(anomaly_event_id: str) -> dict[str, Any]:
    """生成 LLM RCA 证据包。"""
    es = get_es()
    anomaly = es.get(index=ANOMALY_INDEX, id=anomaly_event_id)["_source"]
    sample_doc_ids = anomaly.get("evidence", {}).get("sample_doc_ids", [])
    dataset = anomaly.get("event", {}).get("dataset", "network")

    template_samples: list[dict[str, Any]] = []
    for doc_id in sample_doc_ids[:10]:
        try:
            template_samples.append(
                es.get(index=DRAIN3_INDEX, id=doc_id)["_source"]
            )
        except Exception:
            continue

    raw_logs: list[dict[str, Any]] = []
    for sample in template_samples[:5]:
        message = sample.get("message") or sample.get("normalized_message")
        if message:
            raw_logs.append({"message": message, "dataset": dataset})

    return {
        "anomaly_event": anomaly,
        "template_info": anomaly.get("drain3", {}),
        "window_statistics": anomaly.get("evidence", {}),
        "template_samples": template_samples,
        "sample_messages": raw_logs,
        "related_hosts": [anomaly.get("host", {}).get("name")],
        "related_services": [anomaly.get("service", {}).get("name")],
    }
