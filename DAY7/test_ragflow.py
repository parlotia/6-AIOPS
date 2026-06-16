#!/usr/bin/env python3
# -*- coding=utf-8 -*-
"""
AIOps DAY7 作业 - RagFlow RAG 知识库搭建与测试
使用 RagFlow HTTP API (requests) 完成:
  1. 创建知识库 (Dataset)
  2. 上传个人知识文档
  3. 解析文档 (Parse)
  4. 创建聊天助手 (Chat Assistant)
  5. 基于知识库回答问题
"""

import time
import sys
import os
import re
import requests

# ==================== 配置区域 ====================
# RagFlow 服务器地址 (修改为你的服务器 IP)
RAGFLOW_SERVER = "8.160.166.64"
RAGFLOW_PORT = 9380
BASE_URL = f"http://{RAGFLOW_SERVER}:{RAGFLOW_PORT}"

# RagFlow API Key (在 Web UI 中获取: 头像 → API Key → 生成)
# 首次运行前请先在 Web UI 注册账号并配置 LLM, 然后生成 API Key
API_KEY = "ragflow-IXI5gno-xMsCk3Yt30ZhQKl5mSdPIX031U67wrSa-zg"

# 知识库文档路径
KNOWLEDGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.md")

# 测试问题列表
TEST_QUESTIONS = [
    "朱福松是谁？",
    "朱福松的工作经历是什么？",
    "朱福松有什么兴趣爱好？",
    "朱福松的技术栈有哪些？",
    "朱福松目前在学什么课程？",
    "朱福松为什么学习AIOps？",
    "朱福松的职业规划是什么？",
]


