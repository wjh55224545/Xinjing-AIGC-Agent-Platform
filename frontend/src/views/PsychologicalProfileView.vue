<template>
  <div>
    <h2>个体多维心理画像</h2>
    <p class="page-sub">
      聚合量表（SCL-90 十维度 / SAS / SDS）、E1-E12 前庭参数、风险分级与应对倾向，
      形成个体多维心理画像，辅助心理健康评估决策。
      设计依据：HealthPrism 多模态健康画像（Jiang et al., 2023）；临床仪表盘维度化布局（Wake et al., 2022）。
    </p>

    <!-- 输入选择 -->
    <div class="card">
      <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">
        <div>
          <label class="text-muted" style="display:block;margin-bottom:6px">评估对象</label>
          <select v-model="target" class="input">
            <option value="virtual">虚拟被试（合成数据）</option>
            <option value="student">真实学生（系统记录）</option>
          </select>
        </div>
        <div v-if="target==='virtual'">
          <label class="text-muted" style="display:block;margin-bottom:6px">虚拟被试剖面</label>
          <select v-model="profileId" class="input">
            <option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
        <div v-if="target==='student'">
          <label class="text-muted" style="display:block;margin-bottom:6px">学生 ID</label>
          <input v-model.number="studentId" type="number" class="input" placeholder="如 1" style="width:120px" />
        </div>
        <button class="btn btn-primary" @click="loadProfile" :disabled="loading" style="margin-top:20px">
          {{ loading ? '生成中...' : '生成画像' }}
        </button>
      </div>
    </div>

    <!-- 画像结果 -->
    <div v-if="profile" class="profile-wrap">
      <div class="card head-card">
        <div class="head-left">
          <h3 style="margin:0">
            {{ profile.profile_name || ('学生 #' + profile.student_id) }}
          </h3>
          <p class="text-muted" style="margin:6px 0 0">
            {{ profile.profile_description || '基于系统内量表与AI情绪记录聚合' }}
          </p>
          <span v-if="profile.is_synthetic" class="syn-tag">合成数据</span>
        </div>
        <div class="risk-pill" :class="'risk-' + profile.risk.overall_level">
          <span class="risk-label">综合风险</span>
          <strong>{{ profile.risk.overall_level_cn }}</strong>
          <span class="risk-score">{{ profile.risk.overall_score }}/100</span>
        </div>
      </div>

      <!-- 量表画像 -->
      <div class="card">
        <h3>📋 量表画像</h3>
        <div class="grid-2">
          <div class="chart-box" v-if="profile.scale_profile.scl90_dimensions">
            <h4>SCL-90 十维度（标准分）</h4>
            <v-chart :option="sclOption" autoresize style="height:300px"></v-chart>
          </div>
          <div class="scale-scores">
            <h4>核心量表标准分</h4>
            <div class="score-row" v-if="profile.scale_profile.sas_standard_score !== null && profile.scale_profile.sas_standard_score !== undefined">
              <span class="score-name">SAS 焦虑</span>
              <span class="score-val" :class="scoreLevel(profile.scale_profile.sas_standard_score, 50)">{{ profile.scale_profile.sas_standard_score }}</span>
            </div>
            <div class="score-row" v-if="profile.scale_profile.sds_standard_score !== null && profile.scale_profile.sds_standard_score !== undefined">
              <span class="score-name">SDS 抑郁</span>
              <span class="score-val" :class="scoreLevel(profile.scale_profile.sds_standard_score, 53)">{{ profile.scale_profile.sds_standard_score }}</span>
            </div>
            <div class="score-row" v-if="profile.scale_profile.pss10_standard_score !== null && profile.scale_profile.pss10_standard_score !== undefined">
              <span class="score-name">PSS-10 压力</span>
              <span class="score-val">{{ profile.scale_profile.pss10_standard_score }}</span>
            </div>
            <p class="text-muted" style="margin-top:12px;font-size:12px;line-height:1.6">
              SCL-90 维度得分 = 维度条目均分 ×100（常模界值 ≈200 提示阳性倾向）；
              SAS 标准分 ≥50 轻度、≥60 中度、≥70 重度；SDS 标准分 ≥53 轻度。
            </p>
          </div>
        </div>
      </div>

      <!-- 前庭参数画像（虚拟被试） -->
      <div class="card" v-if="profile.vestibular_profile">
        <h3>📐 E1-E12 前庭参数画像（与常模对照 Z 分）</h3>
        <p class="text-muted" style="margin:4px 0 12px">
          数据来源：VCE.pdf (Minkin, 2020) Table 6-18 "All" 列（N=10,266）。K 值：
          <strong>{{ profile.vestibular_profile.k_value }}</strong>（{{ profile.vestibular_profile.k_interpretation }}）
        </p>
        <div class="grid-2">
          <v-chart :option="vestibOption" autoresize style="height:300px"></v-chart>
          <div class="z-list">
            <div v-for="p in profile.vestibular_profile.params" :key="p.key" class="z-row">
              <span class="z-name">{{ p.name_zh }}</span>
              <span class="z-val" :class="zClass(p)">{{ p.value }}（z={{ p.z_score }}）</span>
              <div class="z-bar">
                <div class="z-fill" :class="zClass(p)" :style="{ width: Math.min(Math.abs(p.z_score)*12, 100) + '%', marginLeft: p.z_score < 0 ? 'auto' : '0' }"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- SJT 应对倾向 -->
      <div class="card" v-if="profile.sjt_profile">
        <h3>🧠 应对倾向画像（SJT）</h3>
        <p class="text-muted" style="margin:4px 0 12px">
          情境判断测验总分 <strong>{{ profile.sjt_profile.total_score }}</strong>（{{ profile.sjt_profile.total_level.label }}）
          · 维度覆盖：考试焦虑 / 学业压力 / 同伴冲突 / 社交回避 / 情绪调节 / 求助意愿
        </p>
        <div class="sjt-dims">
          <div v-for="(d, key) in profile.sjt_profile.dimension_levels" :key="key" class="dim-row">
            <div class="dim-head">
              <span class="dim-name">{{ key }}</span>
              <span class="dim-badge" :class="d.level">{{ d.label }}</span>
              <span class="dim-score">{{ d.score }}</span>
            </div>
            <div class="dim-bar">
              <div class="dim-fill" :class="d.level" :style="{ width: d.score + '%' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 风险与建议 -->
      <div class="card">
        <h3>🔔 风险分级与干预建议</h3>
        <div v-if="profile.risk.warning_flags.length" class="warning-box">
          <p v-for="(w, i) in profile.risk.warning_flags" :key="i">⚠️ {{ w }}</p>
        </div>
        <ul class="rec-list">
          <li v-for="(r, i) in profile.risk.recommendations" :key="i">{{ r }}</li>
        </ul>
      </div>

      <!-- 诊断一致性（虚拟被试） -->
      <div class="card" v-if="profile.diagnosis_consistency">
        <h3>✅ 诊断一致性对照（真值验证）</h3>
        <div class="truth-row">
          <span>量表等级</span>
          <div>
            <span class="verdict" :class="profile.diagnosis_consistency.scale_level_match ? 'ok' : 'diff'">
              {{ profile.diagnosis_consistency.scale_level_match ? '一致' : '偏差' }}
            </span>
            系统判定「{{ profile.diagnosis_consistency.pred_level_cn }}」 / 真值「{{ profile.diagnosis_consistency.true_level_cn }}」
          </div>
        </div>
        <div class="truth-row">
          <span>情绪状态</span>
          <div>
            <span class="verdict" :class="profile.diagnosis_consistency.emotion_match ? 'ok' : 'diff'">
              {{ profile.diagnosis_consistency.emotion_match ? '一致' : '偏差' }}
            </span>
            系统判定 vs 真值（合成数据对照）
          </div>
        </div>
      </div>

      <p class="text-muted note">{{ profile.note }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import axios from "axios";
import { use } from "echarts/core";
import { RadarChart } from "echarts/charts";
import { RadarComponent, TooltipComponent, LegendComponent, GridComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
use([RadarChart, RadarComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer]);

const target = ref("virtual");
const profileId = ref("mild_anxiety");
const studentId = ref(1);
const profiles = ref([]);
const profile = ref(null);
const loading = ref(false);

onMounted(async () => {
  try {
    const resp = await axios.get("/api/virtual-subjects/profiles");
    profiles.value = resp.data.data || [];
    if (profiles.value.length) profileId.value = profiles.value[1]?.id || profiles.value[0].id;
  } catch (e) { /* 静默 */ }
});

async function loadProfile() {
  loading.value = true;
  profile.value = null;
  try {
    let resp;
    if (target.value === "virtual") {
      resp = await axios.post("/api/psychological-profile/virtual", { profile_id: profileId.value, seed: 42 });
    } else {
      resp = await axios.get(`/api/psychological-profile/${studentId.value || 1}`);
    }
    profile.value = resp.data.data;
  } catch (e) {
    alert("生成画像失败：" + (e.response?.data?.detail || e.message));
  } finally {
    loading.value = false;
  }
}

const sclOption = computed(() => {
  const dims = profile.value?.scale_profile?.scl90_dimensions || {};
  const keys = Object.keys(dims);
  return {
    tooltip: { trigger: "item" },
    legend: { show: false },
    radar: {
      indicator: keys.map(k => ({ name: k, max: 300 })),
      radius: "62%",
      axisName: { fontSize: 10 },
    },
    series: [{
      type: "radar",
      data: [{
        value: keys.map(k => dims[k]),
        name: "SCL-90",
        areaStyle: { color: "rgba(99,102,241,0.25)" },
        lineStyle: { color: "#6366f1" },
        itemStyle: { color: "#6366f1" },
      }],
    }],
  };
});

const vestibOption = computed(() => {
  const params = profile.value?.vestibular_profile?.params || [];
  const neg = params.filter(p => p.group === "negative");
  const pos = params.filter(p => p.group === "positive");
  const phys = params.filter(p => p.group === "physiological");
  const makeSeries = (items, color, name) => ({
    name,
    type: "radar",
    value: items.map(p => p.value),
    areaStyle: { color: color + "22" },
    lineStyle: { color },
    itemStyle: { color },
  });
  return {
    tooltip: { trigger: "item" },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    radar: {
      indicator: [
        ...neg.map(p => ({ name: p.name_zh, max: 100 })),
        ...pos.map(p => ({ name: p.name_zh, max: 100 })),
        ...phys.map(p => ({ name: p.name_zh, max: 100 })),
      ],
      radius: "58%",
      center: ["50%", "48%"],
      axisName: { fontSize: 10 },
      splitNumber: 3,
    },
    series: [
      makeSeries(neg, "#ef4444", "负性"),
      makeSeries(pos, "#10b981", "正性"),
      makeSeries(phys, "#f59e0b", "生理"),
    ],
  };
});

function scoreLevel(score, boundary) {
  if (score === null || score === undefined) return "";
  return score >= boundary + 20 ? "lv-severe" : score >= boundary ? "lv-mild" : "lv-normal";
}
function zClass(p) {
  return p.z_score >= 2 ? "z-high" : p.z_score <= -2 ? "z-low" : "";
}
</script>

<style scoped>
.page-sub { color: var(--text-muted, #9e9e9e); font-size: 13px; }
.card { background: var(--card-bg, #fff); border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.text-muted { color: var(--text-muted, #9e9e9e); font-size: 13px; }
.btn { padding: 10px 20px; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; font-weight: 600; }
.btn-primary { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.input { padding: 9px 12px; border: 1px solid var(--border, #e5e7eb); border-radius: 8px; font-size: 14px; background: var(--card-bg, #fff); }

.head-card { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.head-left { flex: 1; }
.syn-tag { display: inline-block; margin-top: 8px; font-size: 11px; padding: 2px 8px; background: rgba(99,102,241,0.12); color: #6366f1; border-radius: 6px; }
.risk-pill { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 14px 24px; border-radius: 12px; }
.risk-pill.risk-low { background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); color: #059669; }
.risk-pill.risk-medium { background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); color: #d97706; }
.risk-pill.risk-high { background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3); color: #dc2626; }
.risk-pill.risk-extreme { background: rgba(185,28,28,0.15); border: 1px solid rgba(185,28,28,0.4); color: #b91c1c; }
.risk-label { font-size: 11px; opacity: .8; }
.risk-pill strong { font-size: 20px; }
.risk-score { font-size: 12px; opacity: .8; }

.grid-2 { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }
@media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
.chart-box, .scale-scores { background: var(--section-bg, #f9fafb); border-radius: 12px; padding: 16px; }
h3 { font-size: 16px; margin: 0 0 12px; }
h4 { font-size: 14px; margin: 0 0 10px; }

.score-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 10px; background: var(--card-bg, #fff); margin-bottom: 8px; }
.score-name { font-size: 14px; }
.score-val { font-size: 22px; font-weight: 700; }
.score-val.lv-normal { color: #10b981; }
.score-val.lv-mild { color: #f59e0b; }
.score-val.lv-severe { color: #ef4444; }

.z-list { display: flex; flex-direction: column; gap: 6px; background: var(--section-bg, #f9fafb); border-radius: 12px; padding: 16px; }
.z-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.z-name { width: 64px; flex-shrink: 0; }
.z-val { width: 92px; text-align: right; font-weight: 600; }
.z-val.z-high { color: #ef4444; }
.z-val.z-low { color: #2563eb; }
.z-bar { flex: 1; height: 6px; background: var(--tag-bg, #f3f4f6); border-radius: 3px; overflow: hidden; }
.z-fill { height: 100%; }
.z-fill.z-high { background: #ef4444; }
.z-fill.z-low { background: #2563eb; }

.sjt-dims { display: flex; flex-direction: column; gap: 10px; }
.dim-row { display: flex; flex-direction: column; gap: 4px; }
.dim-head { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.dim-name { flex: 1; font-weight: 600; }
.dim-badge { font-size: 11px; padding: 2px 8px; border-radius: 6px; font-weight: 600; }
.dim-badge.high { background: #d1fae5; color: #059669; }
.dim-badge.medium { background: #fef3c7; color: #d97706; }
.dim-badge.low { background: #fee2e2; color: #dc2626; }
.dim-score { font-weight: 700; color: #6366f1; width: 36px; text-align: right; }
.dim-bar { height: 8px; background: var(--tag-bg, #f3f4f6); border-radius: 4px; overflow: hidden; }
.dim-fill { height: 100%; border-radius: 4px; }
.dim-fill.high { background: linear-gradient(90deg, #34d399, #10b981); }
.dim-fill.medium { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.dim-fill.low { background: linear-gradient(90deg, #f87171, #ef4444); }

.warning-box { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; }
.warning-box p { margin: 4px 0; font-size: 13px; color: #b91c1c; }
.rec-list { margin: 0; padding-left: 18px; }
.rec-list li { font-size: 13px; color: var(--text, #4b5563); margin: 4px 0; }

.truth-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; font-size: 14px; }
.truth-row > span { width: 72px; color: var(--text-muted, #6b7280); flex-shrink: 0; }
.verdict { padding: 2px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; margin-right: 8px; }
.verdict.ok { background: #d1fae5; color: #059669; }
.verdict.diff { background: #fef3c7; color: #d97706; }

.note { margin-top: 8px; font-size: 12px; line-height: 1.6; }
</style>
