"""
心理评估报告 PDF 导出服务
=========================

将 AIGC 心理评估日报渲染为结构化 PDF。

设计依据（医疗/健康信息报告格式化文献）：
  - Valenstein (2008). Formatting pathology reports: applying four design
    principles to improve communication and patient safety.
    Archives of Pathology & Laboratory Medicine.（诊断标题置顶、布局一致、
    信息密度优化、减少杂乱）
  - Brick et al. (2022). Risk communication in tables versus text: a registered
    report randomized trial on 'fact boxes'. Medical Decision Making.
    （表格化展示比纯文本理解更好，d=0.39）
  - Woloshin et al. (2023). Communicating health information with visual
    displays. Nature Medicine.（目标读者与任务决定展示形式）

结构：风险结论置顶 → 关键指标表 → 关键发现 → 风险分析 → 建议 → 技术附注。
"""

from __future__ import annotations
import io
import logging
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

logger = logging.getLogger(__name__)

# ---------- 中文字体注册（Windows 优先，Linux/CI 兜底） ----------
_FONT_REGISTERED = False
_FONT_NAME = "CJK"


def _register_font() -> str:
    """注册系统中文字体；找不到时回退 Helvetica（中文会缺字，尽力而为）。

    注意：回退时必须同步更新 _FONT_NAME，否则后续调用会因缓存标记
    直接返回从未注册的 "CJK" 字体名，reportlab 会报
    "Can't map determine family/bold/italic for cjk"。
    """
    global _FONT_REGISTERED, _FONT_NAME
    if _FONT_REGISTERED:
        return _FONT_NAME
    candidates = [
        # Windows
        ("C:/Windows/Fonts/simsun.ttc", 0, "SimSun"),
        ("C:/Windows/Fonts/msyh.ttc", 0, "MicrosoftYaHei"),
        ("C:/Windows/Fonts/simhei.ttf", None, "SimHei"),
        ("C:/Windows/Fonts/Deng.ttf", None, "DengXian"),
        # Linux / CI（GitHub Actions ubuntu-latest 安装 fonts-noto-cjk）
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0, "NotoSansCJK"),
        ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf", None, "NotoSansCJKsc"),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0, "NotoSansCJK"),
        # Linux 通用兜底（无中文，但可正常生成）
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", None, "DejaVuSans"),
    ]
    for path, sub_idx, label in candidates:
        if os.path.exists(path):
            try:
                if sub_idx is not None:
                    pdfmetrics.registerFont(TTFont(_FONT_NAME, path, subfontIndex=sub_idx))
                else:
                    pdfmetrics.registerFont(TTFont(_FONT_NAME, path))
                _FONT_REGISTERED = True
                logger.info(f"PDF 使用中文字体: {label} ({path})")
                return _FONT_NAME
            except Exception as e:
                logger.warning(f"字体注册失败 {path}: {e}")
    _FONT_NAME = "Helvetica"
    _FONT_REGISTERED = True
    logger.warning("PDF 未找到可用中文字体，回退 Helvetica")
    return _FONT_NAME


