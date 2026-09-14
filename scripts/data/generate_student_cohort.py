"""
学生样本数据生成脚本（合成示范数据）
====================================

用途：在无真实学生数据的阶段，为「仪表盘 / 预警面板 / 学生详情 / 情绪监测」
等页面批量生成**合成示范学生**及其情绪记录、量表记录、预警记录，
使演示时的数据更丰富、更有代表性。

设计要点：
  - 每个学生由潜在特质 θ 驱动（θ>0 症状倾向更强，θ<0 更健康）
  - 情绪记录复用合成引擎的 E1-E12 参数与情绪映射，时间上构成 7 天观测序列
  - 量表作答按 IRT 3PL 生成，等级与 θ 一致
  - 预警按风险等级生成（green / yellow / red），与风险分级口径一致
  - 全部为合成示范数据（image_path 以 seed_ 前缀标记），不冒充真实样本

用法：
  python scripts/data/generate_student_cohort.py            # 默认新增 20 名
  python scripts/data/generate_student_cohort.py --count 30 --days 7
"""

from __future__ import annotations
import argparse
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.synthetic_data import generate_scale_answers, generate_e_params

DB_PATH = ROOT / "data" / "psych.db"

SURNAMES = ["陈", "林", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "罗", "郑", "梁", "谢", "宋", "唐", "许"]
GIVEN = ["雨欣", "子涵", "浩然", "思远", "梦琪", "嘉豪", "欣怡", "俊杰", "雅婷", "志强",
         "慧敏", "天宇", "若曦", "泽宇", "诗涵", "明轩", "紫萱", "一诺", "文博", "梓萱"]

CLASSES = [
    ("计算机科学2024", "大一"), ("计算机科学2025", "大一"),
    ("电子信息2024", "大二"), ("机械工程2024", "大二"),
    ("心理学2024", "大一"), ("师范英语2024", "大一"),
]
SCHOOL = "示范中学"
SCALE_TYPES = ["SAS", "SDS", "PHQ-9", "GAD-7", "SCL-90", "PSS-10", "PANAS", "BFI-10"]

# 情绪 → (valence 范围, arousal 范围, score 范围)
EMOTION_META = {
    "开心": ((0.70, 0.95), (0.45, 0.80), (0.70, 0.90)),
    "平静": ((0.20, 0.50), (-0.30, 0.30), (0.55, 0.72)),
    "中性": ((-0.10, 0.20), (-0.20, 0.20), (0.45, 0.60)),
    "惊讶": ((0.00, 0.30), (0.55, 0.85), (0.50, 0.70)),
    "焦虑": ((-0.80, -0.45), (0.55, 0.90), (0.18, 0.40)),
    "悲伤": ((-0.90, -0.55), (-0.40, 0.10), (0.12, 0.35)),
    "愤怒": ((-0.90, -0.50), (0.50, 0.90), (0.18, 0.42)),
}

# θ → 情绪候选池（按概率加权）
EMOTION_POOLS = {
    "healthy": [("开心", 35), ("平静", 30), ("中性", 20), ("惊讶", 8), ("悲伤", 4), ("焦虑", 2), ("愤怒", 1)],
    "mild":    [("平静", 25), ("中性", 20), ("开心", 18), ("焦虑", 18), ("悲伤", 9), ("惊讶", 6), ("愤怒", 4)],
    "moderate": [("焦虑", 30), ("悲伤", 20), ("愤怒", 15), ("中性", 12), ("平静", 10), ("惊讶", 8), ("开心", 5)],
    "severe":  [("焦虑", 35), ("悲伤", 25), ("愤怒", 20), ("中性", 8), ("惊讶", 6), ("平静", 4), ("开心", 2)],
}


def level_of_theta(theta: float) -> str:
    if theta < 0:
        return "normal"
    if theta < 0.8:
        return "mild"
    if theta < 1.6:
        return "moderate"
    return "severe"


def pool_of_level(level: str) -> str:
    return {"normal": "healthy", "mild": "mild", "moderate": "moderate", "severe": "severe"}[level]


def pick_emotion(level: str, rng: random.Random) -> str:
    pool = EMOTION_POOLS[pool_of_level(level)]
    names = [n for n, _ in pool]
    weights = [w for _, w in pool]
    return rng.choices(names, weights=weights, k=1)[0]


