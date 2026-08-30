"""
情绪测量实验报告模板（模板模式降级用）
"""

EXPERIMENT_REPORT_TEMPLATE = """# {title}

**日期**：{date}　|　**被试**：{student_name}　|　**指导教师**：{teacher_name}

---

## 一、实验目的

{experiment_objective}

## 二、实验方法

{experiment_method}

## 三、实验结果：个体 vs 常模（N=10,266）

{norm_table}

### 偏离常模的关键参数

{z_highlight}

## 四、量表自评（主观对照）

{scale_summary}

## 五、讨论：客观生理测量 × 主观自评

{crosscheck}

## 六、结论与建议

{conclusions}

---
*本报告由 心镜·AIGC 智能体平台自动生成，用于心理测量课程教学演示。*
"""
