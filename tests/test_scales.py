"""
量表测评模块测试
=================

覆盖：
  1. 量表题库加载（SAS/SDS/SCL-90/PSS-10/PANAS）
  2. 全量表自动计分（含反向题、标准分公式、维度得分、0-base 计分）
  3. CAT 自适应测验引擎（最大信息量选题、θ 估计、结果映射）
  4. 量表×AI 统计检验（Pearson r / Cohen's Kappa / 灵敏度特异度）
  5. 实验报告生成器（模板模式）
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.api.routes.scales import _load_scale, _score_scale

ALL_SCALES = ["SAS", "SDS", "SCL-90", "PSS-10", "PANAS"]


class TestScaleLoading:
    """题库加载"""

    @pytest.mark.parametrize("code", ALL_SCALES)
    def test_load_all_scales(self, code):
        s = _load_scale(code)
        assert s["code"] == code
        assert len(s["questions"]) == s["questions_count"]
        ids = [q["id"] for q in s["questions"]]
        assert ids == list(range(1, s["questions_count"] + 1)), "题号应连续"

    def test_unknown_scale_404(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _load_scale("NOPE")


class TestScoring:
    """自动计分"""

    def test_sas_known_answer(self):
        """SAS 全部选2：15正向×2 + 5反向×(5-2)=30+15=45，标准分 45×1.25≈56"""
        s = _load_scale("SAS")
        sc = _score_scale(s, [2] * 20)
        assert sc["raw_score"] == 45
        assert sc["standard_score"] == 56
        assert sc["level"] == "mild"

    def test_sds_known_answer(self):
        """SDS 全部选2：10正向×2 + 10反向×(5-2)=20+30=50，标准分 62"""
        s = _load_scale("SDS")
        sc = _score_scale(s, [2] * 20)
        assert sc["raw_score"] == 50
        assert sc["standard_score"] == 62
        assert sc["level"] == "mild"

    def test_scl90_dimensions(self):
        """SCL-90 全部选1 → 各维度均分 1.0，总均分 1.0，标准分 100（normal）"""
        s = _load_scale("SCL-90")
        sc = _score_scale(s, [1] * 90)
        assert sc["standard_score"] == 100
        assert sc["level"] == "normal"
        assert set(sc["dimension_scores"].keys()) == {
            "躯体化", "强迫症状", "人际关系敏感", "抑郁", "焦虑", "敌对", "恐怖", "偏执", "精神病性", "其他",
        }
        assert all(abs(v - 1.0) < 1e-6 for v in sc["dimension_scores"].values())

    def test_pss10_zero_base(self):
        """PSS-10 0-base 计分：全部选1（=0分）
        正向 6 题×0 + 反向 4 题(4/5/7/8)×(4-0=4) = 16；
        若错误按 1-base 计分则为 6×1+4×3=18，故 16 可验证 0-base 换算。"""
        s = _load_scale("PSS-10")
        sc = _score_scale(s, [1] * 10)
        assert sc["raw_score"] == 16
        assert sc["standard_score"] == 16
        assert sc["level"] == "mild"

    def test_pss10_reverse(self):
        """PSS-10 全部选5（=4分，即完全压力状态）：正向题4分×6 + 反向题0分×4 = 24（中度）"""
        s = _load_scale("PSS-10")
        sc = _score_scale(s, [5] * 10)
        assert sc["raw_score"] == 24
        assert sc["level"] == "moderate"

    def test_panas_dimension(self):
        """PANAS 全部选5：正性情绪均值 5.0、负性情绪均值 5.0 → 标准分 500（severe）"""
        s = _load_scale("PANAS")
        sc = _score_scale(s, [5] * 20)
        assert sc["dimension_scores"]["正性情绪"] == 5.0
        assert sc["dimension_scores"]["负性情绪"] == 5.0
        assert sc["standard_score"] == 500
        assert sc["level"] == "severe"


class TestCatEngine:
    """CAT 自适应测验引擎"""

    def _run(self, scale_code, answer_fn, max_extra=3):
        from backend.services.cat import next_item, _default_max
        s = _load_scale(scale_code)
        qs = s["questions"]
        rev = s["scoring"]["reverse_items"]
        mx = _default_max(qs)
        answered = []
        res = None
        for _ in range(mx + max_extra):
            res = next_item(qs, answered, rev, 0.0, max_items=mx)
            if res["done"] or res["next"] is None:
                break
            qid = res["next"]["id"]
            answered.append({"id": qid, "score": answer_fn(qid, rev)})
        return res, answered

    def test_cat_selects_and_converges(self):
        res, answered = self._run("SAS", lambda qid, rev: 4 if qid not in rev else 1)
        assert res["done"] is True
        assert len(answered) >= 5
        assert res["theta"] > 0, "高症状作答应得到正 θ"
        assert res["score_estimate"]["level"] == "severe"

    def test_cat_healthy_map(self):
        res, answered = self._run("SAS", lambda qid, rev: 1 if qid not in rev else 4)
        assert res["theta"] < 0, "健康作答应得到负 θ"
        assert res["score_estimate"]["level"] == "normal"

    def test_cat_scales_without_irt(self):
        """SCL-90 无逐题 IRT 参数时应用默认锚定参数，不应报错"""
        res, answered = self._run("SCL-90", lambda qid, rev: 5)
        assert res["done"] is True


class TestScaleStats:
    """统计检验"""

    def test_pearson_r_perfect(self):
        from backend.services.scale_stats import pearson_r
        assert pearson_r([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0, abs=1e-3)

    def test_pearson_r_negative(self):
        from backend.services.scale_stats import pearson_r
        r = pearson_r([1, 2, 3], [3, 2, 1])
        assert r == pytest.approx(-1.0, abs=1e-3)

    def test_cohen_kappa_perfect(self):
        from backend.services.scale_stats import cohen_kappa
        assert cohen_kappa([True, True, False, False], [True, True, False, False]) == pytest.approx(1.0)

    def test_binary_metrics(self):
        from backend.services.scale_stats import binary_metrics
        m = binary_metrics([True, True, False, False], [True, False, True, False])
        assert m["tp"] == 1 and m["fp"] == 1 and m["fn"] == 1 and m["tn"] == 1
        assert m["sensitivity"] == pytest.approx(0.5)


class TestExperimentGenerator:
    """实验报告生成器（模板模式）"""

    def test_template_report(self):
        from backend.aigc.experiment_generator import ExperimentReportGenerator
        gen = ExperimentReportGenerator()
        e = {
            "aggression": 30, "stress": 28, "tension": 22, "suspicious": 20,
            "balance": 62, "charm": 58, "energy": 45, "self_regulation": 55,
            "inhibition": 20, "neuroticism": 25, "depression": 30, "happiness": 42,
        }
        r = gen.generate(
            student_name="测试被试", e_params=e, k_value=4.5,
            scale_data={"SAS": {"standard_score": 62, "level": "mild"}},
        )
        assert r["report_type"] == "experiment"
        assert "实验目的" in r["report_text"]
        assert "实验方法" in r["report_text"]
        assert "常模" in r["report_text"]

    def test_data_readme(self):
        from backend.aigc.experiment_generator import generate_research_data_readme
        text = generate_research_data_readme()
        assert "字段说明" in text
        assert "常模基准" in text
        assert "隐私说明" in text