def build_records(student_id: int, code: str, theta: float, level: str,
                  days: int, per_day: int, rng: random.Random) -> list[tuple]:
    """构造 7 天情绪记录，返回按 emotion_records 列顺序的元组。"""
    e_base = generate_e_params(theta, rng)
    records = []
    start = datetime(2026, 9, 7)
    for d in range(days):
        day = start + timedelta(days=d)
        for i in range(per_day):
            hour = rng.randint(8, 17)
            minute = rng.randint(0, 59)
            ts = day.replace(hour=hour, minute=minute, second=0)
            emotion = pick_emotion(level, rng)
            v_range, a_range, s_range = EMOTION_META[emotion]
            valence = round(rng.uniform(*v_range), 3)
            arousal = round(rng.uniform(*a_range), 3)
            score = round(rng.uniform(*s_range), 3)
            k_val = round(max(0.0, min(1.0, theta * 0.35 + rng.uniform(-0.08, 0.08))), 3)
            if theta <= 0:
                k_val = round(max(0.0, min(0.25, k_val)), 3)
            records.append((
                student_id,
                f"seed_{code}_d{d+1}_{ts.strftime('%H%M')}.mp4",
                emotion, round(rng.uniform(0.72, 0.95), 3), valence, arousal,
                round(rng.uniform(-0.3, 0.9), 3), round(rng.uniform(-0.3, 0.9), 3),
                round(rng.uniform(0.75, 0.95), 3), round(rng.uniform(0.3, 0.9), 3),
                round(e_base["aggression"] + rng.uniform(-3, 3), 2),
                round(e_base["stress"] + rng.uniform(-3, 3), 2),
                round(e_base["tension"] + rng.uniform(-3, 3), 2),
                round(e_base["suspicious"] + rng.uniform(-3, 3), 2),
                round(e_base["balance"] + rng.uniform(-3, 3), 2),
                round(e_base["charm"] + rng.uniform(-3, 3), 2),
                round(e_base["energy"] + rng.uniform(-3, 3), 2),
                round(e_base["self_regulation"] + rng.uniform(-3, 3), 2),
                round(e_base["inhibition"] + rng.uniform(-3, 3), 2),
                round(e_base["neuroticism"] + rng.uniform(-3, 3), 2),
                round(e_base["depression"] + rng.uniform(-3, 3), 2),
                round(e_base["happiness"] + rng.uniform(-3, 3), 2),
                round((e_base["balance"] + e_base["self_regulation"]) / 2 + rng.uniform(-3, 3), 2),
                k_val,
                "合成K值（示范）",
                rng.randint(60, 120),
                round(rng.uniform(2.0, 6.0), 1),
                emotion, score, valence, arousal,
                round(rng.uniform(0.02, 0.10), 3),
                0,
                round(rng.uniform(0.82, 0.97), 2),
                0,
                ts.isoformat(timespec="seconds"),
            ))
    return records


def build_scale(student_id: int, theta: float, rng: random.Random,
                scale_defs: dict) -> list[tuple]:
    """为部分学生生成 1-2 条量表记录。"""
    rows = []
    n_scales = 1 if rng.random() < 0.55 else 2
    chosen = rng.sample(SCALE_TYPES, n_scales)
    level = level_of_theta(theta)
    level_cn = {"normal": "normal", "mild": "mild", "moderate": "moderate", "severe": "severe"}[level]
    std_map = {"normal": rng.uniform(38, 48), "mild": rng.uniform(52, 60),
               "moderate": rng.uniform(62, 70), "severe": rng.uniform(72, 84)}
    for st in chosen:
        scale_def = scale_defs.get(st)
        answers = []
        if scale_def:
            answers = generate_scale_answers(scale_def, theta, rng)
        raw = round(sum(answers) if answers else rng.uniform(25, 60), 1)
        std = round(std_map[level], 1)
        rows.append((student_id, st, raw, std, level, "{}", str(answers),
                     datetime(2026, 9, 8 + rng.randint(0, 5)).isoformat(timespec="seconds")))
    return rows


def build_alert(student_id: str, name: str, theta: float, rng: random.Random,
                now: str) -> tuple | None:
    """按风险等级生成预警；θ<0.3 的学生给绿色提示，θ≥1.6 给红色预警。"""
    if theta < -0.2:
        return (student_id, "green", "近期情绪状态稳定，各项指标正常，保持良好状态",
                "green", "近期情绪状态稳定，各项指标正常，保持良好状态",
                round(rng.uniform(0.75, 0.9), 2), "看板,APP",
                f"[GREEN] {name}: 近期情绪状态稳定，各项指标正常，保持良好状态",
                '["看板", "APP"]', None, "pending", None, 0, None, None, now, now)
    if theta >= 1.6:
        return (student_id, "red", "负面情绪占比高，量表提示中度以上风险，建议尽快联系心理辅导老师",
                "red", "负面情绪占比高，量表提示中度以上风险，建议尽快联系心理辅导老师",
                round(rng.uniform(0.2, 0.4), 2), "看板,APP,微信(班主任),电话(家长)",
                f"[RED] {name}: 负面情绪占比高，量表提示中度以上风险，建议尽快联系心理辅导老师",
                '["看板", "APP", "微信(班主任)", "电话(家长)"]', None, "pending", None, 0, None, None, now, now)
    if theta >= 0.5:
        return (student_id, "yellow", "情绪存在轻度波动，负面情绪占比略高，建议适度关注",
                "yellow", "情绪存在轻度波动，负面情绪占比略高，建议适度关注",
                round(rng.uniform(0.5, 0.68), 2), "看板,APP,微信(班主任)",
                f"[YELLOW] {name}: 情绪存在轻度波动，负面情绪占比略高，建议适度关注",
                '["看板", "APP", "微信(班主任)"]', None, "pending", None, 0, None, None, now, now)
    return None


