"""
协调智能体 (OrchestratorAgent)
==============================

多智能体系统的总调度器。负责协调感知→分析→报告→预警的完整工作流，
管理智能体间的消息传递、任务分配和结果汇总。

这是多智能体协作系统的调度核心，实现真正的多Agent协作。
"""

from __future__ import annotations
import asyncio
import uuid
import logging
from datetime import datetime
from typing import AsyncIterator

from backend.agents.base_agent import BaseAgent
from backend.agents.perception_agent import PerceptionAgent
from backend.agents.analysis_agent import AnalysisAgent
from backend.agents.report_agent import ReportAgent
from backend.agents.alert_agent import AlertAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    协调智能体 — 多智能体协作的总调度器

    工作流程:
    1. 触发感知智能体 → 情绪识别
    2. 触发分析智能体 → 心理健康分析
    3. 触发报告智能体 → AIGC内容生成
    4. 触发预警智能体 → 分级预警与反馈

    特性:
    - 支持同步和流式两种执行模式
    - 每个智能体运行在国产算力平台上
    - 支持SSE事件推送，前端实时观看协作过程
    """

    name = "协调智能体"
    description = (
        "多智能体系统的总调度器。协调感知→分析→报告→预警的完整工作流，"
        "管理智能体间的消息传递、任务分配和结果汇总。"
    )

    def __init__(self, streaming: bool = True, platform: str | None = None):
        self.streaming = streaming
        self.platform = platform
        self._queues: dict[str, asyncio.Queue] = {}
        self._results: dict[str, dict] = {}

        # 初始化智能体
        self.perception = PerceptionAgent(streaming=streaming, platform=platform)
        self.analysis = AnalysisAgent(streaming=streaming, platform=platform)
        self.report = ReportAgent(streaming=streaming, platform=platform)
        self.alert = AlertAgent(streaming=streaming, platform=platform)

        logger.info(
            f"协调智能体初始化完成: "
            f"感知={self.perception.name}, "
            f"分析={self.analysis.name}, "
            f"报告={self.report.name}, "
            f"预警={self.alert.name}"
        )

    def get_queue(self, run_id: str) -> asyncio.Queue:
        """获取或创建SSE事件队列"""
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue()
        return self._queues[run_id]

    def remove_queue(self, run_id: str):
        """清理队列"""
        self._queues.pop(run_id, None)
        self._results.pop(run_id, None)

    async def _emit(self, run_id: str, event: str, data: dict):
        """向SSE队列发送事件"""
        queue = self._queues.get(run_id)
        if queue:
            await queue.put({
                "event": event,
                "timestamp": datetime.now().isoformat(),
                **data,
            })

    async def run_inner_loop(
        self,
        student_id: int,
        video_path: str,
        trigger_type: str = "manual",
        run_id: str | None = None,
    ) -> dict:
        """
        执行内环流程: 感知智能体 → 情绪识别

        多智能体协作模式:
        1. 感知智能体执行情绪识别
        2. 结果传递给协调智能体汇总
        """
        run_id = run_id or str(uuid.uuid4())
        _ = self.get_queue(run_id)

        await self._emit(run_id, "thought", {
            "agent": self.name,
            "content": f"开始{trigger_type}模式情绪采集: 学生ID={student_id}",
        })

        await self._emit(run_id, "action", {
            "agent": self.perception.name,
            "tool": "多模态情绪识别",
            "input": {"student_id": student_id, "video_path": video_path},
        })

        try:
            result = await self.perception.think(
                message=f"请对视频路径 {video_path} 中的学生（ID={student_id}）进行多模态情绪识别。",
                context={"video_path": video_path, "student_id": student_id},
            )

            await self._emit(run_id, "observation", {
                "agent": self.perception.name,
                "result": result.get("final_answer", "")[:500],
            })

            await self._emit(run_id, "final", {
                "agent": self.name,
                "content": f"情绪采集完成: 感知智能体已完成识别",
                "perception_result": result,
            })

            self._results[run_id] = result
            asyncio.create_task(self._schedule_cleanup(run_id))
            return result

        except Exception as e:
            logger.error(f"内环执行失败: {e}")
            await self._emit(run_id, "error", {"content": str(e)})
            return {"error": str(e)}

    async def run_outer_loop(
        self,
        target_date: str,
        student_ids: list[int],
        student_names: dict[int, str] | None = None,
        run_id: str | None = None,
    ) -> dict:
        """
        执行外环流程: 分析智能体 → 报告智能体 → 预警智能体

        多智能体协作模式（完整的AIGC流水线）:
        1. 分析智能体: 拉取7天数据 → 计算12项指标 → 风险判定
        2. 报告智能体: 基于分析结果 → AIGC生成评估报告
        3. 预警智能体: 根据风险等级 → 多渠道反馈

        这是比赛核心展示的多Agent + AIGC协作流程。
        """
        run_id = run_id or str(uuid.uuid4())
        _ = self.get_queue(run_id)
        names = student_names or {}

        await self._emit(run_id, "thought", {
            "agent": self.name,
            "content": f"开始每日心理健康分析 [{target_date}]，涉及 {len(student_ids)} 名学生",
        })

        all_results = []

        for sid in student_ids:
            student_name = names.get(sid, f"学生#{sid}")

            # 步骤1: 分析智能体
            await self._emit(run_id, "action", {
                "agent": self.analysis.name,
                "tool": "时序心理分析",
                "input": {"student_id": sid, "target_date": target_date},
            })

            try:
                analysis_result = await self.analysis.think(
                    message=f"请对学生 {student_name}（ID={sid}）进行 {target_date} 的心理健康深度分析。",
                    context={"student_id": sid, "target_date": target_date},
                )

                await self._emit(run_id, "observation", {
                    "agent": self.analysis.name,
                    "result": analysis_result.get("final_answer", "")[:500],
                })

                # 步骤2: 报告智能体 (AIGC)
                await self._emit(run_id, "action", {
                    "agent": self.report.name,
                    "tool": "生成心理评估日报",
                    "input": {"student_name": student_name},
                })

                report_result = await self.report.think(
                    message=f"请为 {student_name} 生成 {target_date} 的心理评估日报和干预建议。",
                    context={
                        "student_name": student_name,
                        "date": target_date,
                        "analysis": str(analysis_result.get("final_answer", "")),
                    },
                )

                await self._emit(run_id, "observation", {
                    "agent": self.report.name,
                    "result": report_result.get("final_answer", "")[:500],
                })

                # 步骤3: 预警智能体（如需要）
                await self._emit(run_id, "action", {
                    "agent": self.alert.name,
                    "tool": "多渠道反馈",
                    "input": {"student_name": student_name},
                })

                alert_result = await self.alert.think(
                    message=f"请根据分析结果对 {student_name} 进行分级预警判断和反馈。",
                    context={
                        "student_name": student_name,
                        "analysis": str(analysis_result.get("final_answer", "")),
                    },
                )

                await self._emit(run_id, "observation", {
                    "agent": self.alert.name,
                    "result": alert_result.get("final_answer", "")[:500],
                })

                all_results.append({
                    "student_id": sid,
                    "student_name": student_name,
                    "analysis": analysis_result,
                    "report": report_result,
                    "alert": alert_result,
                })

            except Exception as e:
                logger.error(f"外环执行失败 (学生={student_name}): {e}")
                all_results.append({
                    "student_id": sid,
                    "student_name": student_name,
                    "error": str(e),
                })

        await self._emit(run_id, "final", {
            "agent": self.name,
            "content": f"每日分析完成: 共 {len(student_ids)} 名学生，"
                      f"成功 {len([r for r in all_results if 'error' not in r])} 名",
            "summary": {
                "total": len(student_ids),
                "success": len([r for r in all_results if "error" not in r]),
                "failed": len([r for r in all_results if "error" in r]),
            },
        })

        self._results[run_id] = {"all_results": all_results}
        asyncio.create_task(self._schedule_cleanup(run_id))
        return {"all_results": all_results}

    async def _schedule_cleanup(self, run_id: str, delay: int = 120):
        """延迟清理队列和结果缓存"""
        await asyncio.sleep(delay)
        self.remove_queue(run_id)

    def get_agent_info(self) -> dict:
        """获取所有智能体的信息"""
        return {
            "orchestrator": {"name": self.name, "description": self.description},
            "agents": [
                self.perception.get_info(),
                self.analysis.get_info(),
                self.report.get_info(),
                self.alert.get_info(),
            ],
            "platform": self.perception.get_info().get("platform", "未知"),
            "streaming": self.streaming,
        }
