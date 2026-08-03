"""
自进化引擎 — 经验积累与反馈驱动优化
====================================

核心思路：
- 每次 AIGC 内容生成后，记录（数据摘要, 生成结果, 用户评分）
- Agent 生成时从经验库检索相似历史成功案例，注入 prompt
- 用户反馈（已有的 /api/admin/feedback）自动关联为评分信号

不依赖外部框架，仅用 JSONL 文件 + prompt 注入实现"从反馈中进化"。
"""

from __future__ import annotations
import os
import json
import time
import logging
import random
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)

EVOLUTION_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(EVOLUTION_DIR, exist_ok=True)
EXPERIENCE_PATH = os.path.join(EVOLUTION_DIR, "experience.jsonl")


# ========================
# 记录经验
# ========================

def record_experience(
    category: str,          # daily_report / intervention_plan / parent_letter / growth_narrative
    student_name: str,
    outcome: str,           # 生成内容的前 200 字摘要
    rating: Optional[int] = None,  # 用户评分 1-5
    feedback: Optional[str] = None,
) -> Optional[int]:
    """
    将一次 AIGC 生成经验记录到 JSONL 文件。
    返回本次经验 ID（行号）。
    """
    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "student_name": student_name,
            "outcome_preview": outcome[:200] if outcome else "",
            "rating": rating,
            "feedback": feedback[:300] if feedback else None,
        }
        with open(EXPERIENCE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 返回行号作为 ID
        with open(EXPERIENCE_PATH, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return None


# ========================
# 检索经验
# ========================

def retrieve_experience(
    category: Optional[str] = None,
    min_rating: int = 4,
    limit: int = 3,
) -> List[dict]:
    """
    从经验库中检索高质量历史案例，用于注入 Agent prompt。

    Args:
        category: 按类别筛选（None 为全检）
        min_rating: 最低评分阈值（默认 4 分以上）
        limit: 最多返回条数

    Returns:
        经验条目列表，按时间倒序
    """
    if not os.path.exists(EXPERIENCE_PATH):
        return []

    candidates = []
    try:
        with open(EXPERIENCE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if category and entry.get("category") != category:
                        continue
                    r = entry.get("rating")
                    if r is not None and r < min_rating:
                        continue
                    candidates.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    # 按时间倒序，取 limit 条
    candidates.reverse()
    if len(candidates) > limit:
        candidates = random.sample(candidates, limit)
    return candidates


# ========================
# 进化统计
# ========================

def get_evolution_stats() -> dict:
    """
    获取自进化统计指标。

    Returns:
        {
            "total_experiences": 累积经验总数,
            "avg_rating": 平均用户评分,
            "rating_trend": 最近10次评分的趋势（上升/下降/持平）,
            "top_categories": 各类别的经验数量,
            "recent_insights": 最近的高评分经验摘要,
        }
    """
    if not os.path.exists(EXPERIENCE_PATH):
        return {
            "total_experiences": 0,
            "avg_rating": 0,
            "rating_trend": "数据不足",
            "top_categories": {},
            "recent_insights": [],
        }

    entries = []
    ratings = []
    categories = {}

    try:
        with open(EXPERIENCE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    entries.append(e)
                    cat = e.get("category", "other")
                    categories[cat] = categories.get(cat, 0) + 1
                    r = e.get("rating")
                    if r is not None:
                        ratings.append(r)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    # 平均评分
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

    # 趋势：最近 vs 更早
    if len(ratings) >= 10:
        recent_avg = sum(ratings[-5:]) / 5
        older_avg = sum(ratings[-10:-5]) / 5
        diff = recent_avg - older_avg
        if diff > 0.3:
            trend = "上升"
        elif diff < -0.3:
            trend = "下降"
        else:
            trend = "持平"
    else:
        trend = "数据不足"

    # 最近高评分摘要
    entries_with_rating = [e for e in entries if e.get("rating") is not None]
    entries_with_rating.sort(key=lambda e: e["rating"], reverse=True)
    recent_insights = [
        {
            "timestamp": e.get("timestamp", "")[:10],
            "category": e.get("category"),
            "rating": e.get("rating"),
            "student_name": e.get("student_name"),
        }
        for e in entries_with_rating[:5]
    ]

    return {
        "total_experiences": len(entries),
        "avg_rating": avg_rating,
        "rating_trend": trend,
        "top_categories": categories,
        "recent_insights": recent_insights,
    }


# ========================
# 进化 prompt 注入
# ========================

def build_evolution_context(category: str) -> str:
    """
    为 AIGC 生成构造进化上下文。
    从经验库检索高质量案例，拼接到 system prompt 中。

    无经验时返回空字符串。
    """
    experiences = retrieve_experience(category=category, min_rating=4, limit=2)
    if not experiences:
        return ""

    lines = ["\n## 历史成功案例参考（系统从反馈中自动学习）"]
    for i, exp in enumerate(experiences, 1):
        lines.append(
            f"{i}. 对象: {exp.get('student_name', '未知')} | "
            f"评分: {exp.get('rating', '?')}/5\n"
            f"   生成效果: {exp.get('outcome_preview', '暂无详情')[:120]}"
        )

    lines.append("\n请参考以上案例的风格和深度，为当前学生生成同样高质量的内容。")
    return "\n".join(lines)