def load_scale_defs() -> dict:
    defs = {}
    for p in (ROOT / "data" / "scales").glob("*.json"):
        import json
        try:
            with open(p, encoding="utf-8") as f:
                defs[p.stem] = json.load(f)
        except Exception:
            pass
    return defs


def main() -> None:
    ap = argparse.ArgumentParser(description="生成合成示范学生数据")
    ap.add_argument("--count", type=int, default=20, help="新增学生数（默认20）")
    ap.add_argument("--days", type=int, default=7, help="每人情绪观测天数（默认7）")
    ap.add_argument("--per-day", type=int, default=3, help="每天记录条数（默认3）")
    ap.add_argument("--force", action="store_true", help="即使已有较多学生也强制追加")
    args = ap.parse_args()

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    existing = cur.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    if existing >= 25 and not args.force:
        print(f"已有 {existing} 名学生，跳过生成（如需追加请加 --force）。")
        db.close()
        return

    scale_defs = load_scale_defs()
    rng = random.Random(2026)
    now = datetime.now().isoformat(timespec="milliseconds")

    # θ 分布：健康 40% / 轻度 30% / 中度 20% / 重度 10%
    thetas = []
    for _ in range(args.count):
        r = rng.random()
        if r < 0.40:
            thetas.append(round(rng.uniform(-1.6, -0.2), 2))
        elif r < 0.70:
            thetas.append(round(rng.uniform(0.2, 0.75), 2))
        elif r < 0.90:
            thetas.append(round(rng.uniform(0.8, 1.5), 2))
        else:
            thetas.append(round(rng.uniform(1.6, 2.3), 2))
    rng.shuffle(thetas)

    n_student = 0
    n_records = 0
    n_scales = 0
    n_alerts = 0
    existing_codes = {r[0] for r in cur.execute("SELECT student_code FROM students").fetchall()}

    for idx, theta in enumerate(thetas):
        surname = SURNAMES[idx % len(SURNAMES)]
        given = GIVEN[(idx * 7 + 3) % len(GIVEN)]
        name = surname + given
        cls_name, grade = CLASSES[idx % len(CLASSES)]
        code = f"2024-DEMO-{idx + 1:03d}"
        while code in existing_codes:
            code = f"2024-DEMO-{idx + 1:03d}-{rng.randint(10, 99)}"
        existing_codes.add(code)
        baseline = round(max(0.1, min(0.95, 0.78 - theta * 0.22 + rng.uniform(-0.05, 0.05))), 2)
        level = level_of_theta(theta)

        cur.execute(
            "INSERT INTO students (name, class_name, student_code, baseline_mood, created_at, school, grade, teacher_name, parent_phone, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, '', '', 1)",
            (name, cls_name, code, baseline, now, SCHOOL, grade),
        )
        sid = cur.lastrowid
        n_student += 1

        for rec in build_records(sid, code, theta, level, args.days, args.per_day, rng):
            cur.execute(
                "INSERT INTO emotion_records (student_id, image_path, facial_emotion, facial_conf, facial_valence, facial_arousal, "
                "vestibular_valence, vestibular_arousal, vestibular_confidence, vestibular_intensity, "
                "vi_aggression, vi_stress, vi_tension, vi_suspect, vi_balance, vi_charm, vi_energy, vi_self_regulation, "
                "vi_inhibition, vi_neuroticism, vi_depression, vi_happiness, vi_stability, vi_K_value, vi_K_interpretation, "
                "vi_n_windows, vi_duration_sec, fused_emotion, fused_score, fused_valence, fused_arousal, "
                "confidence_diff, requires_review, estimated_accuracy, is_manual, recorded_at) "
                "VALUES (" + ",".join(["?"] * 36) + ")",
                rec,
            )
            n_records += 1

        for srow in build_scale(sid, theta, rng, scale_defs):
            cur.execute(
                "INSERT INTO scale_results (student_id, scale_type, raw_score, standard_score, level, dimension_scores, answers, submitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                srow,
            )
            n_scales += 1

        alert = build_alert(sid, name, theta, rng, now)
        if alert:
            cur.execute(
                "INSERT INTO alerts (student_id, severity, alert_reason, risk_level, risk_reason, overall_score, feedback_channel, "
                "feedback_content, sent_channels, work_order_id, work_order_status, due_time, is_acknowledged, acknowledged_by, "
                "acknowledged_at, triggered_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                alert,
            )
            n_alerts += 1

    db.commit()
    total_students = cur.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_records = cur.execute("SELECT COUNT(*) FROM emotion_records").fetchone()[0]
    total_alerts = cur.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    total_scales = cur.execute("SELECT COUNT(*) FROM scale_results").fetchone()[0]
    db.close()
    print(f"✅ 新增 {n_student} 名合成学生、{n_records} 条情绪记录、{n_scales} 条量表记录、{n_alerts} 条预警。")
    print(f"   当前库内：学生 {total_students} 名 / 情绪记录 {total_records} 条 / 量表 {total_scales} 条 / 预警 {total_alerts} 条。")
    print("   （全部为合成示范数据，image_path 以 seed_ 前缀标记，不冒充真实样本。）")


if __name__ == "__main__":
    main()
