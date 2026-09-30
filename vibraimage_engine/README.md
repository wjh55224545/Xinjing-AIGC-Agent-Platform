# VibraImage Engine

> 从零实现的 VibraImage 情绪识别引擎（clean-room implementation），作为可复用的开源组件独立安装。

本组件依据 Viktor Minkin《Vibraimage, Cybernetics and Emotions》(2020) 中公开的公式体系，
实现了"逐像素帧差分 → 频率分析 → 情绪参数计算"的完整流水线，不依赖任何闭源 SDK。

## 特性

- **纯算法实现**：帧差分 / 直方图统计 / 空间分析 / 频谱分析，全部从零实现
- **情绪模型**：9 种主情绪 + 衍生情绪 + 心理生理指标
- **GPU 自适应**：自动探测 MUSA (沐曦) / CUDA / CPU，透明切换计算后端
- **人脸检测**：默认 Haar Cascade（Apache-2.0），可选 YOLOv8（AGPL，需自行获取权重）
- **零依赖可选**：核心仅需 opencv / numpy / scipy

## 安装

```bash
pip install -e ./vibraimage_engine          # 本地安装
pip install vibraimage-engine               # PyPI（发布后）
pip install "vibraimage-engine[gpu]"        # 启用 YOLO 可选依赖
```

## 快速开始

```python
from vibraimage.pipeline.engine import VibraImageEngine

engine = VibraImageEngine()
results = engine.process_video("path/to/video.mp4")
```

## 测试

```bash
cd vibraimage_engine && pytest tests -v
```

## License

Apache-2.0。YOLOv8 权重（yolov8n.pt）受 AGPL-3.0 约束，不随本仓库分发；
如需使用 YOLO 检测器，请自行从 ultralytics 获取权重并遵守其许可证。
