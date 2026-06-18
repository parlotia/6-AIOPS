"""
DAY9 作业 - 第一部分: 将 Markdown 知识库文档切分并写入 Qdrant 向量数据库

功能:
  1. 使用 DirectoryLoader 加载 homework 目录下的 Markdown 文档
  2. 使用 RecursiveCharacterTextSplitter 切分为文本块
  3. 通过 Ollama nomic-embed-text 生成嵌入向量
  4. 写入本地 Qdrant 向量数据库 (TLS + API Key 认证)
"""

import os
import time
import warnings
warnings.filterwarnings("ignore", module="qdrant_client")

from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance

# LangChain imports
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore

# ====== Qdrant 配置 ======
QDRANT_HOST = "localhost"
QDRANT_GRPC_PORT = 6334
QDRANT_API_KEY = "Cisc0123"
QDRANT_COLLECTION_NAME = "qytang_qdrant_kb"
KNOWLEDGE_BASE_DIR = "/netdevops/homework"  # 知识库目录 (包含大量 .md 文件)

# ====== Ollama 嵌入模型配置 ======
OLLAMA_EMBED_MODEL_NAME = "nomic-embed-text"
OLLAMA_BASE_URL = "http://8.160.166.64:11434"  # 云服务器 Ollama
NOMIC_EMBED_DIMENSION = 768


def setup_qdrant_collection(client, collection_name, vector_size):
    """确保 Qdrant 集合存在并配置正确"""
    if client.collection_exists(collection_name):
        print(f"集合 '{collection_name}' 已存在，删除重建...")
        client.delete_collection(collection_name)
        time.sleep(1)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )
    print(f"集合 '{collection_name}' 已创建/重置，向量维度：{vector_size}")


def load_and_process_documents():
    """使用 DirectoryLoader 加载 Markdown 文档"""
    loader = DirectoryLoader(
        KNOWLEDGE_BASE_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf-8'}
    )
    documents = loader.load()
    print(f"成功加载 {len(documents)} 个 Markdown 文档")
    return documents


def split_documents(documents):
    """使用 RecursiveCharacterTextSplitter 切分文档"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=384,
        chunk_overlap=20,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    split_docs = text_splitter.split_documents(documents)
    print(f"文档分割完成，共生成 {len(split_docs)} 个文本块")
    return split_docs


def write_to_qdrant_with_langchain():
    """主函数: 设置集合 -> 加载文档 -> 切分 -> 写入 Qdrant -> 验证"""
    start_time = time.time()

    # 1. 初始化 Ollama 嵌入模型
    embeddings = OllamaEmbeddings(
        model=OLLAMA_EMBED_MODEL_NAME,
        base_url=OLLAMA_BASE_URL
    )
    print("嵌入模型初始化成功")

    # 2. 连接 Qdrant (TLS 加密, gRPC 优先)
    client = QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_GRPC_PORT,
        api_key=QDRANT_API_KEY,
        prefer_grpc=True,
        https=True,
        grpc_options={"grpc.ssl_target_name_override": "localhost"}
    )
    client.get_collections()
    print("成功连接到 Qdrant")

    # 3. 设置集合
    setup_qdrant_collection(client, QDRANT_COLLECTION_NAME, NOMIC_EMBED_DIMENSION)

    # 4. 加载和处理文档
    documents = load_and_process_documents()
    split_docs = split_documents(documents)

    # 5. 使用 LangChain 的 Qdrant 向量存储
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=QDRANT_COLLECTION_NAME,
        embedding=embeddings
    )
    texts = [doc.page_content for doc in split_docs]
    metadatas = [doc.metadata for doc in split_docs]
    vector_store.add_texts(texts=texts, metadatas=metadatas)
    print(f"成功使用 LangChain 添加 {len(texts)} 个文档到向量存储")

    # 6. 验证结果
    count_result = client.count(collection_name=QDRANT_COLLECTION_NAME)
    actual_count = count_result.count
    if actual_count == len(split_docs):
        print(f"验证成功: 期望 {len(split_docs)} 个向量, 实际 {actual_count} 个")
    else:
        print(f"验证异常: 期望上传 {len(split_docs)} 个向量，但集合中有 {actual_count} 个")

    end_time = time.time()
    print(f"总耗时：{end_time - start_time:.1f} 秒")
    print("=== Qdrant 数据写入脚本执行完毕 ===")


if __name__ == "__main__":
    write_to_qdrant_with_langchain()
