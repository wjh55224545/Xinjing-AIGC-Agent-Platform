"""
VibraImage Engine — 从零实现的VibraImage情绪识别引擎。

基于 Viktor Minkin "Vibraimage, Cybernetics and Emotions" (2020) 专著中的
公开公式，实现逐像素帧差分 → 频率分析 → 情绪参数计算的完整流水线。

使用方法:
    from vibraimage.pipeline.engine import VibraImageEngine
    engine = VibraImageEngine()
    results = engine.process_video("path/to/video.mp4")
"""

__version__ = "0.1.0"
