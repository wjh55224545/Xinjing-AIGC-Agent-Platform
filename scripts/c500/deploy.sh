#!/bin/bash
# 一键部署到曦云C500云GPU实例
# ===============================
# 用法:
#   bash scripts/c500/deploy.sh <c500-host> <user>
#
# 例如:
#   bash scripts/c500/deploy.sh 192.168.1.100 root

set -e

C500_HOST="${1:?请提供C500实例IP}"
C500_USER="${2:-root}"
PROJECT_DIR="$(cd "$(dirname "$0")/../../" && pwd)"
PROJECT_NAME="Xinjing-AIGC-Agent-Platform"
REMOTE_DIR="/home/${C500_USER}/${PROJECT_NAME}"

echo "=== 心镜AIGC · 曦云C500 一键部署 ==="
echo "本地项目: ${PROJECT_DIR}"
echo "远程主机: ${C500_USER}@${C500_HOST}"
echo "远程目录: ${REMOTE_DIR}"
echo ""

# 步骤1: 上传代码
echo "[1/3] 上传代码..."
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' \
      --exclude '.git' --exclude 'node_modules' --exclude 'data/*.db' \
      "${PROJECT_DIR}/" "${C500_USER}@${C500_HOST}:${REMOTE_DIR}/"

# 步骤2: 安装依赖
echo "[2/3] 安装依赖..."
ssh "${C500_USER}@${C500_HOST}" << 'REMOTE_SCRIPT'
cd ~/Xinjing-AIGC-Agent-Platform

# 创建虚拟环境（如不存在）
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
pip install ultralytics opencv-python-headless scipy

# 验证GPU
echo "--- GPU 验证 ---"
python -c "
import torch
print(f'PyTorch版本: {torch.__version__}')
print(f'CUDA可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU型号: {torch.cuda.get_device_name(0)}')
    print(f'显存: {torch.cuda.get_device_properties(0).total_memory / 1024**2:.0f} MB')
"
REMOTE_SCRIPT

# 步骤3: 运行基准测试
echo "[3/3] 运行基准测试..."
ssh "${C500_USER}@${C500_HOST}" << 'REMOTE_SCRIPT'
cd ~/Xinjing-AIGC-Agent-Platform
source .venv/bin/activate
python scripts/c500/benchmark.py --output data/benchmark_c500.json
python scripts/c500/benchmark_report.py data/benchmark_c500.json --output data/benchmark_report.md
REMOTE_SCRIPT

# 拉回基准报告
echo ""
echo "=== 拉回基准报告 ==="
scp "${C500_USER}@${C500_HOST}:${REMOTE_DIR}/data/benchmark_c500.json" \
    "${PROJECT_DIR}/data/benchmark_c500.json"
scp "${C500_USER}@${C500_HOST}:${REMOTE_DIR}/data/benchmark_report.md" \
    "${PROJECT_DIR}/data/benchmark_report.md"

echo ""
echo "=== 部署完成 ==="
echo "基准数据: data/benchmark_c500.json"
echo "基准报告: data/benchmark_report.md"
cat "${PROJECT_DIR}/data/benchmark_report.md" 2>/dev/null || echo "(报告内容见上方文件)"
