# 曦云C500 云GPU 部署指南

## 前提条件

- 曦云C500云GPU实例 SSH 登录凭证（IP、用户名、密码/密钥）
- 实例已预装沐曦MACA SDK + PyTorch MUSA版
- 本地已安装 `rsync` 和 `scp`

## 快速开始

```bash
# 一键部署 + 基准测试
bash scripts/c500/deploy.sh <C500实例IP> <用户名>

# 例如:
bash scripts/c500/deploy.sh 192.168.1.100 root
```

## 手动步骤

### 1. 上传代码

```bash
rsync -avz \
  --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  ./ user@<ip>:/home/user/Xinjing-AIGC-Agent-Platform/
```

### 2. SSH登录并安装依赖

```bash
ssh user@<ip>
cd Xinjing-AIGC-Agent-Platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install ultralytics opencv-python-headless scipy

# 验证GPU
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

### 3. 运行基准测试

```bash
python scripts/c500/benchmark.py --output data/benchmark_c500.json
python scripts/c500/benchmark_report.py data/benchmark_c500.json --output data/benchmark_report.md
```

### 4. 拉回结果

```bash
scp user@<ip>:/home/user/Xinjing-AIGC-Agent-Platform/data/benchmark_* ./data/
```

## 启动后端服务（可选）

```bash
# 在C500实例上启动后端
ssh user@<ip>
cd Xinjing-AIGC-Agent-Platform
source .venv/bin/activate
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 本地访问
curl http://<ip>:8000/api/gpu/status
curl http://<ip>:8000/api/vibraimage/analyze -F "file=@test.mp4"
```

## 常见问题

**Q: `torch.cuda.is_available()` 返回 False？**
A: 确认沐曦PyTorch MUSA版已正确安装：`pip list | grep torch`

**Q: YOLOv8 模型文件找不到？**
A: 首次运行时 ultralytics 会自动下载，或手动放置 `yolov8n.pt` 到 `data/` 目录。
