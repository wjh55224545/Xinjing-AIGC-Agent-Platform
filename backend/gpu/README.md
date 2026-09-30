# backend.gpu — 通用 GPU 计算后端组件

一个与业务解耦的国产算力适配组件，供任何 NumPy/SciPy/Torch 计算任务复用。

## 能力

- **自动探测**：MUSA（沐曦曦云）/ CUDA（NVIDIA）/ CPU（numpy）三级探测，缓存结果
- **统一数组接口**：`get_array_module()` 返回 torch 或 numpy，上层代码透明切换
- **数据传输**：`to_gpu` / `to_cpu` / `ensure_float32` 自动处理设备迁移
- **兼容运算**：`histogram` / `rfft` / `rfftfreq` 在 torch 与 numpy 间保持一致行为
- **性能基准**：`benchmark_context` 记录每次运算 CPU vs GPU 耗时，支持导出

## 用法

```python
from backend.gpu import detect_gpu, get_array_module, to_gpu, to_cpu, histogram

info = detect_gpu()               # {"available": ..., "vendor": "MetaX (沐曦)", ...}
xp = get_array_module()           # torch 或 numpy，按环境自动选择
gpu_data = to_gpu(frames)         # 转移到 GPU（不可用则原样返回）
hist, edges = histogram(gpu_data, bins=100)
```

环境变量：

- `VIBRAIMAGE_GPU_BACKEND=auto|torch|numpy` — 强制后端
- `VIBRAIMAGE_GPU_BENCHMARK=true` — 开启运算耗时记录

## 设计说明

本组件从 `backend/vibraimage/gpu_backend.py` 迁移而来（v2.9），旧路径保留为兼容转发层。
新代码请直接引用 `backend.gpu`。
