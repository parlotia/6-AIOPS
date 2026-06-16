#!/bin/bash
# ============================================================
# AIOps DAY7 - RagFlow 部署脚本
# 服务器: 阿里云 GPU (8.160.166.64)
# 功能: 通过 Docker Compose 部署 RagFlow RAG 引擎
# ============================================================

set -e

echo "========== RagFlow 部署开始 =========="

# ---- 1. 系统参数配置 ----
echo ""
echo ">>> [1/6] 配置系统参数 (vm.max_map_count)"
CURRENT_VAL=$(sysctl -n vm.max_map_count)
echo "    当前 vm.max_map_count = $CURRENT_VAL"

if [ "$CURRENT_VAL" -lt 262144 ]; then
    sysctl -w vm.max_map_count=262144
    # 持久化配置
    if ! grep -q "vm.max_map_count=262144" /etc/sysctl.conf; then
        echo "vm.max_map_count=262144" >> /etc/sysctl.conf
    fi
    echo "    已设置 vm.max_map_count=262144"
else
    echo "    vm.max_map_count 已满足要求,无需修改"
fi

# ---- 2. 检查 Docker 环境 ----
echo ""
echo ">>> [2/6] 检查 Docker 环境"
if ! command -v docker &> /dev/null; then
    echo "    Docker 未安装,正在安装..."
    curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
    systemctl start docker
    systemctl enable docker
    echo "    Docker 安装完成"
else
    DOCKER_VER=$(docker --version | grep -oP '\d+\.\d+\.\d+')
    echo "    Docker 已安装: v${DOCKER_VER}"
fi

if ! docker compose version &> /dev/null; then
    echo "    [错误] Docker Compose V2 未安装"
    exit 1
fi
echo "    Docker Compose: $(docker compose version)"

# ---- 3. 克隆 RagFlow ----
echo ""
echo ">>> [3/6] 克隆 RagFlow 仓库"
RAGFLOW_DIR="/opt/ragflow"

if [ -d "$RAGFLOW_DIR" ]; then
    echo "    RagFlow 目录已存在,更新仓库..."
    cd "$RAGFLOW_DIR"
    git fetch --all
    git checkout -f v0.26.0
else
    echo "    克隆 RagFlow..."
    git clone https://github.com/infiniflow/ragflow.git "$RAGFLOW_DIR"
    cd "$RAGFLOW_DIR"
    git checkout -f v0.26.0
fi
echo "    RagFlow 版本: v0.26.0"

# ---- 4. 配置环境变量 ----
echo ""
echo ">>> [4/6] 配置环境变量"
cd "$RAGFLOW_DIR/docker"

# 配置 .env 文件（使用国内镜像加速）
cat > .env << 'ENVEOF'
# ==================== Elasticsearch ====================
STACK_VERSION=8.11.3
ES_PORT=1200
ELASTIC_PASSWORD=infini_rag_flow

# ==================== Kibana ====================
KIBANA_PORT=6601
KIBANA_USER=rag_flow
KIBANA_PASSWORD=infini_rag_flow

# ==================== Resource ====================
MEM_LIMIT=8073741824

# ==================== MySQL ====================
MYSQL_PASSWORD=infini_rag_flow
MYSQL_PORT=3306
EXPOSE_MYSQL_PORT=5455

# ==================== MinIO ====================
MINIO_CONSOLE_PORT=9001
MINIO_PORT=9000
MINIO_USER=rag_flow
MINIO_PASSWORD=infini_rag_flow

# ==================== Redis ====================
REDIS_PORT=6379
REDIS_PASSWORD=infini_rag_flow

# ==================== RAGFlow ====================
SVR_HTTP_PORT=9380
RAGFLOW_IMAGE=infiniflow/ragflow:v0.26.0

# ==================== Timezone ====================
TZ=Asia/Shanghai

# ==================== HuggingFace 镜像 ====================
HF_ENDPOINT=https://hf-mirror.com
ENVEOF

echo "    .env 配置完成"

# ---- 5. 尝试使用国内镜像（如果默认拉取失败） ----
echo ""
echo ">>> [5/6] 拉取 Docker 镜像"
echo "    如果默认镜像拉取失败,将使用国内镜像..."

# 先尝试拉取
if ! docker compose -f docker-compose.yml pull; then
    echo "    默认镜像拉取失败,切换到华为云镜像..."
    sed -i 's|RAGFLOW_IMAGE=infiniflow/ragflow:v0.26.0|RAGFLOW_IMAGE=swr.cn-north-4.myhuaweicloud.com/infiniflow/ragflow:v0.26.0|' .env
    docker compose -f docker-compose.yml pull
fi
echo "    镜像拉取完成"

# ---- 6. 启动服务 ----
echo ""
echo ">>> [6/6] 启动 RagFlow 服务"
docker compose -f docker-compose.yml up -d
echo "    服务已启动,等待初始化..."

# 等待 RagFlow 就绪
echo ""
echo "========== 等待 RagFlow 初始化 =========="
MAX_WAIT=300
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:9380/api/v1/system/healthz > /dev/null 2>&1; then
        echo ""
        echo "========== RagFlow 启动成功! =========="
        echo ""
        echo "  Web UI:     http://$(hostname -I | awk '{print $1}')"
        echo "  API Server: http://$(hostname -I | awk '{print $1}'):9380"
        echo ""
        echo "  首次使用请:"
        echo "    1. 浏览器打开 Web UI,注册账号"
        echo "    2. 点击右上角头像 → Model providers → 配置 LLM"
        echo "    3. 获取 API Key: 点击右上角头像 → API Key → 生成"
        echo ""
        exit 0
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    echo -ne "\r    等待中... ${WAITED}/${MAX_WAIT}s"
done

echo ""
echo "[警告] RagFlow 初始化超时,请手动检查:"
echo "  docker compose -f docker-compose.yml logs -f ragflow"
echo "  curl http://localhost:9380/api/v1/system/healthz"
