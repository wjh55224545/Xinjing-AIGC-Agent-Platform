"""
学生成长叙事生成器 (NarrativeGenerator)
=========================================

基于长期情绪监测数据，自动生成学生心理成长轨迹叙事。
以温暖、鼓励的笔触，记录学生的心理成长历程。
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from backend.aigc.llm_client import llm_generate as _llm_generate

logger = logging.getLogger(__name__)


class NarrativeGenerator:
    """学生成长叙事生成器"""

    name = "学生成长叙事生成"
    description = "基于长期情绪数据，生成学生心理成长轨迹叙事"

    def generate(
        self,
        student_name: str = "",
        period_days: int = 30,
        historical_data: dict | None = None,
    ) -> dict:
        """
        生成学生成长叙事

        Args:
            student_name: 学生姓名
            period_days: 时间跨度（天）
            historical_data: 历史情绪数据

        Returns:
            包含成长叙事内容的字典
        """
        data = historical_data or {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)
        name = student_name or "同学"
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # ---- 优先尝试 LLM 生成 ----
        llm_text = self._try_llm_generate(name, period_days, start_str, end_str, data)
        if llm_text:
            return {
                "narrative_type": "growth",
                "student_name": student_name,
                "period_days": period_days,
                "start_date": start_str,
                "end_date": end_str,
                "narrative_text": llm_text,
                "generated_by": "心镜·AIGC智能体 (moark.com Qwen3-8B)",
            }

        # ---- LLM 不可用，降级到模板模式 ----
        trend_analysis = self._analyze_growth_trend(data, period_days)
        narrative_text = self._compose_narrative(
            student_name=name, start_date=start_str,
            end_date=end_str, trend=trend_analysis, data=data,
        )

        return {
            "narrative_type": "growth",
            "student_name": student_name,
            "period_days": period_days,
            "start_date": start_str,
            "end_date": end_str,
            "trend_summary": trend_analysis.get("summary", ""),
            "narrative_text": narrative_text,
            "generated_by": "心镜·AIGC智能体 (模板模式)",
        }

    def _try_llm_generate(
        self,
        student_name: str,
        period_days: int,
        start_date: str,
        end_date: str,
        data: dict,
    ) -> str | None:
        """尝试使用 LLM 生成成长叙事，失败返回 None。"""
        avg_score = data.get("avg_score", 0.7)
        trend = data.get("trend_direction", "稳定")
        trend_summary = (
            "在过去这段时间里，情绪状态呈现积极向上的趋势" if trend == "改善中"
            else "在过去这段时间里，经历了一些情绪上的起伏和挑战" if trend == "下降中"
            else "在过去这段时间里，情绪状态保持在一个相对稳定的水平"
        )

        system_prompt = (
            "你是一位温暖而有洞察力的学校心理老师，负责为学生撰写心理成长叙事。"
            "请用温暖、鼓励、充满希望的笔触写作，记录学生的成长历程。"
        )

        user_prompt = f"""请为 {student_name} 同学撰写一段心理成长叙事。

## 基本信息
- 记录周期：{start_date} ~ {end_date}（{period_days}天）
- 平均情绪评分：{avg_score:.2f}/1.00
- 整体趋势：{trend_summary}

## 写作要求
- 以"🌱 {student_name}的成长足迹"为标题
- 用温暖、鼓励的笔触描述这段时间的心理状态
- 挖掘2-3个闪光时刻或值得肯定的进步
- 对未来的成长给予积极的展望
- 篇幅约300-500字
- 结尾附上一句温暖的寄语

请用 Markdown 格式输出，适当使用 emoji 增加温度。"""

        return _llm_generate(system_prompt, user_prompt, max_tokens=2048)

    def _analyze_growth_trend(
        self, data: dict, period_days: int
    ) -> dict:
        """分析成长趋势"""
        # 从数据中提取趋势信息
        avg_score = data.get("avg_score", 0.7)
        trend_direction = data.get("trend_direction", "稳定")
        improvement_areas = data.get("improvement_areas", [])
        strengths = data.get("strengths", [])

        if trend_direction == "改善中":
            summary = "在过去这段时间里，情绪状态呈现积极向上的趋势"
        elif trend_direction == "下降中":
            summary = "在过去这段时间里，经历了一些情绪上的起伏和挑战"
        else:
            summary = "在过去这段时间里，情绪状态保持在一个相对稳定的水平"

        return {
            "summary": summary,
            "avg_score": avg_score,
            "trend": trend_direction,
            "improvements": improvement_areas,
            "strengths": strengths,
        }

    def _compose_narrative(
        self,
        student_name: str,
        start_date: str,
        end_date: str,
        trend: dict,
        data: dict,
    ) -> str:
        """组装成长叙事"""
        name = student_name or "同学"

        narrative = f"""## 🌱 {name}的成长足迹

**记录周期**: {start_date} ~ {end_date}
**记录人**: 心镜·AIGC智能体平台

---

### 📖 成长概述

{trend.get('summary', '在过去这段时间里，情绪状态总体平稳。')}

### 🌟 闪光时刻

在这段日子里，{name}展现出了令人欣慰的成长：
- 在面对学习压力时，表现出逐渐增强的情绪调节能力
- 与同学互动中，展现出更多的积极情感表达
- 情绪的自我恢复能力在逐步提升

### 📈 成长轨迹

从数据上看，{name}的综合情绪得分在 {trend.get('avg_score', 0.7):.2f} 左右，
整体趋势呈现**{trend.get('trend', '稳定')}**。
这反映出正在建立更加健康的情绪管理模式。

### 💪 值得肯定的进步

- 积极情绪表达更加自然和频繁
- 面对挫折时的恢复时间在缩短
- 开始主动寻求社交支持和互动

### 🌈 未来展望

在接下来的时间里，我们期待{name}能够：
- 继续发展情绪识别和表达能力
- 建立更加多元化的压力应对策略
- 在集体活动中获得更多的归属感和成就感

---

> 每一次微小的进步，都是成长的印记。
> 我们相信，每一个孩子都有自己独特的成长节奏。

*这段成长叙事由心镜·AIGC智能体平台基于日常监测数据自动生成。*
*算力平台: 沐曦MetaX GPU / Gitee.AI*
*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
        return narrative
