<template>
  <div>
    <h2>虚拟被试 · 系统诊断演示</h2>
    <p class="page-sub">合成数据引擎 + 系统自动诊断：生成虚拟被试，由诊断算法自动完成量表计分、情绪判定与风险分级，并对照真值验证诊断准确性</p>

    <!-- 步骤1：选择剖面 -->
    <div class="card" v-if="!currentCase">
      <h3>① 选择虚拟被试剖面</h3>
      <p class="text-muted">每个剖面对应一种典型心理状态（θ 越大症状越重）。系统将基于该被试的合成数据执行自动诊断。</p>
      <div class="profile-grid">
        <div v-for="p in profiles" :key="p.id" class="profile-card" :class="severityOf(p.theta)">
          <div class="profile-header">
            <strong>{{ p.name }}</strong>
            <span class="severity-tag">{{ severityText(severityOf(p.theta)) }}</span>
          </div>
          <p class="profile-desc">{{ p.description }}</p>
          <div class="profile-tags">
            <span class="tag">{{ p.dominant_scale }}</span>
            <span class="tag">θ={{ p.theta }}</span>
          </div>
          <button class="btn btn-primary" @click="generateCase(p.id)" :disabled="generating">
            {{ generating ? '生成中...' : '生成并开始诊断' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 步骤2：虚拟被试数据 + 系统自动诊断 -->
    <div class="card" v-if="currentCase">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="margin:0">② {{ currentCase.profile_name }} · {{ currentCase.subject_id }}</h3>
        <button class="btn btn-cancel" @click="reset">重新选择</button>
      </div>
      <p class="text-muted" style="margin-top:8px">{{ currentCase.description }}</p>

      <!-- 量表作答 -->
      <div class="data-section">
        <h4>📋 量表作答记录（合成数据，原始分）</h4>
        <div class="scale-answers">
          <div v-for="(answers, code) in currentCase.scale_answers" :key="code" class="scale-answer-item">
            <div class="sa-header">
              <strong>{{ code }}</strong>
              <span class="sa-raw">原始分: {{ sumAnswers(answers) }}</span>
            </div>
            <div class="sa-dots">
              <span v-for="(a, i) in answers" :key="i" class="sa-dot" :class="'opt' + a" :title="'第' + (i+1) + '题: ' + a + '分'">{{ a }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- E1-E12 前庭参数 -->
      <div class="data-section">
        <h4>📐 E1-E12 前庭参数 + K 值</h4>
        <div class="e-params">
          <div v-for="(v, k) in currentCase.e_params" :key="k" class="e-param-item">
            <span class="e-param-key">{{ k }}</span>
            <span class="e-param-val">{{ typeof v === 'number' ? v.toFixed(1) : v }}</span>
          </div>
        </div>
        <div class="k-value">
          <strong>K 值（前庭敏感指数）：{{ currentCase.k_value }}</strong>
          <span class="text-muted">主导量表：{{ currentCase.dominant_scale }}</span>
        </div>
      </div>

      <!-- 一键系统诊断 -->
      <div class="diagnosis-cta" v-if="!diagResult">
        <p class="text-muted">以上为该系统可获取的观测数据（真值已隐藏）。点击下方按钮，由诊断算法对这名被试执行自动诊断。</p>
        <button class="btn btn-primary" @click="runDiagnosis" :disabled="diagnosing">
          {{ diagnosing ? '诊断中...' : '⚡ 一键系统自动诊断' }}
        </button>
      </div>

      <!-- 系统诊断报告 -->
      <div class="diag-report" v-if="diagResult">
        <h4>🔬 系统自动诊断报告</h4>

        <!-- 诊断结论总览 -->
        <div class="diag-summary">
          <div class="diag-block scale-block">
            <span class="diag-label">量表综合等级</span>
            <strong class="diag-value" :class="'lv-' + diagResult.scale_diagnosis.overall_level">
              {{ diagResult.scale_diagnosis.overall_level_cn }}
            </strong>
          </div>
          <div class="diag-block emo-block">
            <span class="diag-label">情绪状态</span>
            <strong class="diag-value" :class="'emo-' + diagResult.emotion_diagnosis.emotion">
              {{ diagResult.emotion_diagnosis.emotion_cn }}
            </strong>
          </div>
          <div class="diag-block risk-block">
            <span class="diag-label">风险等级</span>
            <strong class="diag-value" :class="'risk-' + diagResult.risk_diagnosis.level">
              {{ diagResult.risk_diagnosis.level_cn }}
            </strong>
          </div>
        </div>

        <!-- 量表维度明细 -->
        <div class="diag-section">
          <h5>量表维度计分明细</h5>
          <table class="diag-table">
            <thead><tr><th>量表</th><th>标准分</th><th>等级</th></tr></thead>
            <tbody>
              <tr v-for="(v, code) in diagResult.scale_diagnosis.detail" :key="code">
                <td>{{ code }}</td>
                <td>{{ v.standard_score }}</td>
                <td><span class="lv-badge" :class="'lv-' + v.level">{{ levelCn(v.level) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 情绪判定依据 -->
        <div class="diag-section">
          <h5>情绪判定依据（E1-E12 前庭参数）</h5>
          <p class="diag-para">
            负性参数均值 <strong>{{ diagResult.emotion_diagnosis.neg_avg }}</strong>，正性参数均值
            <strong>{{ diagResult.emotion_diagnosis.pos_avg }}</strong>，K 值
            <strong>{{ diagResult.emotion_diagnosis.k_value }}</strong> →
            判定为「{{ diagResult.emotion_diagnosis.emotion_cn }}」
          </p>
        </div>

        <!-- 风险分级与干预建议 -->
        <div class="diag-section">
          <h5>风险分级与干预建议（综合分 {{ diagResult.risk_diagnosis.score }}/100）</h5>
          <div v-if="diagResult.risk_diagnosis.warning_flags.length" class="warning-box">
            <p v-for="(w, i) in diagResult.risk_diagnosis.warning_flags" :key="i">⚠️ {{ w }}</p>
          </div>
          <ul class="rec-list">
            <li v-for="(r, i) in diagResult.risk_diagnosis.recommendations" :key="i">{{ r }}</li>
          </ul>
        </div>

        <!-- 真值对照验证 -->
        <div class="diag-section truth-section">
          <h5>✅ 诊断准确性对照（真值验证）</h5>
          <div class="truth-row">
            <span>量表等级</span>
            <div>
              <span class="verdict" :class="diagResult.comparison.scale_level_match ? 'ok' : 'diff'">
                {{ diagResult.comparison.scale_level_match ? '一致' : '偏差' }}
              </span>
              系统判定「{{ diagResult.comparison.scale_level_cn }}」 / 真值「{{ diagResult.comparison.true_level_cn }}」
            </div>
          </div>
          <div class="truth-row">
            <span>情绪状态</span>
            <div>
              <span class="verdict" :class="diagResult.comparison.emotion_match ? 'ok' : 'diff'">
                {{ diagResult.comparison.emotion_match ? '一致' : '偏差' }}
              </span>
              系统判定「{{ diagResult.comparison.emotion_cn }}」 / 真值「{{ diagResult.comparison.true_emotion_cn }}」
            </div>
          </div>
          <p class="text-muted" style="margin-top:8px">说明：虚拟被试的观测数据由合成引擎生成（隐藏真值）。自动诊断从观测数据独立推断，与真值对照用于验证诊断算法的准确性。边界案例可能出现相邻等级偏差，属心理评估的正常现象。</p>
        </div>

        <button class="btn btn-primary" @click="reset" style="margin-top:16px">继续演示下一个</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import axios from "axios";

const profiles = ref([]);
const currentCase = ref(null);
const diagResult = ref(null);
const generating = ref(false);
const diagnosing = ref(false);

onMounted(async () => {
  try {
    const resp = await axios.get("/api/virtual-subjects/profiles");
    profiles.value = resp.data.data || [];
  } catch (e) {
    alert("加载剖面列表失败：" + (e.response?.data?.detail || e.message));
  }
});

async function generateCase(profileId) {
  generating.value = true;
  try {
    const resp = await axios.post("/api/virtual-subjects/generate", { profile_id: profileId });
    currentCase.value = resp.data.data;
    diagResult.value = null;
  } catch (e) {
    alert("生成虚拟被试失败：" + (e.response?.data?.detail || e.message));
  } finally {
    generating.value = false;
  }
}

async function runDiagnosis() {
  diagnosing.value = true;
  try {
    const resp = await axios.post("/api/virtual-subjects/auto-diagnose", {
      subject_id: currentCase.value.subject_id,
    });
    diagResult.value = resp.data.data;
  } catch (e) {
    alert("系统诊断失败：" + (e.response?.data?.detail || e.message));
  } finally {
    diagnosing.value = false;
  }
}

function reset() {
  currentCase.value = null;
  diagResult.value = null;
}

function sumAnswers(arr) { return arr.reduce((s, v) => s + v, 0); }
function levelCn(lv) {
  return { normal: "正常", mild: "轻度", moderate: "中度", severe: "重度" }[lv] || lv;
}
function severityOf(theta) {
  if (theta < 0) return "healthy";
  if (theta < 1) return "mild";
  if (theta < 2) return "moderate";
  return "severe";
}
function severityText(s) {
  return { healthy: "健康", mild: "轻度", moderate: "中度", severe: "重度" }[s] || s;
}
</script>

<style scoped>
.page-sub { color: var(--text-muted, #9e9e9e); font-size: 13px; }
.card { background: var(--card-bg, #fff); border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.text-muted { color: var(--text-muted, #9e9e9e); font-size: 13px; }
.btn { padding: 10px 20px; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; font-weight: 600; }
.btn-primary { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; }
.btn-cancel { background: var(--btn-cancel-bg, #e5e7eb); color: var(--btn-cancel-color, #374151); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.profile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-top: 16px; }
.profile-card { border: 1px solid var(--border, #e5e7eb); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 10px; background: var(--card-bg, #fff); transition: transform .15s, box-shadow .15s; }
.profile-card:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(99,102,241,0.12); }
.profile-card.healthy { border-left: 4px solid #10b981; }
.profile-card.mild { border-left: 4px solid #f59e0b; }
.profile-card.moderate { border-left: 4px solid #f97316; }
.profile-card.severe { border-left: 4px solid #ef4444; }
.profile-header { display: flex; justify-content: space-between; align-items: center; }
.severity-tag { font-size: 11px; padding: 2px 8px; border-radius: 6px; background: var(--tag-bg, #f3f4f6); color: var(--tag-color, #6b7280); }
.profile-desc { font-size: 13px; color: var(--text-muted, #6b7280); margin: 0; flex: 1; }
.profile-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag { font-size: 11px; padding: 2px 6px; background: rgba(99,102,241,0.12); color: #6366f1; border-radius: 6px; }

.data-section { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border, #f0f0f0); }
.data-section h4 { margin: 0 0 12px; font-size: 15px; }

.scale-answers { display: flex; flex-direction: column; gap: 12px; }
.scale-answer-item { background: var(--section-bg, #f9fafb); border-radius: 10px; padding: 12px; }
.sa-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.sa-raw { font-size: 13px; color: var(--text-muted, #6b7280); }
.sa-dots { display: flex; flex-wrap: wrap; gap: 4px; }
.sa-dot { width: 24px; height: 24px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; }
.sa-dot.opt1 { background: #d1fae5; color: #059669; }
.sa-dot.opt2 { background: #dbeafe; color: #2563eb; }
.sa-dot.opt3 { background: #fef3c7; color: #d97706; }
.sa-dot.opt4 { background: #fee2e2; color: #dc2626; }

.e-params { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; margin-bottom: 12px; }
.e-param-item { background: var(--section-bg, #f9fafb); border-radius: 8px; padding: 8px; text-align: center; }
.e-param-key { display: block; font-size: 11px; color: var(--text-muted, #6b7280); }
.e-param-val { display: block; font-size: 15px; font-weight: 600; color: #6366f1; margin-top: 2px; }
.k-value { display: flex; align-items: center; gap: 16px; padding: 10px 14px; background: rgba(99,102,241,0.1); border-radius: 8px; }

.diagnosis-cta { margin-top: 24px; padding: 18px; background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(139,92,246,0.08)); border: 1px dashed #6366f1; border-radius: 12px; text-align: center; }
.diagnosis-cta .btn { font-size: 15px; padding: 12px 28px; margin-top: 8px; }

.diag-report { margin-top: 24px; padding-top: 16px; border-top: 2px solid #6366f1; }
.diag-report h4 { margin: 0 0 16px; font-size: 16px; color: #6366f1; }

.diag-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.diag-block { background: var(--section-bg, #f9fafb); border-radius: 12px; padding: 16px; text-align: center; display: flex; flex-direction: column; gap: 6px; }
.diag-label { font-size: 12px; color: var(--text-muted, #6b7280); }
.diag-value { font-size: 22px; font-weight: 700; }
.lv-normal, .risk-low { color: #10b981; }
.lv-mild, .emo-neutral { color: #f59e0b; }
.lv-moderate, .emo-mild_negative, .risk-medium { color: #f97316; }
.lv-severe, .emo-severe_negative, .risk-high { color: #ef4444; }
.emo-positive { color: #10b981; }
.risk-extreme { color: #b91c1c; }

.diag-section { margin-top: 16px; }
.diag-section h5 { margin: 0 0 10px; font-size: 14px; color: var(--heading-color, #374151); }
.diag-para { font-size: 13px; color: var(--text, #4b5563); margin: 0; }
.diag-para strong { color: #6366f1; }

.diag-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.diag-table th, .diag-table td { padding: 8px 10px; border-bottom: 1px solid var(--border, #f0f0f0); text-align: left; }
.diag-table th { color: var(--text-muted, #6b7280); font-weight: 600; }
.lv-badge { padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
.lv-badge.lv-normal { background: #d1fae5; color: #059669; }
.lv-badge.lv-mild { background: #fef3c7; color: #d97706; }
.lv-badge.lv-moderate { background: #ffedd5; color: #ea580c; }
.lv-badge.lv-severe { background: #fee2e2; color: #dc2626; }

.warning-box { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; }
.warning-box p { margin: 4px 0; font-size: 13px; color: #b91c1c; }
.rec-list { margin: 0; padding-left: 18px; }
.rec-list li { font-size: 13px; color: var(--text, #4b5563); margin: 4px 0; }

.truth-section { background: var(--section-bg, #f9fafb); border-radius: 10px; padding: 14px; }
.truth-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; font-size: 14px; }
.truth-row > span { width: 72px; color: var(--text-muted, #6b7280); flex-shrink: 0; }
.verdict { padding: 2px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; margin-right: 8px; }
.verdict.ok { background: #d1fae5; color: #059669; }
.verdict.diff { background: #fef3c7; color: #d97706; }
</style>
