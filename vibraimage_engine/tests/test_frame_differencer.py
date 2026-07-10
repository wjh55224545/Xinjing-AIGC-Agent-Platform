"""
测试 frame_differencer 模块。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from vibraimage.core.frame_differencer import FrameDifferencer


def test_basic_difference():
    """测试基本的帧差分功能。"""
    differencer = FrameDifferencer(noise_threshold=0.0)
    frames = np.array([
        [[0, 0, 0], [0, 0, 0]],
        [[1, 2, 3], [4, 5, 6]],
        [[2, 4, 6], [8, 10, 12]],
    ], dtype=np.float32)

    diff = differencer.compute(frames)
    assert diff.shape == (2, 2, 3), f"Wrong shape: {diff.shape}"
    # Frame 1-0: diff should be [[1,2,3],[4,5,6]]
    assert np.allclose(diff[0], np.array([[1, 2, 3], [4, 5, 6]])), f"Wrong diff[0]: {diff[0]}"
    print("[PASS] test_basic_difference")


def test_noise_threshold():
    """测试噪声阈值。"""
    differencer = FrameDifferencer(noise_threshold=3.0)
    frames = np.array([
        [[0, 0, 0], [0, 0, 0]],
        [[1, 2, 5], [4, 10, 6]],
    ], dtype=np.float32)

    diff = differencer.compute(frames)
    # Values < 3 should be zero
    assert diff[0, 0, 0] == 0.0, f"Expected 0, got {diff[0,0,0]}"
    assert diff[0, 0, 1] == 0.0, f"Expected 0, got {diff[0,0,1]}"
    assert diff[0, 0, 2] == 5.0, f"Expected 5, got {diff[0,0,2]}"
    assert diff[0, 1, 0] == 4.0, f"Expected 4, got {diff[0,1,0]}"
    assert diff[0, 1, 1] == 10.0, f"Expected 10, got {diff[0,1,1]}"
    print("[PASS] test_noise_threshold")


def test_accumulate():
    """测试多帧累积。"""
    differencer = FrameDifferencer(noise_threshold=0.0, accumulate_frames=2)
    frames = np.array([
        [[0, 0], [0, 0]],
        [[1, 1], [1, 1]],
        [[3, 3], [3, 3]],
        [[6, 6], [6, 6]],
    ], dtype=np.float32)

    diff = differencer.compute(frames)
    # With accumulate_frames=2:
    # - diff[0] = abs(f1-f0) = [[1,1],[1,1]]
    # - diff[1] = abs(f2-f1) = [[2,2],[2,2]]
    # - diff[2] = abs(f3-f2) = [[3,3],[3,3]]
    # - accumulated[0] = diff[0]+diff[1] = [[3,3],[3,3]]
    # - accumulated[1] = diff[1]+diff[2] = [[5,5],[5,5]]
    assert diff.shape[0] == 2, f"Wrong accumulated shape: {diff.shape}"
    assert np.allclose(diff[0], np.array([[3, 3], [3, 3]])), f"Wrong accumulated[0]: {diff[0]}"
    assert np.allclose(diff[1], np.array([[5, 5], [5, 5]])), f"Wrong accumulated[1]: {diff[1]}"
    print("[PASS] test_accumulate")


def test_statistics():
    """测试统计量。"""
    differencer = FrameDifferencer()
    frames = np.random.randn(10, 32, 32).astype(np.float32)
    diff = differencer.compute(frames)
    stats = differencer.compute_statistics(diff)
    assert 'mean_diff' in stats
    assert 'std_diff' in stats
    assert 'activity_level' in stats
    assert len(stats['spatial_mean_per_frame']) == 9
    print("[PASS] test_statistics")


if __name__ == '__main__':
    test_basic_difference()
    test_noise_threshold()
    test_accumulate()
    test_statistics()
    print("\n所有 frame_differencer 测试通过!")
