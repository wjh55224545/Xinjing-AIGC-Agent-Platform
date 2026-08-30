"""
AIGC输出模板 - 报告模板
========================

为心理评估日报、周报提供结构化模板。
模板定义输出格式，具体内容由LLM根据数据填充。
"""

# 心理评估日报模板
DAILY_REPORT_TEMPLATE = """## 📊 {student_name} 心理健康评估日报

**日期**: {date}
**评估平台**: 心镜·AIGC智能体平台（沐曦MetaX GPU / Gitee.AI）

---

### 一、情绪概况

{emotion_overview}

### 二、关键指标

| 指标 | 数值 | 状态 |
|------|------|------|
| 综合评分 | {overall_score:.2f}/1.00 | {score_status} |
| 情绪稳定性 | {stability:.2f} | {stability_status} |
| 积极情绪占比 | {positive_ratio:.0%} | {positive_status} |
| 负面情绪占比 | {negative_ratio:.0%} | {negative_status} |
| 情绪趋势 | {trend} | — |

### 三、关键发现

{key_findings}

### 四、风险分析

{risk_analysis}

### 五、明日预测

{next_day_prediction}

### 六、建议措施

{suggestions}

---

*本报告由心镜·AIGC智能体平台自动生成*
*算力平台: 沐曦MetaX GPU | 模型: 基于Gitee.AI国产算力*
"""

# 周度趋势分析模板
WEEKLY_TREND_TEMPLATE = """## 📈 {student_name} 周度情绪趋势分析

**分析周期**: {start_date} ~ {end_date}
**报告生成**: 心镜·AIGC智能体平台

---

### 一、周度概况

{weekly_overview}

### 二、日度对比

{day_by_day_comparison}

### 三、趋势识别

{trend_identification}

### 四、风险时段

{risk_periods}

### 五、下周预测

{next_week_prediction}

### 六、综合建议

{weekly_suggestions}

---

*数据来源: 心镜智能体7天连续监测*
*算力平台: 沐曦MetaX GPU / Gitee.AI*
"""

# 数据可视化解读模板
VISUALIZATION_TEMPLATE = """## 📉 数据可视化解读

### 图表说明
{chart_description}

### 数据洞察
{data_insights}

### 关键数值
{key_numbers}

### 对比分析
{comparative_analysis}

---

*AI生成解读，仅供参考*
"""
