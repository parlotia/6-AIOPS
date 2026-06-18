"""
DAY9 作业 - 第三部分: Langchain Agent + Qdrant RAG 工具

功能:
  1. 将 query_knowledge_base 封装为 Langchain Tool
  2. 使用 langgraph create_react_agent 创建 Agent
  3. Agent 使用 ChatOllama (qwen3:4b) 作为 LLM
  4. 测试课程相关问答, 验证 RAG 能力 + 记忆能力
"""

import warnings
warnings.filterwarnings("ignore", module="qdrant_client")

import requests
from qdrant_client import QdrantClient

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

# ====== 配置 ======
QDRANT_HOST = "localhost"
QDRANT_GRPC_PORT = 6334
QDRANT_API_KEY = "Cisc0123"
COLLECTION_NAME = "qytang_qdrant_kb"
OLLAMA_BASE_URL = "http://8.160.166.64:11434"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen3:4b"


# ====== RAG 工具 ======
@tool
def query_knowledge_base(question: str) -> str:
    """查询知识库向量数据库。当需要回答关于课程内容、网络技术、乾颐堂等问题时使用此工具。
    输入一个问题, 返回知识库中最相关的文档片段。"""
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

        # 2. 获取查询向量
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

        # 4. 提取文档
        docs = []
        for point in search_results.points:
            text = (point.payload.get("page_content") or
                    point.payload.get("text") or
                    point.payload.get("content"))
            metadata = point.payload.get("metadata", {})
            file_name = metadata.get("source", "").split("/")[-1]

            doc_text = "--------\n"
            if file_name:
                doc_text += f"文件: {file_name}\n"
            if hasattr(point, 'score'):
                doc_text += f"相似度: {point.score:.4f}\n"
            if text:
                doc_text += f"内容: {text}\n"
            docs.append(doc_text)

        if docs:
            return "\n\n".join(docs)
        else:
            return "未找到相关信息"

    except Exception as e:
        return f"查询失败: {str(e)}"


# ====== 创建 Agent ======
all_tools = [query_knowledge_base]

agent = create_react_agent(
    model=ChatOllama(
        model=CHAT_MODEL,
        temperature=0,
        base_url=OLLAMA_BASE_URL,
    ),
    tools=all_tools,
    checkpointer=InMemorySaver(),
    prompt="你是一个知识库助手。回答问题时请优先使用 RAG 工具查询知识库, 不要仅依赖自身知识。如果知识库中没有相关信息, 再用自身知识回答。使用中文回答。"
)


def main():
    """运行问答测试"""
    questions = [
        "数据库是什么？",
        "NetDevOps中Python基础学习内容是什么？",
        "ZTP开局是怎么做的？",
        "SNMP监控是如何实现的？",
        "天空为什么是蓝色的？",
    ]

    # 记忆测试
    memory_questions = [
        "记忆测试: 请记住我的名字叫秦柯",
        "我叫什么名字？",
    ]

    config = {"configurable": {"thread_id": "session_1"}}

    print("=" * 60)
    print("DAY9 作业 - Langchain Agent + Qdrant RAG 问答测试")
    print("=" * 60)

    # 通用问题测试
    for question in questions:
        print(f"\n{'='*60}")
        print(f"问题: {question}")
        print(f"{'='*60}")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config
        )
        answer = result["messages"][-1].content
        # 清理 qwen3 thinking 推理过程 (兼容有/无 <think> 标签)
        import re
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
        answer = re.sub(r'.*?</think>', '', answer, flags=re.DOTALL)
        answer = answer.strip()
        print(f"✅ 回答:\n{answer}")

    # 记忆测试
    print(f"\n{'='*60}")
    print("记忆测试")
    print(f"{'='*60}")
    for question in memory_questions:
        print(f"\n问题: {question}")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config
        )
        answer = result["messages"][-1].content
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL)
        answer = re.sub(r'.*?</think>', '', answer, flags=re.DOTALL)
        answer = answer.strip()
        print(f"✅ 回答:\n{answer}")

    print(f"\n{'='*60}")
    print("=== DAY9 Agent RAG 问答测试完毕 ===")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