def _style() -> dict:
    font = _register_font()
    return {
        "title": ParagraphStyle("title", fontName=font, fontSize=18, leading=24,
                                spaceAfter=2, alignment=TA_LEFT),
        "subtitle": ParagraphStyle("subtitle", fontName=font, fontSize=10, leading=14,
                                   textColor=colors.HexColor("#555555")),
        "h2": ParagraphStyle("h2", fontName=font, fontSize=13, leading=18,
                             spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("body", fontName=font, fontSize=10.5, leading=16,
                               spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName=font, fontSize=10, leading=14),
        "note": ParagraphStyle("note", fontName=font, fontSize=8.5, leading=12,
                               textColor=colors.HexColor("#777777")),
    }


# 风险等级展示映射
RISK_SHOW = {
    "green": ("绿色 · 低风险", colors.HexColor("#16a34a")),
    "yellow": ("黄色 · 中等风险", colors.HexColor("#d97706")),
    "red": ("红色 · 高风险", colors.HexColor("#dc2626")),
}


def build_report_pdf(
    student_name: str,
    date: str,
    overall_score: float,
    risk_level: str,
    indicators: dict,
    emotion_overview: str,
    key_findings: str,
    risk_analysis: str,
    suggestions: list,
) -> bytes:
    """
    生成结构化 PDF 报告字节流。

    indicators: 指标字典（含 emotional_stability_index / positive_emotion_ratio /
                negative_emotion_ratio / trend / emotion_recovery_speed /
                stress_accumulation_index）
    suggestions: 建议列表（dict 含 content，或字符串）
    """
    st = _style()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"{student_name} 心理健康评估日报",
    )
    story = []

    # ---- 标题区 ----
    story.append(Paragraph(f"{student_name} 心理健康评估日报", st["title"]))
    story.append(Paragraph(f"报告日期：{date}　生成平台：心镜·AIGC智能体平台", st["subtitle"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1")))

    # ---- 1. 风险结论置顶（Valenstein 2008：诊断标题置顶） ----
    risk_cn, risk_color = RISK_SHOW.get(risk_level, (risk_level, colors.HexColor("#64748b")))
    conclusion = (
        f"综合评分 {overall_score:.2f}/1.00　|　风险等级 {risk_cn}　|　"
        f"情绪趋势 {indicators.get('trend', '—')}"
    )
    box = Table([[Paragraph(conclusion, st["body"])]], colWidths=[174 * mm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), risk_color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(Spacer(1, 10))
    story.append(box)

    # ---- 2. 情绪概况 ----
    story.append(Paragraph("一、情绪概况", st["h2"]))
    story.append(Paragraph(emotion_overview, st["body"]))

    # ---- 3. 关键指标表（Brick et al. 2022：表格化展示） ----
    story.append(Paragraph("二、关键指标", st["h2"]))

    def _status(label: str, ok: bool) -> str:
        return f"{label}"

    rows = [
        ["指标", "数值", "状态"],
        ["综合评分", f"{overall_score:.2f}/1.00", _status("—", True)],
        ["风险等级", risk_cn, "—"],
        ["情绪稳定性", f"{indicators.get('emotional_stability_index', '—')}", "—"],
        ["积极情绪占比", f"{indicators.get('positive_emotion_ratio', '—')}", "—"],
        ["负面情绪占比", f"{indicators.get('negative_emotion_ratio', '—')}", "—"],
        ["情绪趋势", f"{indicators.get('trend', '—')}", "—"],
        ["情绪恢复速度", f"{indicators.get('emotion_recovery_speed', '—')}", "—"],
        ["压力累积指数", f"{indicators.get('stress_accumulation_index', '—')}", "—"],
    ]
    # 占比数值转百分比显示
    for i in range(1, len(rows)):
        if rows[i][0] in ("积极情绪占比", "负面情绪占比"):
            try:
                v = float(rows[i][1])
                rows[i][1] = f"{v:.0%}"
            except (ValueError, TypeError):
                pass
    table = Table(rows, colWidths=[44 * mm, 60 * mm, 70 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), st["cell"].fontName),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)

    # ---- 4. 关键发现 ----
    story.append(Paragraph("三、关键发现", st["h2"]))
    for line in str(key_findings).split("\n"):
        if line.strip():
            story.append(Paragraph(line.strip().lstrip("- "), st["body"]))

    # ---- 5. 风险分析 ----
    story.append(Paragraph("四、风险分析", st["h2"]))
    story.append(Paragraph(risk_analysis, st["body"]))

    # ---- 6. 建议措施 ----
    story.append(Paragraph("五、建议措施", st["h2"]))
    for s in suggestions:
        if isinstance(s, dict):
            story.append(Paragraph(f"• {s.get('content', '')}", st["body"]))
        else:
            story.append(Paragraph(f"• {s}", st["body"]))

    # ---- 7. 技术附注（来源/口径/免责声明） ----
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#e2e8f0")))
    story.append(Paragraph("技术附注", st["h2"]))
    story.append(Paragraph(
        "数据来源：面部表情识别（计算机视觉）与 VibraImage 前庭振动测量融合的情绪信号，"
        "并结合心理量表测评交叉验证。", st["note"]))
    story.append(Paragraph(
        "指标口径：综合评分为当日情绪融合得分的均值；积极/负面情绪占比按当日情绪记录中"
        "对应类别条数占比计算；情绪稳定性由评分离散程度换算（0–1，越高越稳定）；"
        "风险等级由综合评分、情绪构成与稳定性综合判定。", st["note"]))
    story.append(Paragraph(
        "免责声明：本报告由 AI 系统自动生成，仅作为心理状态监测的辅助参考，"
        "不构成医学诊断。如有持续情绪困扰，请及时联系学校心理咨询中心或专业医疗机构。",
        st["note"]))

    doc.build(story)
    return buf.getvalue()
