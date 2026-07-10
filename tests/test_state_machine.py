"""
LangGraph 双环状态机端到端验证脚本

验证项：
1. EmotionRecognitionTool 返回的字段名与状态定义一致
2. 内环图可编译并 invoke
3. 外环图可编译并 invoke
4. Orchestrator 内环返回完整状态（含 fused_emotion + record_id）
5. Orchestrator 外环返回完整状态（含 alerts_generated + feedback_sent）

用法: python tests/test_state_machine.py
"""

import os
import sys
import asyncio

# 在导入任何 backend 模块之前设置测试数据库（文件型，跨连接可见）
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "test_state_machine.db")
# 清理上次运行残留的测试数据库
for _f in [TEST_DB_PATH, TEST_DB_PATH + "-journal"]:
    if os.path.exists(_f):
        os.remove(_f)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 现在安全导入 backend
from backend.database import engine, Base, SessionLocal, init_db
from backend.models.student import Student
from backend.models.emotion_record import EmotionRecord
from backend.graph.inner_loop import build_inner_loop
from backend.graph.outer_loop import build_outer_loop
from backend.graph.state import InnerLoopState, OuterLoopState
from backend.tools.emotion_recognition import EmotionRecognitionTool

pass_count = 0
fail_count = 0


def check(name: str, condition: bool, detail: str = ""):
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  PASS  {name}")
    else:
        fail_count += 1
        print(f"  FAIL  {name}  — {detail}")


# ---------- 准备数据库 ----------

init_db()

db = SessionLocal()
s1 = Student(name="测试学生A", class_name="实验班", student_code="TEST001", baseline_mood=0.72)
db.add(s1)
db.commit()
db.refresh(s1)
student_id = s1.id

# 预置一条情绪记录（供外环聚合使用）
from datetime import datetime
er = EmotionRecord(
    student_id=student_id,
    image_path="/tmp/test_face.jpg",
    facial_emotion="平静", facial_conf=0.85, facial_valence=0.3, facial_arousal=-0.3,
    vestibular_valence=0.25, vestibular_arousal=-0.28, vestibular_confidence=0.72, vestibular_intensity=0.45,
    fused_emotion="平静", fused_score=0.68, fused_valence=0.28, fused_arousal=-0.29,
    confidence_diff=0.13, requires_review=0, estimated_accuracy=0.93,
    recorded_at=datetime.now().isoformat(),
)
db.add(er)
db.commit()
db.close()

print(f"准备完成: 学生 id={student_id}, 预置 1 条情绪记录\n")


# ========== 测试 1: 工具字段名一致性 ==========
print("测试1: EmotionRecognitionTool 字段名一致性")
tool = EmotionRecognitionTool()
result = tool.execute(image_path="/tmp/test_face.jpg", student_id=student_id, baseline_mood=0.72)
check("工具执行成功", result.success, result.error)
check("存在 facial_conf", "facial_conf" in result.data, f"实际 keys: {sorted(result.data.keys())}")
check("facial_conf 是 float", isinstance(result.data.get("facial_conf"), float))
check("facial_conf > 0", result.data.get("facial_conf", 0) > 0)
check("存在 fused_emotion", "fused_emotion" in result.data)
check("存在 fused_score", "fused_score" in result.data)
print()


# ========== 测试 2: 内环图编译与 invoke ==========
print("测试2: 内环图编译与 invoke")
inner = build_inner_loop()
initial_inner: InnerLoopState = {
    "student_id": student_id,
    "video_path": "/tmp/test_face.jpg",
    "trigger_type": "manual",
}
final_inner = inner.invoke(initial_inner)
check("编译图类型正确", hasattr(inner, "invoke"))
check("返回 fused_emotion", "fused_emotion" in final_inner, str(final_inner.get("error", "")))
check("fused_emotion 非空", bool(final_inner.get("fused_emotion")))
check("返回 fused_score", "fused_score" in final_inner)
check("fused_score > 0", final_inner.get("fused_score", 0) > 0)
check("返回 facial_conf", "facial_conf" in final_inner,
      f"实际 keys: {[k for k in final_inner if 'facial' in k]}")
check("facial_conf > 0", final_inner.get("facial_conf", 0) > 0)
check("返回 record_id", "record_id" in final_inner)
check("返回 stored=True", final_inner.get("stored") is True)
print()


# ========== 测试 3: 外环图编译与 invoke ==========
print("测试3: 外环图编译与 invoke")
outer = build_outer_loop()
initial_outer: OuterLoopState = {
    "target_date": datetime.now().strftime("%Y-%m-%d"),
    "student_ids": [student_id],
}
final_outer = outer.invoke(initial_outer)
check("编译图类型正确", hasattr(outer, "invoke"))
check("返回 analysis_results", "analysis_results" in final_outer)
check("analysis_results 非空", bool(final_outer.get("analysis_results")))
check("返回 alerts_generated", "alerts_generated" in final_outer)
check("alerts_generated 非空", len(final_outer.get("alerts_generated", [])) > 0)
check("返回 feedback_sent", "feedback_sent" in final_outer)
check("feedback_sent 非空", bool(final_outer.get("feedback_sent")))
print()


# ========== 测试 4: Orchestrator 内环完整状态 ==========
print("测试4: Orchestrator 内环完整状态")


async def test_orchestrator_inner():
    from backend.graph.orchestrator import Orchestrator
    orch = Orchestrator()
    result = await orch.run_inner_loop(
        student_id=student_id,
        video_path="/tmp/test_face_async.jpg",
        trigger_type="manual",
    )
    check("同时含 fused_emotion", "fused_emotion" in result)
    check("同时含 record_id", "record_id" in result)
    check("同时含 stored", "stored" in result)
    check("fused_score > 0", result.get("fused_score", 0) > 0)
    return result

asyncio.run(test_orchestrator_inner())
print()


# ========== 测试 5: Orchestrator 外环完整状态 ==========
print("测试5: Orchestrator 外环完整状态")


async def test_orchestrator_outer():
    from backend.graph.orchestrator import Orchestrator
    orch = Orchestrator()
    result = await orch.run_outer_loop(target_date=datetime.now().strftime("%Y-%m-%d"))
    check("同时含 alerts_generated", "alerts_generated" in result)
    check("同时含 feedback_sent", "feedback_sent" in result)
    check("同时含 analysis_results", "analysis_results" in result)
    check("alerts_generated 非空", len(result.get("alerts_generated", [])) > 0,
          f"实际 {len(result.get('alerts_generated', []))} 条")
    return result

asyncio.run(test_orchestrator_outer())
print()


# ========== 清理测试数据库 ==========
engine.dispose()
try:
    os.remove(TEST_DB_PATH)
    os.remove(TEST_DB_PATH + "-journal") if os.path.exists(TEST_DB_PATH + "-journal") else None
except OSError:
    pass

# ========== 结果汇总 ==========
total = pass_count + fail_count
print(f"{'='*50}")
print(f"结果: {pass_count}/{total} 通过", end="")
if fail_count > 0:
    print(f", {fail_count} 失败")
    sys.exit(1)
else:
    print(" 全部通过")
    sys.exit(0)