def headers():
    """构造请求头"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }


def api_post(path, json_data=None, files=None):
    """POST 请求封装"""
    url = f"{BASE_URL}{path}"
    if files:
        h = {"Authorization": f"Bearer {API_KEY}"}
        resp = requests.post(url, headers=h, files=files)
    else:
        resp = requests.post(url, headers=headers(), json=json_data)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"API 错误: {data.get('message', data)}")
    return data.get("data")


def api_get(path, params=None):
    """GET 请求封装"""
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, headers=headers(), params=params)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"API 错误: {data.get('message', data)}")
    return data.get("data")


def healthcheck():
    """检查 RagFlow 服务是否健康"""
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/system/healthz", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def wait_for_parsing(dataset_id, doc_ids, timeout=300):
    """等待文档解析完成"""
    print("  等待文档解析...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            docs_data = api_get(f"/api/v1/datasets/{dataset_id}/documents")
            docs = docs_data if isinstance(docs_data, list) else docs_data.get("docs", [])
            all_done = True
            for doc in docs:
                doc_id = doc.get("id", "")
                if doc_id in doc_ids:
                    run_status = doc.get("run", "")
                    chunk_num = doc.get("chunk_count", doc.get("chunk_num", 0))
                    name = doc.get("name", "")
                    print(f"    文档: {name} | 状态: {run_status} | chunks: {chunk_num}")
                    if run_status not in ["DONE", "done", "success"]:
                        all_done = False
                    elif chunk_num == 0:
                        all_done = False
            if all_done:
                print("  ✓ 文档解析完成!")
                return True
        except Exception as e:
            print(f"    检查状态出错: {e}")
        time.sleep(5)
    print("  ⚠ 解析超时,继续执行...")
    return False


def main():
    print("=" * 60)
    print("  AIOps DAY7 - RagFlow RAG 知识库测试")
    print("=" * 60)

    # ---- Step 1: 检查 RagFlow 服务 ----
    print(f"\n[Step 1] 检查 RagFlow 服务器: {BASE_URL}")
    if healthcheck():
        print("  ✓ RagFlow 服务正常运行!")
    else:
        print("  ✗ RagFlow 服务不可达!")
        print("  请检查:")
        print(f"    1. RagFlow 是否已启动: curl {BASE_URL}/api/v1/system/healthz")
        print("    2. 防火墙是否放行 9380 端口")
        sys.exit(1)

    # ---- Step 2: 创建知识库 ----
    print("\n[Step 2] 创建知识库 (Dataset)")
    dataset_name = "朱福松个人知识库"
    try:
        # 先检查是否已存在
        existing = api_get("/api/v1/datasets")
        datasets = existing if isinstance(existing, list) else existing.get("datasets", [])
        matched = [d for d in datasets if d.get("name") == dataset_name]
        if matched:
            dataset_id = matched[0]["id"]
            print(f"  ✓ 知识库已存在: {dataset_id}")
        else:
            result = api_post("/api/v1/datasets", {
                "name": dataset_name,
                "description": "朱福松的个人知识库,包含基本信息、工作经历、技术栈、兴趣爱好等",
                "chunk_method": "naive",
            })
            dataset_id = result["id"]
            print(f"  ✓ 知识库创建成功: {dataset_id}")
    except Exception as e:
        print(f"  ✗ 创建知识库失败: {e}")
        sys.exit(1)

    # ---- Step 3: 上传文档 ----
    print(f"\n[Step 3] 上传知识文档: {KNOWLEDGE_FILE}")
    if not os.path.exists(KNOWLEDGE_FILE):
        print(f"  ✗ 文件不存在: {KNOWLEDGE_FILE}")
        sys.exit(1)

    try:
        with open(KNOWLEDGE_FILE, "rb") as f:
            files = {"file": ("朱福松_个人知识库.md", f, "text/markdown")}
            result = api_post(f"/api/v1/datasets/{dataset_id}/documents", files=files)
        print("  ✓ 文档上传成功!")

        # 获取文档 ID
        doc_ids = []
        if isinstance(result, list):
            doc_ids = [d["id"] for d in result]
        elif isinstance(result, dict):
            docs = result.get("docs", result.get("data", []))
            doc_ids = [d["id"] for d in docs]
        print(f"  文档 ID: {doc_ids}")
    except Exception as e:
        print(f"  ✗ 上传失败: {e}")
        sys.exit(1)

    # ---- Step 4: 解析文档 ----
    print("\n[Step 4] 解析文档 (Parse)")
    try:
        if doc_ids:
            api_post(f"/api/v1/datasets/{dataset_id}/chunks", {
                "document_ids": doc_ids,
            })
            print(f"  ✓ 开始解析 {len(doc_ids)} 个文档...")
            # 等待解析完成
            wait_for_parsing(dataset_id, doc_ids)
        else:
            # 查找已上传的文档
            docs_data = api_get(f"/api/v1/datasets/{dataset_id}/documents")
            docs = docs_data if isinstance(docs_data, list) else docs_data.get("docs", [])
            doc_ids = [d["id"] for d in docs]
            if doc_ids:
                api_post(f"/api/v1/datasets/{dataset_id}/chunks", {
                    "document_ids": doc_ids,
                })
                print(f"  ✓ 开始解析 {len(doc_ids)} 个文档...")
                wait_for_parsing(dataset_id, doc_ids)
            else:
                print("  ⚠ 未找到已上传的文档")
    except Exception as e:
        print(f"  ✗ 解析失败: {e}")

    # ---- Step 5: 创建聊天助手 ----
    print("\n[Step 5] 创建聊天助手 (Chat Assistant)")
    chat_name = "朱福松助手"
    chat_id = None
    try:
        # 先检查是否已存在
        existing_chats = api_get("/api/v1/chats")
        chats = existing_chats if isinstance(existing_chats, list) else existing_chats.get("chats", [])
        matched_chats = [c for c in chats if c.get("name") == chat_name]
        if matched_chats:
            chat_id = matched_chats[0]["id"]
            print(f"  ✓ 聊天助手已存在: {chat_id}")
        else:
            result = api_post("/api/v1/chats", {
                "name": chat_name,
                "dataset_ids": [dataset_id],
                "prompt_config": {
                    "system": "你是朱福松的个人AI助手。请基于知识库 {knowledge} 中的内容回答用户的问题。如果知识库中没有相关信息,请如实告知。",
                    "prologue": "你好!我是朱福松的AI助手,很高兴为你解答关于朱福松的问题。",
                    "empty_response": "抱歉,在知识库中没有找到相关信息。",
                    "quote": True,
                },
            })
            chat_id = result["id"]
            print(f"  ✓ 聊天助手创建成功: {chat_id}")
    except Exception as e:
        print(f"  ✗ 创建聊天助手失败: {e}")
        sys.exit(1)

    # ---- Step 6: 创建会话 ----
    print("\n[Step 6] 创建会话 (Session)")
    session_id = None
    try:
        result = api_post(f"/api/v1/chats/{chat_id}/sessions", {
            "name": "DAY7测试会话",
        })
        session_id = result["id"]
        print(f"  ✓ 会话创建成功: {session_id}")
    except Exception as e:
        print(f"  ✗ 创建会话失败: {e}")
        sys.exit(1)

    # ---- Step 7: 测试问答 ----
    print("\n[Step 7] 基于知识库的问答测试")
    print("-" * 60)

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\nQ{i}: {question}")
        try:
            resp = requests.post(
                f"{BASE_URL}/api/v1/chat/completions",
                headers=headers(),
                json={
                    "chat_id": chat_id,
                    "session_id": session_id,
                    "stream": False,
                    "messages": [
                        {"role": "user", "content": question}
                    ],
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == 0:
                answer_data = data.get("data", {})
                if isinstance(answer_data, dict):
                    # RagFlow v0.26 格式: data.answer
                    answer_text = answer_data.get("answer", "")
                    if not answer_text:
                        # 兼容 choices 格式
                        choices = answer_data.get("choices", [])
                        if choices:
                            answer_text = choices[0].get("message", {}).get("content", "")
                    answer_text = re.sub(r'<[^>]+>', '', answer_text)
                    print(f"A{i}: {answer_text.strip()}")
                else:
                    print(f"A{i}: {str(data.get('data', ''))[:500]}")
            else:
                print(f"A{i}: [错误] {data.get('message', data)}")
        except Exception as e:
            print(f"A{i}: [请求失败] {e}")
        time.sleep(1)

    print("\n" + "=" * 60)
    print("  RagFlow RAG 知识库测试完成!")
    print(f"  Web UI: http://{RAGFLOW_SERVER}")
    print("=" * 60)


if __name__ == "__main__":
    main()
