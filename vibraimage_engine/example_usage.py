#!/usr/bin/env python
"""
VibraImage Engine — 使用示例。

演示完整的视频处理流程:
    加载视频 → 人脸检测 → 帧差分 → 频率分析 → 情绪参数输出

依赖:
    pip install opencv-python numpy scipy ultralytics
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vibraimage.pipeline.engine import VibraImageEngine
from vibraimage.utils.validation import print_emotion_report, validate_all


def example_offline_video(video_path: str = "test.mp4"):
    """离线视频分析示例。"""
    print(f"分析视频: {video_path}")

    engine = VibraImageEngine(
        window_frames=100,      # ~3.3秒 @ 30fps
        window_stride=50,       # 50%重叠
        freq_method='zerocross', # 过零率法 (快速)
    )

    result = engine.process_video(video_path)

    # 打印报告
    emotion_params = result.to_dict()['emotions']
    print_emotion_report(emotion_params)

    # 打印逐窗口趋势
    print(f"\n逐窗口趋势 ({result.n_windows}个窗口):")
    print(f"{'窗口':>6s} {'E1(A)':>8s} {'E2(S)':>8s} {'E3(T)':>8s} {'E4(Su)':>8s}")
    for w in result.window_results[:10]:
        print(
            f"{w.window_id:>6d} "
            f"{w.aggression:>8.2f} "
            f"{w.stress:>8.2f} "
            f"{w.tension:>8.2f} "
            f"{w.suspect:>8.2f}"
        )
    if result.n_windows > 10:
        print(f"  ... ({result.n_windows - 10} more)")

    # 验证
    issues = validate_all(emotion_params)
    if issues:
        print(f"\n参数验证问题:")
        for param, msgs in issues.items():
            print(f"  {param}: {', '.join(msgs)}")

    # 保存
    result.to_json("output_result.json")
    print(f"\n结果已保存到 output_result.json")

    return result


def example_camera_stream():
    """摄像头实时分析示例 (需要摄像头)。"""
    import cv2
    import numpy as np

    engine = VibraImageEngine(
        window_frames=60,   # 2秒 @ 30fps
        window_stride=30,
        freq_method='zerocross',
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return

    print("摄像头已打开。按 'q' 退出。")

    frame_buffer = []
    buffer_size = engine.window_frames

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 检测人脸
        bbox = engine.face_detector.detect_face_roi(frame)
        if bbox is not None:
            roi = engine.face_detector.crop_and_resize(frame, bbox)
            frame_buffer.append(roi)

        # 累积足够帧后处理
        if len(frame_buffer) >= buffer_size:
            frames_array = np.array(frame_buffer[-buffer_size:])
            result = engine.process_frames(frames_array)
            emotions = result.to_dict()['emotions']
            print(
                f"\rE1={emotions['aggression']:5.1f} "
                f"E2={emotions['stress']:5.1f} "
                f"E3={emotions['tension']:5.1f} "
                f"K={result.K_value:6.2f}",
                end='',
            )

        cv2.imshow('VibraImage', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        example_offline_video(sys.argv[1])
    else:
        print(__doc__)
        print("用法:")
        print("  python example_usage.py <video_path>    # 分析视频文件")
        print("  python example_usage.py                 # 显示此帮助")
        print()
        print("或使用CLI:")
        print("  python -m vibraimage <video_path>")
