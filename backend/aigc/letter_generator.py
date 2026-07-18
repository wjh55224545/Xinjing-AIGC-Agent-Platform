"""
家校沟通函生成器 (LetterGenerator)
===================================

根据学生的情绪状态和风险等级，自动生成温和、专业、易懂的家校沟通函。
特别注意措辞，在传达关注的同时避免引起家长不必要的焦虑。
"""

from __future__ import annotations
import logging
from datetime import datetime
from backend.aigc.templates.letter_templates import (
    GREEN_LETTER_TEMPLATE,
    YELLOW_LETTER_TEMPLATE,
    RED_LETTER_TEMPLATE,
)
from backend.aigc.llm_client import llm_generate as _llm_generate

logger = logging.getLogger(__name__)


class LetterGenerator:
    """家校沟通函生成器"""

    name = "家校沟通函生成"
    description = "用温和、专业、易懂的语言向家长传达学生情绪状态"

    def generate(
        self,
        student_name: str = "",
        class_name: str = "",
        emotion_summary: str = "",
        risk_level: str = "green",
        suggestions: list | None = None,
        teacher_name: str = "",
        teacher_phone: str = "",
    ) -> dict:
        """
        生成家校沟通函

        Args:
            student_name: 学生姓名
            class_name: 班级
            emotion_summary: 情绪概况
            risk_level: 风险等级
            suggestions: 建议列表
            teacher_name: 班主任姓名
            teacher_phone: 班主任电话

        Returns:
            包含沟通函内容的字典
        """
        suggs = suggestions or []
        letter_date = datetime.now().strftime("%Y-%m-%d")
        teacher = teacher_name or "班主任"
        phone = teacher_phone or "请通过学校通讯录查询"
        name = student_name or "同学"

        # ---- 优先尝试 LLM 生成 ----
        llm_text = self._try_llm_generate(name, class_name, emotion_summary, risk_level, suggs, teacher, phone)
        if llm_text:
            return {
                "letter_type": risk_level,
                "student_name": student_name,
                "class_name": class_name,
                "risk_level": risk_level,
                "letter_text": llm_text,
                "generated_by": "心镜·AIGC智能体 (moark.com Qwen3-8B)",
                "generated_at": letter_date,
                "needs_review": risk_level in ("yellow", "red"),
            }

        # ---- LLM 不可用，降级到模板模式 ----
        if risk_level == "red":
            template = RED_LETTER_TEMPLATE
            actions = self._get_actions_taken()
            home_support = self._get_home_support_suggestions(suggs)
            follow_up = self._get_follow_up_plan()
            letter_text = template.format(
                student_name=name, emotion_summary=emotion_summary or "详见心理评估报告",
                actions_taken=actions, home_support_suggestions=home_support,
                follow_up_plan=follow_up, teacher_name=teacher, teacher_phone=phone,
                date=letter_date,
            )
        elif risk_level == "yellow":
            template = YELLOW_LETTER_TEMPLATE
            attention = self._get_attention_points(suggs)
            collab = self._get_collaboration_suggestions(suggs)
            letter_text = template.format(
                student_name=name,
                emotion_summary=emotion_summary or "情绪状态总体稳定，有轻微波动",
                attention_points=attention, collaboration_suggestions=collab,
                teacher_name=teacher,
            )
        else:
            template = GREEN_LETTER_TEMPLATE
            positive = self._get_positive_findings()
            light = self._get_light_suggestions()
            letter_text = template.format(
                student_name=name,
                emotion_summary=emotion_summary or "情绪状态良好，各项指标正常",
                positive_findings=positive, light_suggestions=light,
                teacher_name=teacher,
            )

        return {
            "letter_type": risk_level,
            "student_name": student_name,
            "class_name": class_name,
            "risk_level": risk_level,
            "letter_text": letter_text,
            "generated_by": "心镜·AIGC智能体 (模板模式)",
            "generated_at": letter_date,
            "needs_review": risk_level in ("yellow", "red"),
        }

    def _try_llm_generate(
        self,
        student_name: str,
        class_name: str,
        emotion_summary: str,
        risk_level: str,
        suggestions: list,
        teacher_name: str,
        teacher_phone: str,
    ) -> str | None:
        """尝试使用 LLM 生成家校沟通函，失败返回 None。"""
        level_desc = {"green": "情绪状态良好，无需特别担心", "yellow": "情绪有轻微波动，需要适度关注", "red": "情绪状态需要紧急关注"}
        desc = level_desc.get(risk_level, "")

        suggestion_str = "\n".join(
            f"- {s.get('content', str(s))}" if isinstance(s, dict) else f"- {s}"
            for s in suggestions[:3]
        ) or "- 保持规律作息和良好沟通"

        system_prompt = (
            "你是一位经验丰富的班主任老师，需要向家长发送学生心理状态沟通函。"
            "语气必须温和、专业、不引起恐慌，同时传达必要的关注信息。"
        )

        user_prompt = f"""请为 {student_name}{class_name if class_name else ''}的家长撰写一封家校沟通函。

## 关键信息
- 情绪概况：{emotion_summary}
- 风险等级：{risk_level}（{desc}）
- 建议措施：{suggestion_str}
- 老师署名：{teacher_name}
- 联系方式：{teacher_phone}

## 写作要求
- 开头用温暖的问候语
- 如实但不夸张地描述学生情绪状态
- {"绿色等级：强调积极方面，给出轻声建议" if risk_level == "green" else ""}{"黄色等级：温和地表达关注，不要引起过度担忧" if risk_level == "yellow" else ""}{"红色等级：严肃但不慌张地说明情况，明确下一步安排" if risk_level == "red" else ""}
- 给家长2-3条可操作的家庭支持建议
- 结尾留老师联系方式，表达家校合作的诚意
- 全文温暖、专业、不引起不必要的焦虑

请用信函格式输出，以"尊敬的{student_name}家长："开头。"""

        return _llm_generate(system_prompt, user_prompt, max_tokens=1024)

    def _get_positive_findings(self) -> str:
        """绿色等级 - 积极发现"""
        return (
            "- 情绪状态整体稳定，能较好地适应学习生活\n"
            "- 日常表现出积极、开朗的情绪特征\n"
            "- 与同学互动正常，社交状态良好"
        )

    def _get_light_suggestions(self) -> str:
        """绿色等级 - 小建议"""
        return (
            "- 鼓励孩子每天分享一件开心的事\n"
            "- 保持规律的作息和适度的户外活动\n"
            "- 关注孩子的兴趣爱好，给予积极支持"
        )

    def _get_attention_points(self, suggs: list) -> str:
        """黄色等级 - 需关注方面"""
        base = "- 近期情绪有轻微波动，属于正常范围\n"
        if suggs:
            for s in suggs[:3]:
                content = s.get("content", "") if isinstance(s, dict) else str(s)
                base += f"- {content}\n"
        base += (
            "- 建议多加观察，但不必过度担心——大多数情况下适当的关注就能帮助孩子"
        )
        return base

    def _get_collaboration_suggestions(self, suggs: list) -> str:
        """黄色等级 - 协作建议"""
        return (
            "1. 每天抽出10分钟与孩子聊一聊学校生活\n"
            "2. 关注孩子的睡眠质量和饮食情况\n"
            "3. 如果发现异常变化，及时与班主任沟通\n"
            "4. 鼓励孩子参与户外活动和社交"
        )

    def _get_actions_taken(self) -> str:
        """红色等级 - 已采取措施"""
        return (
            "1. ✅ 已通知班主任密切关注学生状态\n"
            "2. ✅ 心理老师已做好准备，随时可以提供一对一咨询\n"
            "3. ✅ 心镜系统已将该生列为重点关注对象\n"
            "4. 🔄 正在建立家校联动支持机制"
        )

    def _get_home_support_suggestions(self, suggs: list) -> str:
        """红色等级 - 家庭支持建议"""
        base = (
            "1. 请尽量保持家庭氛围的稳定和温暖\n"
            "2. 每天与孩子进行15分钟以上的谈心\n"
            "3. 注意观察孩子的饮食、睡眠变化\n"
        )
        if suggs:
            for i, s in enumerate(suggs[:3], 4):
                content = s.get("content", "") if isinstance(s, dict) else str(s)
                base += f"{i}. {content}\n"
        base += (
            "\n**重要提醒**: 如果孩子出现自伤、轻生念头或其他紧急情况，"
            "请立即拨打24小时心理援助热线 010-82951332"
        )
        return base

    def _get_follow_up_plan(self) -> str:
        """红色等级 - 后续安排"""
        return (
            "- **本周内**: 心理老师将安排一对一访谈\n"
            "- **2周内**: 完成专业心理评估\n"
            "- **持续**: 心镜系统将每日跟踪情绪变化\n"
            "- **每月**: 召开家校联席会议评估进展"
        )
