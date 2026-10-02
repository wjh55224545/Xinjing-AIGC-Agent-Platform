# -*- coding: utf-8 -*-
"""
FaceDetector 后备模式测试
=========================

覆盖: 全帧 ROI 后备（无 YOLO / 无 Haar 时可用）、ROI 裁剪与缩放、
      视频帧序列检测完整性。
"""

import numpy as np
import pytest


class TestFullFrameFallback:
    """全帧 ROI 后备模式（RAVDESS 等人脸居中抽帧场景）"""

    def test_full_frame_roi_returns_whole_frame(self):
        """无模型无 Haar 时，detect_face_roi 返回整帧边界框。"""
        from vibraimage.pipeline.face_detector import FaceDetector

        detector = FaceDetector()
        # 强制进入全帧模式
        detector.model = None
        detector._use_haar = False

        frame = np.zeros((224, 224, 3), dtype=np.uint8)
        bbox = detector.detect_face_roi(frame)
        assert bbox == (0, 0, 224, 224)

    def test_detect_faces_in_video_full_frame(self):
        """全帧模式下，视频所有帧都得到 ROI 且尺寸一致。"""
        from vibraimage.pipeline.face_detector import FaceDetector

        detector = FaceDetector()
        detector.model = None
        detector._use_haar = False

        frames = np.zeros((5, 224, 224, 3), dtype=np.uint8)
        face_frames, bboxes = detector.detect_faces_in_video(frames, as_grayscale=True)
        assert face_frames.shape == (5, 224, 224)
        assert all(b is not None for b in bboxes)


class TestCropResize:
    """ROI 裁剪与缩放"""

    def test_crop_and_resize_grayscale(self):
        """裁剪后缩放为 ROI 尺寸的灰度图。"""
        from vibraimage.pipeline.face_detector import FaceDetector

        detector = FaceDetector()
        frame = np.ones((200, 200, 3), dtype=np.uint8) * 128
        roi = detector.crop_and_resize(frame, (10, 10, 110, 110), as_grayscale=True)
        assert roi.shape == (224, 224)
        assert roi.dtype == np.float32

    def test_crop_and_resize_invalid_bbox_returns_zero(self):
        """无效边界框返回零图而非崩溃。"""
        from vibraimage.pipeline.face_detector import FaceDetector

        detector = FaceDetector()
        frame = np.ones((100, 100, 3), dtype=np.uint8)
        roi = detector.crop_and_resize(frame, (50, 50, 50, 50), as_grayscale=True)
        assert roi.shape == (224, 224)
        assert roi.sum() == 0.0

    def test_crop_and_resize_color(self):
        """彩色 ROI 保留三通道。"""
        from vibraimage.pipeline.face_detector import FaceDetector

        detector = FaceDetector()
        frame = np.ones((200, 200, 3), dtype=np.uint8) * 100
        roi = detector.crop_and_resize(frame, (0, 0, 100, 100), as_grayscale=False)
        assert roi.shape == (224, 224, 3)


class TestHeadRegion:
    """头部区域裁剪逻辑"""

    def test_head_region_within_bounds(self):
        """头部区域不越界。"""
        from vibraimage.pipeline.face_detector import FaceDetector

        detector = FaceDetector()
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        bbox = detector._crop_head_region(frame, 10, 10, 150, 230)
        x1, y1, x2, y2 = bbox
        assert 0 <= x1 < x2 <= 320
        assert 0 <= y1 < y2 <= 240
