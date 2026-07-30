#!/usr/bin/env python3
"""
心镜·AIGC智能体平台 — 端到端 Demo 脚本 (一键启动版)
=====================================================

自动完成全链路：
  1. 构建前端（npm run build → static/）
  2. 启动后端（uvicorn）
  3. 轮询等待就绪
  4. [可选] 启动前端开发服务器（vite）
  5. 运行 8 步验证流程
  6. 打开浏览器 → 交付前端

用法:
    python demo.py                      # 验证模式（后端需已启动）
    python demo.py --full               # 一键启动：构建 + 启动 + 验证 + 打开浏览器
    python demo.py --full --no-open     # 同上，不自动打开浏览器（云环境/SSH隧道）
    python demo.py --full --frontend-dev # 额外启动 vite 开发服务器（端口5173）
    python demo.py --full --rebuild      # 强制重新构建前端
    python demo.py --generate           # 仅生成演示视频
    python demo.py --quick              # 跳过 LLM 调用（快）
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
import webbrowser
from datetime import datetime

BASE = "http://127.0.0.1:8000"
FRONTEND_DEV_PORT = 5173
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
STATIC_DIR = os.path.join(ROOT_DIR, "static")
DATA_DIR = os.path.join(ROOT_DIR, "data", "demo")
os.makedirs(DATA_DIR, exist_ok=True)

# 后台子进程引用，用于 Ctrl+C 统一清理
_backend_proc = None
_frontend_proc = None


# ═══════════════════════════════════════════════════════════════
# HTTP 工具
# ═══════════════════════════════════════════════════════════════

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
    print(f"\n{'=' * 60}")
    if title:
        print(f"  {title}")
        print(f"{'=' * 60}")


def step(n: int, label: str) -> float:
    print(f"\n{'─' * 50}")
    print(f"  [{n}/8] {label}")
    print(f"{'─' * 50}")
    return time.time()


# ═══════════════════════════════════════════════════════════════
# 前端构建
# ═══════════════════════════════════════════════════════════════

def _check_npm() -> bool:
    """检查 npm 是否可用。"""
    try:
        subprocess.run(
            ["npm", "--version"], capture_output=True,
            cwd=FRONTEND_DIR, timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _build_frontend(force: bool = False) -> bool:
    """
    构建前端到 static/ 目录。
    返回 True 表示构建成功或已有构建产物。
    """
    index_html = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_html) and not force:
        print(f"[FRONTEND] 已有构建产物: {index_html}")
        print(f"            使用 --rebuild 强制重新构建")
        return True

    if not os.path.isdir(FRONTEND_DIR):
        print(f"[FRONTEND] 前端目录不存在: {FRONTEND_DIR}")
        return False

    if not os.path.isfile(os.path.join(FRONTEND_DIR, "package.json")):
        print("[FRONTEND] package.json 不存在，跳过前端构建")
        return False

    if not _check_npm():
        print("[FRONTEND] npm 不可用，跳过前端构建（后端将仅提供 API 服务）")
        print("           安装 Node.js 后运行: cd frontend && npm install && npm run build")
        return False

    # 安装依赖（如需要）
    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        print("[FRONTEND] 安装前端依赖 (npm install)...")
        try:
            subprocess.run(
                ["npm", "install", "--registry=https://registry.npmmirror.com"],
                cwd=FRONTEND_DIR, check=True, timeout=120,
            )
        except subprocess.CalledProcessError:
            print("[FRONTEND] npm install 失败，跳过前端构建")
            return False

    # 构建
    print("[FRONTEND] 构建前端 (npm run build)...")
    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=FRONTEND_DIR, check=True, timeout=120,
        )
        if os.path.isfile(os.path.join(STATIC_DIR, "index.html")):
            print(f"[FRONTEND] ✓ 构建完成 → {STATIC_DIR}")
            return True
        else:
            print("[FRONTEND] 构建完成但未生成 index.html，请检查 vite 配置")
            return False
    except subprocess.CalledProcessError:
        print("[FRONTEND] 构建失败，后端将仅提供 API 服务")
        return False


# ═══════════════════════════════════════════════════════════════
# 服务启动
# ═══════════════════════════════════════════════════════════════

def _start_backend(host: str = "127.0.0.1", port: int = 8000) -> subprocess.Popen:
    """启动后端 uvicorn 进程。"""
    global _backend_proc
    print(f"[BACKEND] 启动后端服务 {host}:{port}...")
    _backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", host, "--port", str(port)],
        cwd=ROOT_DIR,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return _backend_proc


def _wait_for_backend(timeout: int = 60) -> bool:
    """轮询 /api/health 直到后端就绪。"""
    print("[BACKEND] 等待后端就绪...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{BASE}/api/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    print(f"\n[BACKEND] ✓ 就绪 (v{data.get('version', '?')})")
                    return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1)

    print(f"\n[BACKEND] ✗ 超时（{timeout}s），请检查后端日志")
    return False


def _start_frontend_dev() -> subprocess.Popen | None:
    """启动 vite 前端开发服务器。"""
    global _frontend_proc
    if not _check_npm():
        print("[FRONTEND-DEV] npm 不可用，跳过前端开发服务器")
        return None

    if not os.path.isdir(os.path.join(FRONTEND_DIR, "node_modules")):
        print("[FRONTEND-DEV] node_modules 不存在，跳过")
        return None

    print(f"[FRONTEND-DEV] 启动 Vite 开发服务器 (端口 {FRONTEND_DEV_PORT})...")
    _frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(2)
    if _frontend_proc.poll() is not None:
        print("[FRONTEND-DEV] ✗ Vite 启动失败")
        _frontend_proc = None
        return None
    print(f"[FRONTEND-DEV] ✓ Vite 开发服务器: http://localhost:{FRONTEND_DEV_PORT}")
    return _frontend_proc


# ═══════════════════════════════════════════════════════════════
# 浏览器
# ═══════════════════════════════════════════════════════════════

def _open_browser(url: str):
    """打开默认浏览器。"""
    print(f"\n[BROWSER] 打开浏览器 → {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[BROWSER] 无法自动打开浏览器: {e}")


# ═══════════════════════════════════════════════════════════════
# 访问指引
# ═══════════════════════════════════════════════════════════════

def _print_access_info(frontend_dev: bool = False, host: str = "127.0.0.1",
                       port: int = 8000, cloud_mode: bool = False):
    """打印访问入口信息。"""
    divider("🌐 访问入口")
    print(f"  仪表盘:    http://localhost:{port}")
    print(f"  API 文档:  http://localhost:{port}/docs")
    print(f"  健康检查:  http://localhost:{port}/api/health")

    if frontend_dev:
        print(f"  Vite 开发:  http://localhost:{FRONTEND_DEV_PORT}")

    if cloud_mode:
        print(f"\n  ┌─────────────────────────────────────────────┐")
        print(f"  │ 云环境：通过 SSH 隧道访问                  │")
        print(f"  │                                             │")
        print(f"  │ 在本地终端执行:                            │")
        print(f"  │ ssh -L {port}:localhost:{port} <容器连接信息>    │")
        print(f"  │                                             │")
        print(f"  │ 然后浏览器打开 http://localhost:{port}        │")
        print(f"  └─────────────────────────────────────────────┘")

    has_frontend = os.path.isfile(os.path.join(STATIC_DIR, "index.html"))
    if not has_frontend and not frontend_dev:
        print(f"\n  ⚠ 前端未构建，访问 / 将跳转到 API 文档")
        print(f"    构建前端: cd frontend && npm install && npm run build")


# ═══════════════════════════════════════════════════════════════
# 信号处理
# ═══════════════════════════════════════════════════════════════

def _cleanup(signum=None, frame=None):
    """清理子进程。"""
    print("\n正在关闭服务...")
    for proc, name in [(_frontend_proc, "前端"), (_backend_proc, "后端")]:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            print(f"  {name} 已关闭")
    print("再见。")
    sys.exit(0)


def _keep_alive():
    """保持服务运行，直到用户 Ctrl+C。"""
    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    print(f"\n{'─' * 50}")
    print("  服务运行中，按 Ctrl+C 退出")
    print(f"{'─' * 50}")

    # 等待任一子进程退出
    procs = [p for p in [_backend_proc, _frontend_proc] if p is not None]
    if not procs:
        return

    while True:
        for proc in procs:
            if proc.poll() is not None:
                # 有进程异常退出
                print(f"\n⚠ 服务意外退出 (exit code: {proc.returncode})")
                _cleanup()
                return
        time.sleep(0.5)


# ═══════════════════════════════════════════════════════════════
# 生成演示视频
# ═══════════════════════════════════════════════════════════════

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

    mouth_params = {
        "happy":    ("arc_up", 1.0),
        "sad":      ("arc_down", 1.0),
        "neutral":  ("flat", 1.0),
        "surprised": ("open", 1.0),
    }
    eye_params = {
        "happy":    1.0,
        "sad":      1.1,
        "neutral":  1.3,
        "surprised": 2.0,
    }
    mouth_w, mouth_h = mouth_params.get(expression, ("flat", 1.0))

    for i in range(n_frames):
        t = i / fps
        frame_bg = np.full((H, W, 3), 180, dtype=np.uint8)

        shake_x = int(1.5 * np.sin(2 * np.pi * 4.0 * t))
        shake_y = int(0.8 * np.sin(2 * np.pi * 3.5 * t))
        cx = W // 2 + shake_x
        cy = H // 2 - 20 + shake_y

        cv2.ellipse(frame_bg, (cx, cy - 20), (105, 125), 0, 0, 360, (50, 35, 25), -1)
        cv2.ellipse(frame_bg, (cx, cy), (85, 105), 0, 0, 360, (210, 180, 165), -1)

        eye_y = cy - 25
        eye_x_off = 28
        cv2.circle(frame_bg, (cx - eye_x_off, eye_y), 18, (130, 110, 100), -1)
        cv2.circle(frame_bg, (cx + eye_x_off, eye_y), 18, (130, 110, 100), -1)

        er = int(14 * eye_params.get(expression, 1.0))
        er_h = max(6, min(16, er))
        er_w = max(8, min(16, er))
        for sx in [-1, 1]:
            ex, ey = cx + sx * eye_x_off, eye_y
            cv2.ellipse(frame_bg, (ex, ey), (er_w, er_h), 0, 0, 360, (240, 240, 240), -1)
            cv2.circle(frame_bg, (ex, ey + 1), max(3, er // 3), (40, 30, 20), -1)

        brow_y = eye_y - 18
        for sx in [-1, 1]:
            bx, by = cx + sx * eye_x_off, brow_y
            pts = np.array([[bx - 16, by + 3], [bx - 8, by], [bx, by - 1],
                           [bx + 8, by], [bx + 16, by + 3]], dtype=np.int32)
            cv2.polylines(frame_bg, [pts], False, (60, 40, 25), 2)

        nose_top = eye_y + 10
        nose_bot = cy + 30
        cv2.line(frame_bg, (cx - 3, nose_top), (cx - 3, nose_bot), (170, 140, 125), 2)
        cv2.line(frame_bg, (cx + 3, nose_top), (cx + 3, nose_bot), (170, 140, 125), 2)
        cv2.line(frame_bg, (cx, nose_top), (cx, nose_bot - 5), (220, 200, 185), 1)

        mouth_y = cy + 50
        mw = 23
        if isinstance(mouth_w, str):
            if mouth_w == "arc_up":
                cv2.ellipse(frame_bg, (cx, mouth_y - 3), (mw, 14), 0, 20, 160, (140, 70, 60), -1)
            elif mouth_w == "arc_down":
                cv2.ellipse(frame_bg, (cx, mouth_y + 12), (mw, 14), 0, 200, 340, (130, 70, 65), -1)
            elif mouth_w == "open":
                cv2.ellipse(frame_bg, (cx, mouth_y), (mw - 3, 18), 0, 0, 360, (80, 40, 35), -1)
            else:
                cv2.ellipse(frame_bg, (cx, mouth_y), (mw, 7), 0, 0, 180, (150, 80, 70), -1)
        else:
            cv2.ellipse(frame_bg, (cx, mouth_y), (mw, 7), 0, 0, 180, (150, 80, 70), -1)

        writer.write(frame_bg)

    writer.release()
    return path


# ═══════════════════════════════════════════════════════════════
# 验证流程
# ═══════════════════════════════════════════════════════════════

def run_demo(quick: bool = False):
    """运行 8 步端到端验证。"""
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
    print(f"  [TIME]  {time.time() - t:.2f}s")

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

    # 4. 生成演示视频
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
                r_dict.update({
                    "success": "True", "emotion": r.data.get("fused_emotion", "?"),
                    "score": str(r.data.get("fused_score", 0)),
                    "facial": r.data.get("facial_emotion", "?"),
                    "faces": str(r.data.get("faces_detected", 0)),
                })
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
                "indicators": {
                    "emotional_stability_index": 0.72, "positive_emotion_ratio": 0.62,
                    "negative_emotion_ratio": 0.18, "trend": "稳定",
                },
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
    divider("Demo 验证完成 [OK]")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="心镜·AIGC智能体平台 — 端到端 Demo 一键启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python demo.py --full                   一键启动（构建前端 + 后端 + 验证 + 打开浏览器）
  python demo.py --full --no-open         云环境模式（不打开浏览器，打印SSH隧道指引）
  python demo.py --full --frontend-dev    同时启动 vite 开发服务器（热重载）
  python demo.py --quick                 仅验证（跳过LLM调用，后端需已启动）
  python demo.py --generate              仅生成演示视频
        """,
    )
    parser.add_argument("--full", action="store_true",
                        help="一键启动：构建前端 + 启动后端 + 验证 + 打开前端")
    parser.add_argument("--quick", action="store_true",
                        help="跳过 LLM 调用")
    parser.add_argument("--generate", action="store_true",
                        help="仅生成演示视频")
    parser.add_argument("--frontend-dev", action="store_true",
                        help="额外启动 vite 前端开发服务器（端口5173）")
    parser.add_argument("--no-open", action="store_true",
                        help="不自动打开浏览器（云环境/SSH隧道场景）")
    parser.add_argument("--rebuild", action="store_true",
                        help="强制重新构建前端")
    parser.add_argument("--host", default="127.0.0.1",
                        help="后端监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8000,
                        help="后端端口（默认 8000）")
    args = parser.parse_args()

    # -- 仅生成视频 --
    if args.generate:
        for expr, name in [("happy", "开心表情"), ("neutral", "中性表情"),
                           ("sad", "悲伤表情"), ("angry", "愤怒表情")]:
            path = os.path.join(DATA_DIR, f"demo_{expr}.mp4")
            generate_demo_video(path, expression=expr)
            print(f"[OK] 生成: {path} ({name})")
        print(f"\n演示视频已生成到: {DATA_DIR}")
        return

    # -- 判断是否为云环境（无 DISPLAY 环境变量） --
    is_cloud = not os.environ.get("DISPLAY") and sys.platform != "win32"

    # -- 一键启动模式 --
    if args.full:
        global BASE
        BASE = f"http://{args.host}:{args.port}"

        divider("心镜·AIGC智能体平台 — 一键启动")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  地址: {args.host}:{args.port}")

        # 1. 构建前端
        divider("步骤 1/5: 构建前端")
        frontend_built = _build_frontend(force=args.rebuild)

        # 2. 启动后端
        divider("步骤 2/5: 启动后端服务")
        _start_backend(host=args.host, port=args.port)

        # 3. 等待就绪
        divider("步骤 3/5: 等待服务就绪")
        if not _wait_for_backend():
            print("[ERROR] 后端启动失败，请查看上方日志")
            _cleanup()
            return

        # 4. [可选] 启动前端开发服务器
        if args.frontend_dev:
            divider("步骤 4/5: 启动前端开发服务器")
            _start_frontend_dev()

        # 5. 运行验证
        divider("步骤 5/5: 端到端验证")
        try:
            run_demo(quick=args.quick)
        except Exception as e:
            print(f"\n[WARN] 验证过程出现异常（不影响服务运行）: {e}")

        # 打印访问信息
        _print_access_info(
            frontend_dev=args.frontend_dev,
            host=args.host, port=args.port,
            cloud_mode=(is_cloud or args.no_open),
        )

        # 打开浏览器
        if not args.no_open:
            _open_browser(f"http://localhost:{args.port}")

        # 保持服务运行
        _keep_alive()

    else:
        # -- 仅验证模式（后端需已启动） --
        run_demo(quick=args.quick)
        has_frontend = os.path.isfile(os.path.join(STATIC_DIR, "index.html"))
        print(f"\n访问前端: {BASE}" if has_frontend else f"\n访问 API 文档: {BASE}/docs")
        if has_frontend:
            if not os.environ.get("DISPLAY") and sys.platform != "win32":
                print(f"SSH隧道: ssh -L {args.port}:localhost:{args.port} <容器连接信息>")


if __name__ == "__main__":
    main()
