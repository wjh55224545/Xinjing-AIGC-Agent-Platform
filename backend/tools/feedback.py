"""
多渠道反馈工具 (MultiChannelFeedbackTool)
==========================================

功能说明：
- 根据风险等级动态选择反馈渠道
- 绿色状态：推送至学生个人APP
- 黄色状态：同时通知学生与班主任
- 红色状态：触发紧急流程，自动通知心理教师与家长

通知渠道：
- 看板（Dashboard）：系统预警面板展示
- APP（移动应用）：学生端APP推送
- 微信（WeChat）：企业微信/公众号模板消息
- 短信（SMS）：运营商短信通道
- 邮件（Email）：学校邮箱系统
- 紧急电话（Emergency Call）：自动外呼

触发流程：
绿色 → 看板
黄色 → 看板 + APP + 微信(班主任)
红色 → 看板 + APP + 微信(班主任) + 邮件 + 短信 + 紧急工单
"""

from __future__ import annotations
import random
import hashlib
from datetime import datetime
from typing import Optional, List
from backend.tools.base import BaseTool, ToolResult


# 渠道配置
CHANNELS = {
    "dashboard": {
        "name": "看板",
        "enabled": True,
        "delay": 0,
        "priority": "low",
    },
    "app": {
        "name": "学生APP",
        "enabled": True,
        "delay": 1,
        "priority": "medium",
    },
    "wechat_teacher": {
        "name": "微信(班主任)",
        "enabled": True,
        "delay": 2,
        "priority": "medium",
    },
    "wechat_parent": {
        "name": "微信(家长)",
        "enabled": True,
        "delay": 2,
        "priority": "high",
    },
    "sms_parent": {
        "name": "短信(家长)",
        "enabled": True,
        "delay": 3,
        "priority": "high",
    },
    "email_psychologist": {
        "name": "邮件(心理教师)",
        "enabled": True,
        "delay": 2,
        "priority": "high",
    },
    "phone_emergency": {
        "name": "紧急电话",
        "enabled": True,
        "delay": 5,
        "priority": "critical",
    },
}

# 风险等级对应的渠道策略
CHANNEL_STRATEGY = {
    "green": ["dashboard", "app"],
    "yellow": ["dashboard", "app", "wechat_teacher"],
    "red": [
        "dashboard", "app", "wechat_teacher",
        "wechat_parent", "sms_parent",
        "email_psychologist", "phone_emergency"
    ],
}

# 通知模板
NOTIFICATION_TEMPLATES = {
    "green": {
        "title": "🌿 心理健康状态良好",
        "content": "{student_name}同学今日情绪状态稳定，继续保持哦！",
        "dashboard": "学生 {student_name} 今日心理健康状态良好，综合评分 {score}。",
    },
    "yellow": {
        "title": "⚠️ 需要关注",
        "content": "{student_name}同学近期情绪有些波动，建议多加留意。详情请查看系统。",
        "dashboard": "【关注】学生 {student_name} 心理健康状态需要关注。风险因素：{risk_reasons}。建议：{suggestions}。",
        "wechat_teacher": "【心理健康预警】{student_name} 同学近期情绪状态需要关注。班级：{class_name}。请班主任留意并适当关怀。",
    },
    "red": {
        "title": "🚨 紧急预警",
        "content": "{student_name}同学情绪状态异常，需要立即关注！",
        "dashboard": "【紧急】学生 {student_name} 心理健康状态异常！综合评分 {score}。风险因素：{risk_reasons}。需立即启动干预流程。",
        "wechat_teacher": "【紧急预警】{student_name} 同学情绪状态异常，请立即联系学生并了解情况。风险因素：{risk_reasons}",
        "wechat_parent": "【心理健康预警】{student_name} 家长您好，您的孩子近期情绪状态需要关注。学校心理老师将尽快与您联系了解情况。如有紧急情况，请拨打学校心理热线。",
        "sms_parent": "【心镜智能】{student_name}家长，您的孩子近期情绪状态需要关注。学校心理教师将尽快与您联系。",
        "email_psychologist": "【紧急工单】学生 {student_name}（学号：{student_code}，班级：{class_name}）心理健康状态异常，需安排一对一访谈。综合评分：{score}。风险因素：{risk_reasons}。建议：{suggestions}",
    },
}


