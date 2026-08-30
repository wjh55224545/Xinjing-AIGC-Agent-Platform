"""
测试 pipeline 模块 — 端到端集成测试。

使用合成视频（无头移动的静态圆）验证全流水线。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import tempfile
from pathlib import Path


def generate_synthetic_video(path: str, n_frames: int = 200, fps: int = 30):
    """
    生成合成测试视频: 带微小正弦振动的静态圆 (模拟头部微振动)。
    """
    H, W = 480, 640
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(path, fourcc, fps, (W, H))

    for i in range(n_frames):
        frame = np.ones((H, W, 3), dtype=np.uint8) * 128  # 灰背景

        # 正弦微振动 (0.1-10Hz范围内)
        dx = 2.0 * np.sin(2 * np.pi * 3.0 * i / fps)      # 3Hz水平振动
        dy = 1.0 * np.sin(2 * np.pi * 5.0 * i / fps)      # 5Hz垂直振动

        center = (int(W // 2 + dx), int(H // 2 + dy))
        cv2.circle(frame, center, 100, (200, 200, 200), -1)  # 灰色圆(人脸)
        cv2.circle(frame, center, 100, (180, 180, 180), 2)   # 轮廓

        writer.write(frame)

    writer.release()


def test_pipeline_with_synthetic():
    """用合成视频测试全流水线。"""
    from vibraimage.pipeline.engine import VibraImageEngine

    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        video_path = tmp.name

    try:
        # 生成合成视频
        print("生成合成测试视频...")
        generate_synthetic_video(video_path, n_frames=150)

        # 运行引擎 (不使用YOLO人脸检测，直接处理原始帧)
        print("运行VibraImage引擎...")
        engine = VibraImageEngine(
            window_frames=60,
            window_stride=30,
            freq_method='zerocross',
        )

        # 加载视频帧
        cap = cv2.VideoCapture(video_path)
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_resized = cv2.resize(gray, (224, 224))
            frames.append(gray_resized.astype(np.float32))
        cap.release()

        frames_array = np.array(frames)
        print(f"  帧数: {len(frames_array)}, 尺寸: {frames_array.shape}")

        # 直接处理帧 (跳过人脸检测)
        result = engine.process_frames(frames_array)

        # 验证
        emotions = result.to_dict()['emotions']
        print(f"\n结果:")
        print(f"  窗口数: {result.n_windows}")
        print(f"  E1 (Aggression): {emotions['aggression']:.2f}%")
        print(f"  E2 (Stress): {emotions['stress']:.2f}%")
        print(f"  E3 (Tension): {emotions['tension']:.2f}%")
        print(f"  K值: {result.K_value:.2f}")

        # 基本断言
        assert result.n_windows > 0, "应该至少生成1个窗口"
        assert 0 <= emotions['aggression'] <= 100
        assert 0 <= emotions['stress'] <= 100
        assert 0 <= emotions['tension'] <= 100

        print("\n[PASS] test_pipeline_with_synthetic passed")

    finally:
        os.unlink(video_path)


if __name__ == '__main__':
    test_pipeline_with_synthetic()
    print("\n所有 pipeline 测试通过！")
