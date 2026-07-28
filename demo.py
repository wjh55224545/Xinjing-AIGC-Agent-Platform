#!/usr/bin/env python3
"""
心镜·AIGC智能体平台 — 端到端 Demo 脚本
========================================

自动执行全链路演示：
  1. 启动服务 → 2. 仪表盘 → 3. 上传视频 → 4. 情绪识别 → 5. 外环分析
  → 6. AIGC 报告 → 7. 预警面板 → 8. 汇总

用法:
    python demo.py                  # 全流程（需要后端已启动）
    python demo.py --full           # 启动服务 + 全流程
    python demo.py --generate       # 仅生成演示视频
    python demo.py --quick          # 跳过 LLM 调用（快）
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

BASE = "http://127.0.0.1:8000"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "demo")
os.makedirs(DATA_DIR, exist_ok=True)


def http(method: str, path: str, **kwargs) -> dict:
    """简易 HTTP 客户端。"""
    url = f"{BASE}{path}"
    data = kwargs.pop("data", None)
    if data is not None:
        data = json.dumps(data).encode()
    try:
        req = urllib.request.Request(url, data=data, method=method, **kwargs)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"_error": e.code, "_body": body[:300]}
    except Exception as e:
        return {"_error": str(e)}


def divider(title: str = ""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
        print(f"{'='*60}")


def step(n: int, label: str) -> float:
    print(f"\n{'─'*50}")
    print(f"  [{n}/8] {label}")
    print(f"{'─'*50}")
    return time.time()


# ========================
# 生成演示视频
# ========================

def generate_demo_video(path: str, expression: str = "happy",
                        duration_sec: float = 8.0, fps: int = 30):
    """
    生成带表情的真实人脸模拟视频。

    使用 OpenCV 绘制高对比度面部特征（含眼窝阴影、鼻梁高光），
    确保 Haar Cascade 人脸检测器能够正确识别。

    expression: happy / sad / neutral / surprised
    """
    import cv2
    import numpy as np

    H, W = 480, 640
    n_frames = int(duration_sec * fps)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(path, fourcc, fps, (W, H))

    # 面部参数定义（不同表情）
    mouth_params = {
        "happy":  ("arc_up", 1.0),
        "sad":    ("arc_down", 1.0),
        "neutral": ("flat", 1.0),
        "surprised": ("open", 1.0),
    }
    eye_params = {
        "happy":  1.0,        # 眯眼（椭圆半短轴小）
        "sad":    1.1,
        "neutral": 1.3,
        "surprised": 2.0,     # 睁大眼睛
    }
    mouth_w, mouth_h = mouth_params.get(expression, ("flat", 1.0))

    for i in range(n_frames):
        t = i / fps
        # 皮肤底色 + 微振动
        frame_bg = np.full((H, W, 3), 180, dtype=np.uint8)

        # 微振动 (3-5Hz 生理性震颤)
        shake_x = int(1.5 * np.sin(2 * np.pi * 4.0 * t))
        shake_y = int(0.8 * np.sin(2 * np.pi * 3.5 * t))
        cx = W // 2 + shake_x
        cy = H // 2 - 20 + shake_y

        # === 绘制高对比度人脸（Cascade 可检测） ===

        # 1. 头发（椭圆形深色区域，形成头部轮廓）
        cv2.ellipse(frame_bg, (cx, cy - 20), (105, 125), 0, 0, 360, (50, 35, 25), -1)

        # 2. 面部（浅肤色椭圆，Cascade需要面部-背景对比）
        face_x, face_y = cx, cy
        cv2.ellipse(frame_bg, (face_x, face_y), (85, 105), 0, 0, 360, (210, 180, 165), -1)

        # 3. 眼窝阴影（Cascade靠这个检测人脸）
        eye_y = face_y - 25
        eye_x_off = 28
        cv2.circle(frame_bg, (face_x - eye_x_off, eye_y), 18, (130, 110, 100), -1)
        cv2.circle(frame_bg, (face_x + eye_x_off, eye_y), 18, (130, 110, 100), -1)

        # 4. 眼白
        er = int(14 * eye_params.get(expression, 1.0))
        er_h = max(6, min(16, er))
        er_w = max(8, min(16, er))
        for sx in [-1, 1]:
            ex, ey = face_x + sx * eye_x_off, eye_y
            cv2.ellipse(frame_bg, (ex, ey), (er_w, er_h), 0, 0, 360, (240, 240, 240), -1)
            # 瞳孔
            cv2.circle(frame_bg, (ex, ey + 1), max(3, er // 3), (40, 30, 20), -1)

        # 5. 眉毛（深色弧线）
        brow_y = eye_y - 18
        for sx in [-1, 1]:
            bx, by = face_x + sx * eye_x_off, brow_y
            pts = np.array([[bx - 16, by + 3], [bx - 8, by], [bx, by - 1],
                           [bx + 8, by], [bx + 16, by + 3]], dtype=np.int32)
            cv2.polylines(frame_bg, [pts], False, (60, 40, 25), 2)

        # 6. 鼻梁（竖线高光+两侧阴影）
        nose_top = eye_y + 10
        nose_bot = face_y + 30
        cv2.line(frame_bg, (face_x - 3, nose_top), (face_x - 3, nose_bot), (170, 140, 125), 2)
        cv2.line(frame_bg, (face_x + 3, nose_top), (face_x + 3, nose_bot), (170, 140, 125), 2)
        cv2.line(frame_bg, (face_x, nose_top), (face_x, nose_bot - 5), (220, 200, 185), 1)

        # 7. 嘴
        mouth_y = face_y + 50
        mw = 23
        if isinstance(mouth_w, str):
            if mouth_w == "arc_up":
                cv2.ellipse(frame_bg, (face_x, mouth_y - 3), (mw, 14), 0, 20, 160, (140, 70, 60), -1)
            elif mouth_w == "arc_down":
                cv2.ellipse(frame_bg, (face_x, mouth_y + 12), (mw, 14), 0, 200, 340, (130, 70, 65), -1)
            elif mouth_w == "open":
                cv2.ellipse(frame_bg, (face_x, mouth_y), (mw - 3, 18), 0, 0, 360, (80, 40, 35), -1)
            else:  # flat
                cv2.ellipse(frame_bg, (face_x, mouth_y), (mw, 7), 0, 0, 180, (150, 80, 70), -1)
        else:
            cv2.ellipse(frame_bg, (face_x, mouth_y), (mw, 7), 0, 0, 180, (150, 80, 70), -1)

        writer.write(frame_bg)

    writer.release()
    return path


# ========================
# 主流程
# ========================

def run_demo(full: bool = False, quick: bool = False):
    divider("心镜·AIGC智能体平台 — 端到端 Demo")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    total_start = time.time()

    # 1. 健康检查
    t = step(1, "健康检查")
    health = http("GET", "/api/health")
    if health.get("status") == "ok":
        print(f"  [OK] 服务正常运行 | 版本: {health.get('version')} | 平台: {health.get('platform')}")
        if health.get("model"):
            print(f"  LLM 模型: {health.get('model')}")
    else:
        print(f"  [FAIL] 服务异常: {health}")
        return
    step_time = time.time() - t
    print(f"  [TIME]  {step_time:.2f}s")

    # 2. 仪表盘
    t = step(2, "仪表盘数据")
    dash = http("GET", "/api/dashboard/summary")
    print(f"  学生总数: {dash.get('total_students', 0)}")
    print(f"  今日均分: {dash.get('today_avg_emotion', 0)}")
    print(f"  活跃预警: {dash.get('active_alerts', 0)}")
    print(f"  绿/黄/红: {dash.get('green_count', 0)}/{dash.get('yellow_count', 0)}/{dash.get('red_count', 0)}")
    print(f"  [TIME]  {time.time() - t:.2f}s")

    # 3. 智能体信息
    t = step(3, "多智能体系统")
    agents = http("GET", "/api/agents/info")
    if agents.get("success"):
        for a in agents["data"]["agents"]:
            print(f"  {a['name']}: {len(a['tools'])} 工具")
        print(f"  调度平台: {agents['data']['platform']}")
    print(f"  [TIME]  {time.time() - t:.2f}s")

    # 4. 生成并上传演示视频
    t = step(4, "生成演示视频")
    video_paths = []
    for expr, name in [("happy", "开心表情"), ("neutral", "中性表情"), ("sad", "悲伤表情")]:
        path = os.path.join(DATA_DIR, f"demo_{expr}.mp4")
        if not os.path.exists(path):
            generate_demo_video(path, expression=expr)
            print(f"  [GEN] 生成: {path} ({name})")
        video_paths.append((path, name))
    print(f"  [TIME]  {time.time() - t:.2f}s")

    # 5. 上传视频触发情绪识别
    t = step(5, "上传视频 → 情绪识别")
    results = []
    for vid_path, label in video_paths:
        if not os.path.exists(vid_path):
            continue
        try:
            from backend.tools.emotion_recognition import EmotionRecognitionTool
            tool = EmotionRecognitionTool()
            t0 = time.time()
            r = tool.execute(video_path=vid_path, student_id=1, baseline_mood=0.7)
            t1 = time.time() - t0
            r_dict = {"label": label, "path": vid_path}
            if r.success:
                r_dict.update({"success": "True", "emotion": r.data.get("fused_emotion", "?"),
                               "score": str(r.data.get("fused_score", 0)),
                               "facial": r.data.get("facial_emotion", "?"),
                               "faces": str(r.data.get("faces_detected", 0))})
            else:
                r_dict.update({"success": "False", "error": r.error or "unknown"})
            r_dict["time"] = f"{t1:.2f}"
            results.append(r_dict)
            status = "[OK]" if r_dict.get("success") == "True" else "[FAIL]"
            print(f"  {status} {label}: {r_dict.get('emotion', r_dict.get('error', '?'))} "
                  f"(耗时{r_dict.get('time', '?')}s | 人脸帧:{r_dict.get('faces', '?')})")
        except Exception as e:
            print(f"  [FAIL] {label}: {e}")
            results.append({"label": label, "success": "False", "error": str(e)})
    print(f"  [TIME]  {time.time() - t:.2f}s")

    # 6. AIGC 报告生成
    if not quick:
        t = step(6, "AIGC 心理评估报告 (Lingshu-32B)")
        report = http("POST", "/api/aigc/report/daily", data={
            "student_name": "演示学生",
            "date": str(datetime.now().date()),
            "emotion_data": {"fused_emotion": "开心", "fused_score": 0.78},
            "analysis_result": {
                "overall_score": 0.76, "risk_level": "green",
                "indicators": {"emotional_stability_index": 0.72, "positive_emotion_ratio": 0.62,
                               "negative_emotion_ratio": 0.18, "trend": "稳定"},
                "risk_factors": [], "suggestions": [{"priority": "low", "content": "保持良好状态"}],
                "lstm_transformer_analysis": {"prediction": {"next_day_emotion": 0.74, "trend_prediction": "稳定"}},
            },
        })
        if report.get("success"):
            print(f"  [OK] 生成成功 ({report['data'].get('generated_by', '?')})")
            text = report["data"].get("report_text", "")[:250]
            print(f"  {text}...")
        else:
            print(f"  [WARN]  {report}")
        print(f"  [TIME]  {time.time() - t:.2f}s")

    # 7. 运营数据
    t = step(7, "运营数据统计")
    stats = http("GET", "/api/admin/stats")
    if stats.get("success"):
        api = stats["data"].get("api", {})
        llm = stats["data"].get("llm", {})
        print(f"  API 请求: {api.get('total_requests', 0)}")
        print(f"  LLM 调用: {llm.get('total_calls', 0)} (成功率: {llm.get('success_rate', 0)})")
        print(f"  Token 消耗: {llm.get('total_tokens', 0)}")
    print(f"  [TIME]  {time.time() - t:.2f}s")

    # 8. 汇总
    t = step(8, "Demo 汇总")
    total = time.time() - total_start
    ok = sum(1 for r in results if r.get("success") == "True")
    print(f"  视频处理: {ok}/{len(results)} 成功")
    print(f"  总耗时: {total:.1f}s")
    print(f"\n  [WEB] 前端页面: {BASE}")
    print(f"  [DOC] API 文档: {BASE}/docs")
    print(f"  [DASH] 仪表盘:   {BASE}/#/ (或 {BASE}/)")
    divider("Demo 完成 [OK]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="心镜 Demo 脚本")
    parser.add_argument("--full", action="store_true", help="启动服务 + 全流程")
    parser.add_argument("--quick", action="store_true", help="跳过 LLM 调用")
    parser.add_argument("--generate", action="store_true", help="仅生成演示视频")
    args = parser.parse_args()

    if args.generate:
        for expr, name in [("happy", "开心表情"), ("neutral", "中性表情"),
                           ("sad", "悲伤表情"), ("angry", "愤怒表情")]:
            path = os.path.join(DATA_DIR, f"demo_{expr}.mp4")
            generate_demo_video(path, expression=expr)
            print(f"[OK] 生成: {path} ({name})")
        print(f"\n演示视频已生成到: {DATA_DIR}")
        sys.exit(0)

    if args.full:
        import subprocess
        print("启动后端服务...")
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app",
             "--host", "127.0.0.1", "--port", "8000"],
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        time.sleep(5)
        try:
            run_demo(full=True, quick=args.quick)
        finally:
            proc.terminate()
    else:
        run_demo(quick=args.quick)
