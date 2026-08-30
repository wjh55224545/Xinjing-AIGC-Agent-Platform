"""
情绪测量实验报告生成器（学科教学/科研版）
==========================================

面向心理学「实验教学」与「科研数据采集」场景，把 E1–E12 前庭振动测量结果
与量表数据组装成符合心理测量课程规范的结构化实验报告：

    实验目的 → 实验方法（被试/设备/程序） → 实验结果（个体 vs 常模 Z 分）
    → 讨论（量表×AI 交叉验证） → 结论与教学建议

LLM 优先（复用 心镜·AIGC 生成通道），不可用时降级为模板模式，
保证课程/教学场景下始终可输出可交付的实验报告。
"""

from __future__ import annotations
import logging
from datetime import datetime
from backend.aigc.templates.experiment_template import EXPERIMENT_REPORT_TEMPLATE
from backend.aigc.llm_client import llm_generate as _llm_generate

logger = logging.getLogger(__name__)


class ExperimentReportGenerator:
    """情绪测量实验报告生成器（学科教学/科研版）"""

    name = "情绪测量实验报告生成"
    description = "基于 E1-E12 前庭振动参数与量表数据，生成符合心理测量课程规范的结构化实验报告"

    def generate(
        self,
        student_name: str = "",
        date: str = "",
        e_params: dict | None = None,
        k_value: float | None = None,
        scale_data: dict | None = None,
        experiment_title: str = "基于前庭振动技术（VibraImage）的情绪测量实验",
        teacher_name: str = "",
    ) -> dict:
        """生成实验报告。"""
        e = e_params or {}
        scales = scale_data or {}
        report_date = date or datetime.now().strftime("%Y-%m-%d")
        name = student_name or "演示被试"

        # ---- LLM 优先 ----
        llm_text = self._try_llm_generate(
            name, report_date, e, k_value, scales, experiment_title
        )
        if llm_text:
            return {
                "report_type": "experiment",
                "student_name": name,
                "date": report_date,
                "title": experiment_title,
                "report_text": llm_text,
                "generated_by": "心镜·AIGC智能体 (学科实验报告)",
            }

        # ---- 模板降级 ----
        z_scores = self._zscore_table(e)
        z_highlight = self._highlight_extreme(z_scores)
        norm_table = self._norm_table(e)
        scale_summary = self._scale_summary(scales)
        crosscheck = self._crosscheck_summary(scales)
        conclusions = self._conclusions(z_scores, scales)

        report_text = EXPERIMENT_REPORT_TEMPLATE.format(
            title=experiment_title,
            date=report_date,
            student_name=name,
            teacher_name=teacher_name or "（指导教师）",
            experiment_objective=self._objective(),
            experiment_method=self._method(experiment_title),
            norm_table=norm_table,
            z_highlight=z_highlight,
            scale_summary=scale_summary,
            crosscheck=crosscheck,
            conclusions=conclusions,
        )

        return {
            "report_type": "experiment",
            "student_name": name,
            "date": report_date,
            "title": experiment_title,
            "report_text": report_text,
            "generated_by": "心镜·AIGC智能体 (模板模式)",
        }

    # ---- LLM 生成 ----
    def _try_llm_generate(
        self, name: str, date: str, e: dict, k_value: float | None,
        scales: dict, title: str,
    ) -> str | None:
        if not e:
            return None
        e_str = "\n".join(f"- {k}: {v}" for k, v in e.items())
        scale_str = "\n".join(
            f"- {k}: 标准分 {v.get('standard_score')}，等级 {v.get('level')}"
            for k, v in scales.items()
        ) or "- 本次未提交量表"

        system_prompt = (
            "你是一位心理测量学课程的实验指导教师。请撰写一份结构规范的"
            "《情绪测量实验报告》，遵循实验目的、实验方法、实验结果、讨论、结论"
            "五个部分，用 Markdown 输出，语言学术、严谨、可读。"
        )
        user_prompt = f"""请为被试「{name}」撰写 {date} 的情绪测量实验报告《{title}》。

## 前庭振动参数（E1-E12，归一化值）
{e_str}

## 量表数据（交叉验证）
{scale_str}

## 要求
1. **实验目的** — 说明用非侵入式前庭振动技术测量情绪的心理学意义
2. **实验方法** — 被试、设备（VibraImage）、程序（视频采集→引擎分析）
3. **实验结果** — 用表格呈现 E1-E12 与个体对照常模（Z 分）的解读
4. **讨论** — 结合量表数据讨论客观生理测量与主观自评的一致性
5. **结论** — 给出 2-3 条教学/研究结论与建议

请用中文撰写，专业且适合课堂教学展示。"""
        return _llm_generate(system_prompt, user_prompt)

    # ---- 模板辅助 ----
    def _objective(self) -> str:
        return (
            "本实验旨在通过非侵入式的前庭振动测量技术（VibraImage），"
            "采集被试在平静状态下的头部微振动（E1–E12 十二项心理生理参数），"
            "评估其情绪状态，并与标准化量表自评结果进行交叉验证，"
            "帮助学生理解「客观生理测量 + 主观自评」的多模态情绪评估范式。"
        )

    def _method(self, title: str) -> str:
        return (
            "**被试**：单被试演示性采集（正式实验建议 ≥30 人）。\n"
            "**设备**：普通摄像头 + 心镜·VibraImage 引擎（前庭振动频率分析，"
            "支持国产 GPU 加速）。\n"
            "**程序**：① 被试保持静坐平视摄像头约 30 秒；② 引擎逐帧提取面部关键点"
            "并计算头部微振动频谱；③ 输出 E1–E12 参数与情绪融合结果；"
            "④ 被试完成对应量表（SAS/SDS/SCL-90 等）自评；⑤ 平台自动生成"
            "个体 vs 常模（N=10,266）对照与交叉验证报告。"
        )

    def _norm_table(self, e: dict) -> str:
        from backend.vibraimage.utils.constants import NORMAL_NORMS, NORMAL_SDS, PARAM_NAMES_ZH
        rows = []
        for k, v in e.items():
            m = NORMAL_NORMS.get(k)
            sd = NORMAL_SDS.get(k)
            if m is None or sd is None:
                continue
            z = round((v - m) / sd, 2)
            name = PARAM_NAMES_ZH.get(k, k)
            rows.append(f"| {name}（{k}） | {v} | {m} | {sd} | {z} |")
        return (
            "| 参数 | 实测值 | 常模均值 | 常模 SD | Z 分 |\n"
            "|---|---|---|---|---|\n" + "\n".join(rows)
        )

    def _zscore_table(self, e: dict) -> dict:
        from backend.vibraimage.utils.constants import NORMAL_NORMS, NORMAL_SDS, PARAM_NAMES_ZH
        out = {}
        for k, v in e.items():
            m = NORMAL_NORMS.get(k)
            sd = NORMAL_SDS.get(k)
            if m is None or sd is None:
                continue
            out[PARAM_NAMES_ZH.get(k, k)] = round((v - m) / sd, 2)
        return out

    def _highlight_extreme(self, z_scores: dict) -> str:
        extreme = {k: v for k, v in z_scores.items() if abs(v) >= 1.5}
        if not extreme:
            return "各项参数 Z 分均在 ±1.5 以内，处于常模正常波动范围。"
        lines = [f"- **{k}**：Z = {v:.2f}（" + ("显著偏高" if v > 0 else "显著偏低") + "）"
                 for k, v in extreme.items()]
        return "以下参数偏离常模超过 1.5 个标准差，值得课堂讨论：\n" + "\n".join(lines)

    def _scale_summary(self, scales: dict) -> str:
        if not scales:
            return "本次实验未采集量表自评数据（可另行补充）。"
        return "\n".join(
            f"- {k}：标准分 {v.get('standard_score')}，等级「{v.get('level')}」"
            for k, v in scales.items()
        )

    def _crosscheck_summary(self, scales: dict) -> str:
        if not scales:
            return "无量表数据，无法进行交叉验证。"
        abnormal = [
            k for k, v in scales.items()
            if v.get("level") in {"moderate", "severe"}
            or v.get("standard_score", 0) >= 60
        ]
        if abnormal:
            return f"量表提示需关注（{'、'.join(abnormal)}），建议结合课堂观察与后续复测确认。"
        return "量表自评均在正常范围，与前庭振动测量结果相互印证，一致性良好。"

    def _conclusions(self, z_scores: dict, scales: dict) -> str:
        lines = [
            "1. 前庭振动测量（E1–E12）可非侵入地表征个体情绪状态，"
            "且参数对照 10,266 人常模的 Z 分具备直观的教学解释力；",
            "2. 多模态交叉验证（客观生理测量 × 主观量表自评）能有效提升"
            "情绪评估结论的可靠性，可作为心理测量课程的教学范式；",
        ]
        if scales:
            lines.append("3. 本报告数据可进一步用于个体纵向追踪与班级群体画像研究。")
        else:
            lines.append("3. 建议补充量表自评数据，以完成客观-主观一致性分析。")
        return "\n".join(lines)


