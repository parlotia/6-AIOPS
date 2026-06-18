"""
DAY9 作业 - 第二部分: 查询 Qdrant 向量数据库找到问题相关的知识库

功能:
  1. 连接 Qdrant (TLS + API Key)
  2. 通过 Ollama API 获取查询文本的嵌入向量
  3. 在向量数据库中搜索最相关的文档片段
  4. 格式化输出搜索结果 (文件名、相似度、内容)
"""

import warnings
warnings.filterwarnings("ignore", module="qdrant_client")

import requests
from qdrant_client import QdrantClient

# ====== 配置 ======
QDRANT_HOST = "localhost"
QDRANT_GRPC_PORT = 6334
QDRANT_API_KEY = "Cisc0123"
COLLECTION_NAME = "qytang_qdrant_kb"
OLLAMA_BASE_URL = "http://8.160.166.64:11434"
EMBED_MODEL = "nomic-embed-text"


def query_knowledge_base(question: str):
    """查询向量数据库, 返回与问题最相关的知识库文档片段"""
    try:
        # 1. 连接 Qdrant
        client = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_GRPC_PORT,
            api_key=QDRANT_API_KEY,
            prefer_grpc=True,
            https=True,
            grpc_options={"grpc.ssl_target_name_override": "localhost"}
        )

        # 2. 获取查询向量 (通过 Ollama API 获取嵌入)
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": question},
            timeout=30
        )
        embedding = response.json()["embedding"]

        # 3. 搜索向量数据库
        search_results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=embedding,
            limit=5,
            with_payload=True
        )

        # 4. 提取文档并格式化输出
        docs = []
        for point in search_results.points:
            # 获取文本内容 (兼容多种 payload 字段名)
            text = (point.payload.get("page_content") or
                    point.payload.get("text") or
                    point.payload.get("content"))

            # 获取文件名
            metadata = point.payload.get("metadata", {})
            file_name = metadata.get("source", "").split("/")[-1]

            doc_text = "--------\n"
            if file_name:
                doc_text += f"文件: {file_name}\n"
            if hasattr(point, 'score'):
                doc_text += f"相似度: {point.score:.4f}\n"
            if text:
                doc_text += f"内容: {text[:200]}...\n"
            docs.append(doc_text)

        if docs:
            return "\n\n".join(docs)
        else:
            return "未找到相关信息"

    except Exception as e:
        return f"查询失败: {str(e)}"


if __name__ == "__main__":
    # 测试查询
    test_questions = [
        "乾颐堂",
        "ZTP开局",
        "OSPF路由协议",
        "SNMP网络监控",
    ]
    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"查询: {q}")
        print(f"{'='*60}")
        print(query_knowledge_base(q))
