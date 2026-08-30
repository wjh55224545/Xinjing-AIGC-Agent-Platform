<template>
  <div>
    <h2>虚拟被试教学演练</h2>
    <p class="text-muted">参数化虚拟被试 + 学生诊断 + 自动批改：无需真实被试即可完成心理评估教学闭环</p>

    <!-- 步骤1：选择剖面 -->
    <div class="card" v-if="!currentCase">
      <h3>选择虚拟被试剖面</h3>
      <p class="text-muted">每个剖面对应一种典型心理状态，生成后仅显示学生可见数据（量表作答 + E1-E12 前庭参数），真值隐藏</p>
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
            {{ generating ? '生成中...' : '生成虚拟被试' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 步骤2：学生可见数据 + 诊断填写 -->
    <div class="card" v-if="currentCase && !gradeResult">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="margin:0">{{ currentCase.profile_name }} · {{ currentCase.subject_id }}</h3>
        <button class="btn btn-cancel" @click="reset">重新选择</button>
      </div>
      <p class="text-muted" style="margin-top:8px">{{ currentCase.description }}</p>

      <!-- 量表作答 -->
      <div class="data-section">
        <h4>📋 量表作答记录（原始分，未计算标准分/等级）</h4>
        <div class="scale-answers">
          <div v-for="(answers, code) in currentCase.scale_answers" :key="code" class="scale-answer-item">
            <div class="sa-header">
              <strong>{{ code }}</strong>
              <span class="sa-raw">原始分: {{ sumAnswers(answers) }} / {{ answers.length * 4 }}</span>
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
            <span class="e-param-val">{{ typeof v === 'number' ? v.toFixed(3) : v }}</span>
          </div>
        </div>
        <div class="k-value">
          <strong>K 值（前庭敏感指数）：{{ currentCase.k_value }}</strong>
          <span class="text-muted">主导量表：{{ currentCase.dominant_scale }}</span>
        </div>
      </div>

      <!-- 教学提示 -->
      <div class="data-section teaching-note">
        <h4>💡 教学提示</h4>
        <p>{{ currentCase.note }}</p>
        <p class="text-muted">{{ currentCase.teaching_note }}</p>
      </div>

      <!-- 学生诊断填写 -->
      <div class="diagnosis-section">
        <h4>✍ 你的诊断</h4>
        <div class="form-row">
          <label>量表等级判定：</label>
          <select v-model="diagnosis.level_judgment" class="form-select">
            <option value="" disabled>请选择</option>
            <option value="normal">正常</option>
            <option value="mild">轻度异常</option>
            <option value="moderate">中度异常</option>
            <option value="severe">重度异常</option>
          </select>
        </div>
        <div class="form-row">
          <label>情绪状态判定：</label>
          <select v-model="diagnosis.emotion_judgment" class="form-select">
            <option value="" disabled>请选择</option>
            <option value="positive">积极/开心</option>
            <option value="neutral">平静/中性</option>
            <option value="mild_negative">轻度负性</option>
            <option value="severe_negative">重度负性</option>
          </select>
        </div>
        <div class="form-row">
          <label>干预建议：</label>
          <textarea v-model="diagnosis.suggestion" class="form-textarea"
                    placeholder="根据量表作答、E1-E12 参数和 K 值，给出你的干预建议..." rows="3"></textarea>
        </div>
        <button class="btn btn-primary" @click="submitDiagnosis"
                :disabled="!diagnosis.level_judgment || !diagnosis.emotion_judgment || grading">
          {{ grading ? '批改中...' : '提交诊断' }}
        </button>
      </div>
    </div>

    <!-- 步骤3：批改结果 -->
    <div class="card" v-if="gradeResult">
      <h3>批改结果 · {{ gradeResult.profile_name }}</h3>
      <div class="grade-summary">
        <div class="grade-score" :class="gradeClass(gradeResult.total)">
          {{ gradeResult.total }}
          <span class="grade-label">总分 / 100</span>
        </div>
        <div class="grade-level">{{ gradeResult.grade }}</div>
      </div>

      <div class="breakdown">
        <h4>得分明细</h4>
        <div v-for="(v, k) in gradeResult.breakdown" :key="k" class="breakdown-row">
          <span>{{ k }}</span>
          <span :class="v >= maxOf(k) * 0.6 ? 'pass' : 'fail'">{{ v }} / {{ maxOf(k) }}</span>
        </div>
      </div>

      <div class="feedback-section">
        <h4>教师反馈</h4>
        <p v-for="(f, i) in gradeResult.feedback" :key="i" class="feedback-item">{{ f }}</p>
      </div>

      <div class="truth-section">
        <h4>正确答案（真值揭示）</h4>
        <div v-for="(v, k) in gradeResult.correct_answer" :key="k" class="truth-row">
          <span>{{ k }}：</span>
          <strong>{{ Array.isArray(v) ? v.join('、') : v }}</strong>
        </div>
      </div>

      <button class="btn btn-primary" @click="reset" style="margin-top:16px">再练一个</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import axios from "axios";

const profiles = ref([]);
const currentCase = ref(null);
const gradeResult = ref(null);
const generating = ref(false);
const grading = ref(false);
const diagnosis = ref({ level_judgment: "", emotion_judgment: "", suggestion: "" });

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
    gradeResult.value = null;
    diagnosis.value = { level_judgment: "", emotion_judgment: "", suggestion: "" };
  } catch (e) {
    alert("生成虚拟被试失败：" + (e.response?.data?.detail || e.message));
  } finally {
    generating.value = false;
  }
}

