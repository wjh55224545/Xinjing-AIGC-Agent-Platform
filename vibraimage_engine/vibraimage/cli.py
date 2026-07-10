"""
命令行入口。

使用方法:
    # 分析单个视频
    python -m vibraimage path/to/video.mp4

    # 指定窗口参数
    python -m vibraimage video.mp4 --window-frames 100 --stride 50

    # 输出JSON结果
    python -m vibraimage video.mp4 --output results.json

    # 使用FFT模式 (更精确但更慢)
    python -m vibraimage video.mp4 --method fft
"""

import argparse
import sys
import json
import logging
from pathlib import Path

from .pipeline.engine import VibraImageEngine
from .utils.validation import print_emotion_report, validate_all

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )


def main():
    parser = argparse.ArgumentParser(
        description='VibraImage — 基于头部微振动视频的情绪识别引擎',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m vibraimage test.mp4
  python -m vibraimage test.mp4 --output result.json
  python -m vibraimage test.mp4 --window-frames 100 -v
        """,
    )
    parser.add_argument('video', help='视频文件路径')
    parser.add_argument('--output', '-o', help='结果输出JSON路径')
    parser.add_argument('--window-frames', type=int, default=100,
                        help='每窗口帧数 (默认100, ~3.3s@30fps)')
    parser.add_argument('--stride', type=int, default=50,
                        help='窗口步长 (默认50, 50%%重叠)')
    parser.add_argument('--method', choices=['zerocross', 'fft'], default='zerocross',
                        help='频率分析方法 (默认zerocross)')
    parser.add_argument('--start-time', type=float, default=0.0,
                        help='开始时间 [秒]')
    parser.add_argument('--duration', type=float, default=None,
                        help='处理时长 [秒]')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='详细日志输出')
    parser.add_argument('--no-report', action='store_true',
                        help='不打印参数报告')

    args = parser.parse_args()

    setup_logging(args.verbose)

    # 检查视频文件
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"错误: 视频文件不存在: {args.video}", file=sys.stderr)
        sys.exit(1)

    # 创建引擎
    print(f"初始化VibraImage引擎...")
    print(f"  窗口大小: {args.window_frames}帧")
    print(f"  步长: {args.stride}帧")
    print(f"  频率方法: {args.method}")

    engine = VibraImageEngine(
        window_frames=args.window_frames,
        window_stride=args.stride,
        freq_method=args.method,
    )

    # 处理视频
    print(f"\n处理视频: {video_path}")
    try:
        result = engine.process_video(
            str(video_path),
            start_time=args.start_time,
            duration=args.duration,
        )
    except Exception as e:
        print(f"处理失败: {e}", file=sys.stderr)
        if args.verbose:
            raise
        sys.exit(1)

    # 输出
    emotion_params = result.to_dict()['emotions']

    if not args.no_report:
        print_emotion_report(emotion_params)

        # 额外信息
        psychophys = result.to_dict()['psychophysiological']
        print(f"\n--- 心理生理参数 ---")
        print(f"  稳定性: {psychophys['stability']:.1f}%")
        print(f"\n--- 综合指标 ---")
        print(f"  K值: {result.K_value:.2f}")
        print(f"  解释: {result.to_dict()['K_interpretation']}")

        # 参数验证
        issues = validate_all(emotion_params)
        if issues:
            print(f"\n⚠ 参数警告:")
            for param, msgs in issues.items():
                print(f"  {param}: {', '.join(msgs)}")

    # 保存JSON
    if args.output:
        result.to_json(args.output)
        print(f"\n结果已保存: {args.output}")
    else:
        # 默认输出到视频同目录
        default_output = video_path.with_suffix('.vibraimage.json')
        result.to_json(str(default_output))
        print(f"\n结果已保存: {default_output}")

    print(f"\n处理完成: {result.n_windows}个窗口, {result.duration_sec:.1f}秒")


if __name__ == '__main__':
    main()
