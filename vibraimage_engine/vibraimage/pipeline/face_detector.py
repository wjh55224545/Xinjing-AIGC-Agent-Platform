"""
人脸/头部检测模块。

使用YOLOv8检测人体并裁剪头部ROI区域。
参考现有demo_vestibular.py中的检测逻辑:
    - 检测人体(person)边界框
    - 取上部40%为头部区域
    - 缩放到统一尺寸供后续分析

VibraImage产品使用前置摄像头捕捉人脸，本模块提供等效功能。
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class FaceDetector:
    """
    基于YOLOv8的头部ROI检测器。

    检测视频帧中的人体(person)，裁剪头部区域。

    Parameters
    ----------
    model_path : str, default='yolov8n.pt'
        YOLOv8模型路径。默认使用nano版本。
    roi_size : tuple, default=(224, 224)
        ROI缩放尺寸 (H, W)。
    conf_threshold : float, default=0.5
        检测置信度阈值。
    head_ratio : float, default=0.4
        头部在人体框中的比例 (取上部head_ratio部分)。
    head_extend : float, default=0.3
        头部区域向下延伸的比例。
    """

    def __init__(
        self,
        model_path: str = 'yolov8n.pt',
        roi_size: Tuple[int, int] = (224, 224),
        conf_threshold: float = 0.5,
        head_ratio: float = 0.4,
        head_extend: float = 0.3,
    ):
        self.roi_size = roi_size
        self.conf_threshold = conf_threshold
        self.head_ratio = head_ratio
        self.head_extend = head_extend

        self.model = None
        self._load_model(model_path)

    def _load_model(self, model_path: str):
        """延迟加载YOLO模型。"""
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            logger.info(f"YOLO模型加载成功: {model_path}")
        except ImportError:
            logger.warning(
                "ultralytics未安装，请执行: pip install ultralytics\n"
                "将使用Haar Cascade作为后备方案。"
            )
            self._load_haar_cascade()
        except Exception as e:
            logger.warning(f"YOLO加载失败: {e}，使用Haar Cascade后备")
            self._load_haar_cascade()

    def _load_haar_cascade(self):
        """加载OpenCV Haar Cascade作为后备方案。"""
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self._face_cascade = cv2.CascadeClassifier(cascade_path)
        self._use_haar = True
        logger.info("使用Haar Cascade人脸检测")

    def detect_face_roi(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        在单帧中检测头部ROI边界框。

        Parameters
        ----------
        frame : np.ndarray, shape (H, W, 3)
            BGR彩色帧。

        Returns
        -------
        bbox : tuple or None
            (x1, y1, x2, y2) 头部ROI坐标，未检测到时返回None。
        """
        if self.model is not None:
            return self._detect_yolo(frame)
        else:
            return self._detect_haar(frame)

    def _detect_yolo(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """YOLOv8检测。"""
        results = self.model(frame, verbose=False)

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                # 只检测person类 (COCO class 0)
                if cls_id == 0 and conf >= self.conf_threshold:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                    # 裁剪头部区域
                    head_roi = self._crop_head_region(frame, x1, y1, x2, y2)
                    if head_roi is not None:
                        return head_roi

        return None

    def _detect_haar(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Haar Cascade人脸检测 (后备方案)。"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )

        if len(faces) > 0:
            # 取最大的人脸
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            return (x, y, x + w, y + h)

        return None

    def _crop_head_region(
        self,
        frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
    ) -> Tuple[int, int, int, int]:
        """
        从人体边界框裁剪头部区域。

        逻辑 (来自demo_vestibular.py):
            head_height = (y2 - y1) * head_ratio
            neck_y = y1 + head_height * 0.8
            head_y2 = neck_y + head_height * head_extend
        """
        H, W = frame.shape[:2]
        person_height = y2 - y1

        head_height = int(person_height * self.head_ratio)
        neck_y = y1 + int(head_height * 0.8)
        head_y2 = min(H, neck_y + int(head_height * self.head_extend))

        return (max(0, x1), max(0, y1), min(W, x2), min(H, head_y2))

    def crop_and_resize(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        as_grayscale: bool = True,
    ) -> np.ndarray:
        """
        裁剪并缩放ROI。

        Parameters
        ----------
        frame : np.ndarray
            原始帧。
        bbox : tuple
            (x1, y1, x2, y2) 边界框。
        as_grayscale : bool
            是否转为灰度图。

        Returns
        -------
        roi : np.ndarray, shape (H_roi, W_roi) or (H_roi, W_roi, 3)
        """
        x1, y1, x2, y2 = bbox

        # 边界检查
        H, W = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)

        if x2 <= x1 or y2 <= y1:
            # 无效bbox → 返回零图
            if as_grayscale:
                return np.zeros(self.roi_size, dtype=np.float32)
            else:
                return np.zeros((*self.roi_size, 3), dtype=np.float32)

        roi = frame[y1:y2, x1:x2]
        roi = cv2.resize(roi, self.roi_size[::-1])  # cv2.resize takes (W, H)

        if as_grayscale and roi.ndim == 3:
            roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        return roi.astype(np.float32)

    def detect_faces_in_video(
        self,
        frames: np.ndarray,
        as_grayscale: bool = True,
    ) -> Tuple[np.ndarray, List[Optional[Tuple[int, int, int, int]]]]:
        """
        对视频的所有帧检测人脸并裁剪ROI。

        Parameters
        ----------
        frames : np.ndarray, shape (N, H, W, 3)
            视频帧序列 (BGR彩色)。
        as_grayscale : bool
            ROI是否转为灰度。

        Returns
        -------
        face_frames : np.ndarray, shape (N, H_roi, W_roi) or (N, H_roi, W_roi)
            裁剪后的ROI帧序列。
        bboxes : list of tuples
            每帧的检测边界框。
        """
        N = frames.shape[0]
        face_frames = []
        bboxes = []

        for i in range(N):
            bbox = self.detect_face_roi(frames[i])
            bboxes.append(bbox)

            if bbox is not None:
                roi = self.crop_and_resize(frames[i], bbox, as_grayscale)
            else:
                # 未检测到 → 黑色填充
                if as_grayscale:
                    roi = np.zeros(self.roi_size, dtype=np.float32)
                else:
                    roi = np.zeros((*self.roi_size, 3), dtype=np.float32)

            face_frames.append(roi)

        return np.array(face_frames), bboxes