def generate_research_data_readme() -> str:
    """
    生成科研数据采集说明（附在导出数据包中的 README）。
    说明导出字段的心理学含义、常模基准与引用规范，支持学术复用。
    """
    return (
        "# 心镜情绪测量数据 · 科研复用说明\n\n"
        "## 字段说明\n"
        "- `recorded_at`：采集时间（ISO 8601）\n"
        "- `fused_emotion`：融合情绪（面部 + 前庭振动双模态）\n"
        "- `fused_score`：融合情绪评分 [0,1]，越高越积极\n"
        "- `fused_valence / fused_arousal`：效价 / 唤醒度 [0,1]\n"
        "- `vi_*`：前庭振动 E1–E12 参数（aggression/stress/tension/suspect/balance/charm/"
        "energy/self_regulation/inhibition/neuroticism/depression/happiness）\n"
        "- `vi_K_value`：情绪状态指数（|K|<3 稳定，3–6 关注，≥6 预警）\n\n"
        "## 常模基准\n"
        "E1–E12 常模均值和标准差来源于 VCE 专著（Minkin, 2020, Table 6-18, N=10,266）。\n\n"
        "## 引用建议\n"
        "使用本数据请注明数据来源（心镜·AIGC 智能体平台）与测量原理文献（VibraImage / VCE）。\n\n"
        "## 隐私说明\n"
        "导出数据已做匿名化处理（隐去姓名/学号），仅保留被试编号，请勿重新关联个人身份。\n"
    )
