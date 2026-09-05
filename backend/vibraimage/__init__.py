"""
VibraImage Engine — 从零实现的VibraImage情绪识别引擎。

基于 Viktor Minkin "Vibraimage, Cybernetics and Emotions" (2020) 专著中的
公开公式，实现逐像素帧差分 → 频率分析 → 情绪参数计算的完整流水线。

v0.2.0 更新:
    - 短视频容错修复: _process_windows() 帧数不足时自动收缩窗口
    - 新增 L2 映射层: E1-E12 → Z-Score → 效价/唤醒度 → 10 类情绪

引擎能力:
    - L1: 视频 → 人脸检测(YOLOv8) → 帧差分 → 频率分析 → E1-E12参数 + K值
    - L2: E1-E12 → Z-Score标准化 → 加权求和 → 效价/唤醒度 → 10类情绪分类

使用方法:
    from backend.vibraimage.pipeline.engine import VibraImageEngine
    engine = VibraImageEngine()
    results = engine.process_video("path/to/video.mp4")

    from backend.vibraimage.mapping.emotion_mapper import EmotionMapper
    mapper = EmotionMapper()
    emotion = mapper.map(results.to_dict()['emotions'], K=results.K_value)
"""

__version__ = "0.2.0"