class MultiChannelFeedbackTool(BaseTool):
    """多渠道反馈工具"""

    name = "多渠道反馈"
    description = (
        "根据预警等级通过看板、APP、微信、邮件、短信等多渠道发送分级反馈通知。"
        "绿色→APP；黄色→APP+班主任；红色→APP+班主任+心理教师+家长，触发紧急干预流程。"
    )

    def __init__(self):
        super().__init__()
        self._send_count = 0

    def execute(
        self,
        alert_id: int = 0,
        severity: str = "green",
        student_name: str = "",
        content: str = "",
        student_info: dict | None = None,
        analysis_result: dict | None = None,
        **kwargs
    ) -> ToolResult:
        """
        执行多渠道反馈

        Args:
            alert_id: 预警ID
            severity: 风险等级 (green/yellow/red)
            student_name: 学生姓名
            content: 预警内容
            student_info: 学生详细信息 {student_code, class_name, school}
            analysis_result: 分析结果数据
        """
        self._send_count += 1

        try:
            # 步骤1: 确定发送渠道
            channels_to_send = CHANNEL_STRATEGY.get(severity, CHANNEL_STRATEGY["green"])

            # 步骤2: 获取通知模板
            templates = NOTIFICATION_TEMPLATES.get(severity, NOTIFICATION_TEMPLATES["green"])

            # 步骤3: 构建通知内容
            notification_data = self._build_notification_content(
                student_name, severity, content, student_info, analysis_result, templates
            )

            # 步骤4: 分渠道发送
            send_results = {}
            for channel in channels_to_send:
                result = self._send_to_channel(
                    channel, alert_id, notification_data, severity
                )
                send_results[channel] = result

            # 步骤5: 生成预警工单（红色级别）
            work_order = None
            if severity == "red":
                work_order = self._create_emergency_work_order(
                    alert_id, student_name, student_info, analysis_result, send_results
                )

            # 统计发送结果
            success_count = sum(1 for r in send_results.values() if r["success"])
            total_count = len(send_results)

            return ToolResult(
                success=True,
                data={
                    # 发送状态摘要
                    "sent_channels": [CHANNELS[c]["name"] for c in channels_to_send],
                    "channel_count": total_count,
                    "success_count": success_count,
                    "failure_count": total_count - success_count,
                    "success_rate": round(success_count / total_count, 2) if total_count > 0 else 0,

                    # 各渠道详细结果
                    "channel_results": send_results,

                    # 预警工单（红色级别）
                    "work_order": work_order,

                    # 通知内容
                    "notification_content": notification_data,

                    # 元数据
                    "alert_id": alert_id,
                    "severity": severity,
                    "student_name": student_name,
                    "send_timestamp": datetime.now().isoformat(),
                    "message_id": f"msg-{hashlib.md5(f'{alert_id}{self._send_count}'.encode()).hexdigest()[:12]}",
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"多渠道反馈发送失败: {str(e)}"
            )

    def _build_notification_content(
        self,
        student_name: str,
        severity: str,
        content: str,
        student_info: dict | None,
        analysis_result: dict | None,
        templates: dict
    ) -> dict:
        """构建各渠道的通知内容"""
        info = student_info or {}
        analysis = analysis_result or {}

        # 提取风险因素和建议
        risk_factors = analysis.get("risk_factors", [])
        risk_reasons = "；".join(risk_factors) if risk_factors else content

        suggestions = analysis.get("suggestions", [])
        if suggestions and isinstance(suggestions[0], dict):
            suggestion_texts = [s.get("content", "") for s in suggestions[:2]]
            suggestion_text = "；".join(suggestion_texts)
        else:
            suggestion_text = str(suggestions[0]) if suggestions else "建议持续关注"

        # 构建格式化数据
        format_data = {
            "student_name": student_name,
            "class_name": info.get("class_name", "未知班级"),
            "student_code": info.get("student_code", "未知学号"),
            "school": info.get("school", ""),
            "score": str(analysis.get("overall_score", analysis.get("attention_score", 0))),
            "risk_reasons": risk_reasons,
            "suggestions": suggestion_text,
            "content": content,
        }

        # 生成各渠道内容
        contents = {}
        for key, template in templates.items():
            if isinstance(template, str):
                try:
                    contents[key] = template.format(**format_data)
                except KeyError:
                    contents[key] = template

        return {
            "title": contents.get("title", templates.get("title", "")),
            "content": contents.get("content", ""),
            "dashboard": contents.get("dashboard", ""),
            "wechat_teacher": contents.get("wechat_teacher", ""),
            "wechat_parent": contents.get("wechat_parent", ""),
            "sms_parent": contents.get("sms_parent", ""),
            "email_psychologist": contents.get("email_psychologist", ""),
            "formatted_data": format_data,
        }

    def _send_to_channel(
        self,
        channel: str,
        alert_id: int,
        notification_data: dict,
        severity: str
    ) -> dict:
        """
        模拟向指定渠道发送通知
        真实实现应调用各渠道的SDK/API
        """
        channel_info = CHANNELS.get(channel, {})
        channel_name = channel_info.get("name", channel)

        # 模拟发送延迟
        import time
        time.sleep(0.05 * channel_info.get("delay", 0))

        # 模拟发送结果
        success = random.random() > 0.05  # 95%成功率

        result = {
            "success": success,
            "channel": channel,
            "channel_name": channel_name,
            "priority": channel_info.get("priority", "low"),
            "sent_at": datetime.now().isoformat(),
            "message_id": f"{channel}-{hashlib.md5(f'{alert_id}{channel}'.encode()).hexdigest()[:8]}",
        }

        if success:
            result["delivery_status"] = "delivered"
            result["read_status"] = "unread"
        else:
            result["delivery_status"] = "failed"
            result["error_message"] = "通道暂时不可用"
            result["retry_recommended"] = True

        # 特定渠道的附加信息
        if channel == "app":
            result["device_type"] = random.choice(["iOS", "Android"])
            result["push_id"] = f"push-{random.randint(100000, 999999)}"
        elif channel == "sms_parent":
            result["phone_number"] = "138****8888"  # 脱敏
            result["sms_signature"] = "【心镜智能】"
        elif channel == "email_psychologist":
            result["email_address"] = "psych@school.edu.cn"
            result["subject"] = f"[{severity.upper()}] 学生心理预警通知 - {notification_data['formatted_data']['student_name']}"
        elif channel == "phone_emergency":
            result["call_status"] = random.choice(["dialing", "answered", "missed"])
            result["call_duration"] = random.randint(0, 120) if result["call_status"] == "answered" else 0

        return result

    def _create_emergency_work_order(
        self,
        alert_id: int,
        student_name: str,
        student_info: dict | None,
        analysis_result: dict | None,
        send_results: dict
    ) -> dict:
        """
        创建紧急干预工单
        真实实现应接入学校工单系统或OA系统
        """
        info = student_info or {}
        analysis = analysis_result or {}

        # 生成工单号
        work_order_id = f"WO-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(f'{alert_id}'.encode()).hexdigest()[:6].upper()}"

        # 统计各渠道发送结果
        channel_summary = []
        for channel, result in send_results.items():
            channel_summary.append({
                "channel": CHANNELS.get(channel, {}).get("name", channel),
                "status": result.get("delivery_status", "unknown"),
            })

        return {
            "work_order_id": work_order_id,
            "alert_id": alert_id,
            "student_name": student_name,
            "student_code": info.get("student_code", ""),
            "class_name": info.get("class_name", ""),
            "priority": "P0",  # 最高优先级
            "status": "pending",  # pending -> processing -> resolved
            "assigned_to": "心理教师组",
            "due_time": (datetime.now() + timedelta(hours=24)).isoformat(),
            "description": f"学生{student_name}情绪状态异常，综合评分{analysis.get('overall_score', 0):.2f}，需安排一对一访谈。",
            "risk_level": "red",
            "risk_factors": analysis.get("risk_factors", []),
            "suggestions": [s.get("content", "") if isinstance(s, dict) else str(s)
                           for s in analysis.get("suggestions", [])],
            "channel_summary": channel_summary,
            "created_at": datetime.now().isoformat(),
            "creator": "心镜智能体",
            "work_order_type": "psychological_intervention",
            "follow_up_required": True,
            "escalation_enabled": True,
        }

    def query_notification_status(
        self,
        message_ids: List[str]
    ) -> ToolResult:
        """
        查询通知送达状态
        """
        status_results = []
        for msg_id in message_ids:
            status_results.append({
                "message_id": msg_id,
                "status": random.choice(["delivered", "read", "failed"]),
                "delivered_at": datetime.now().isoformat() if random.random() > 0.1 else None,
                "read_at": datetime.now().isoformat() if random.random() > 0.5 else None,
            })

        return ToolResult(
            success=True,
            data={
                "query_count": len(message_ids),
                "results": status_results,
                "query_time": datetime.now().isoformat(),
            },
        )


# 辅助函数
def timedelta(**kwargs):
    """简单的timedelta替代"""
    from datetime import timedelta as td
    return td(**kwargs)