async function submitDiagnosis() {
  if (!diagnosis.value.level_judgment || !diagnosis.value.emotion_judgment) return;
  grading.value = true;
  try {
    const resp = await axios.post("/api/virtual-subjects/grade", {
      subject_id: currentCase.value.subject_id,
      level_judgment: diagnosis.value.level_judgment,
      emotion_judgment: diagnosis.value.emotion_judgment,
      suggestion: diagnosis.value.suggestion,
    });
    gradeResult.value = resp.data.data;
  } catch (e) {
    alert("批改失败：" + (e.response?.data?.detail || e.message));
  } finally {
    grading.value = false;
  }
}

function reset() {
  currentCase.value = null;
  gradeResult.value = null;
  diagnosis.value = { level_judgment: "", emotion_judgment: "", suggestion: "" };
}

function sumAnswers(arr) { return arr.reduce((s, v) => s + v, 0); }
function maxOf(k) {
  if (k.includes("量表")) return 40;
  if (k.includes("情绪")) return 30;
  return 30;
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
function gradeClass(s) {
  if (s >= 85) return "excellent";
  if (s >= 70) return "good";
  if (s >= 60) return "pass";
  return "poor";
}
</script>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.text-muted { color: #9e9e9e; font-size: 13px; }
.btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-primary { background: #4f46e5; color: #fff; }
.btn-cancel { background: #e5e7eb; color: #374151; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.profile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-top: 16px; }
.profile-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.profile-card.healthy { border-left: 4px solid #10b981; }
.profile-card.mild { border-left: 4px solid #f59e0b; }
.profile-card.moderate { border-left: 4px solid #f97316; }
.profile-card.severe { border-left: 4px solid #ef4444; }
.profile-header { display: flex; justify-content: space-between; align-items: center; }
.severity-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #f3f4f6; color: #6b7280; }
.profile-desc { font-size: 13px; color: #6b7280; margin: 0; flex: 1; }
.profile-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag { font-size: 11px; padding: 2px 6px; background: #eef2ff; color: #4f46e5; border-radius: 4px; }

.data-section { margin-top: 20px; padding-top: 16px; border-top: 1px solid #f0f0f0; }
.data-section h4 { margin: 0 0 12px; font-size: 15px; }

.scale-answers { display: flex; flex-direction: column; gap: 12px; }
.scale-answer-item { background: #f9fafb; border-radius: 8px; padding: 12px; }
.sa-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.sa-raw { font-size: 13px; color: #6b7280; }
.sa-dots { display: flex; flex-wrap: wrap; gap: 4px; }
.sa-dot { width: 24px; height: 24px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; }
.sa-dot.opt1 { background: #d1fae5; color: #059669; }
.sa-dot.opt2 { background: #dbeafe; color: #2563eb; }
.sa-dot.opt3 { background: #fef3c7; color: #d97706; }
.sa-dot.opt4 { background: #fee2e2; color: #dc2626; }

.e-params { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; margin-bottom: 12px; }
.e-param-item { background: #f9fafb; border-radius: 6px; padding: 8px; text-align: center; }
.e-param-key { display: block; font-size: 11px; color: #6b7280; }
.e-param-val { display: block; font-size: 15px; font-weight: 600; color: #4f46e5; margin-top: 2px; }
.k-value { display: flex; align-items: center; gap: 16px; padding: 10px 14px; background: #eef2ff; border-radius: 6px; }

.teaching-note { background: #fffbeb; border-radius: 8px; padding: 14px; }
.teaching-note p { margin: 4px 0; font-size: 13px; }

.diagnosis-section { margin-top: 24px; padding-top: 16px; border-top: 2px solid #4f46e5; }
.diagnosis-section h4 { margin: 0 0 16px; font-size: 15px; color: #4f46e5; }
.form-row { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 14px; }
.form-row label { width: 110px; font-size: 14px; padding-top: 8px; flex-shrink: 0; }
.form-select { padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; min-width: 200px; }
.form-textarea { flex: 1; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; font-family: inherit; resize: vertical; }

.grade-summary { display: flex; align-items: center; gap: 24px; padding: 20px; background: #f9fafb; border-radius: 8px; margin-bottom: 16px; }
.grade-score { font-size: 56px; font-weight: bold; display: flex; flex-direction: column; align-items: center; line-height: 1; }
.grade-score.excellent { color: #10b981; }
.grade-score.good { color: #3b82f6; }
.grade-score.pass { color: #f59e0b; }
.grade-score.poor { color: #ef4444; }
.grade-label { font-size: 13px; color: #9e9e9e; font-weight: normal; margin-top: 4px; }
.grade-level { font-size: 20px; font-weight: 600; color: #374151; }

.breakdown { margin-bottom: 16px; }
.breakdown h4 { margin: 0 0 10px; font-size: 14px; }
.breakdown-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.breakdown-row .pass { color: #10b981; font-weight: 600; }
.breakdown-row .fail { color: #ef4444; font-weight: 600; }

.feedback-section, .truth-section { margin-top: 16px; padding: 14px; background: #f9fafb; border-radius: 8px; }
.feedback-section h4, .truth-section h4 { margin: 0 0 10px; font-size: 14px; }
.feedback-item { font-size: 13px; color: #4b5563; margin: 4px 0; }
.truth-row { font-size: 14px; padding: 4px 0; }
.truth-row strong { color: #4f46e5; }
</style>
