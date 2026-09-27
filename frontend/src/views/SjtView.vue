<template>
  <div>
    <h2>情境判断测验 · SJT</h2>
    <p class="page-sub">
      以校园真实压力情境呈现行为倾向型 SJT（选"最可能做"而非"最应该做"），
      评估考试焦虑、学业压力、同伴冲突、社交回避、情绪调节、求助意愿六个维度的应对倾向。
      依据：Weekley &amp; Jones (1999)；Webster et al. (2020) 元分析 pooled r=0.32；Harenbrock et al. (2023) 重测信度 pooled r=0.698。
    </p>

    <!-- 模式选择：真实作答 / 虚拟被试合成评估 -->
    <div class="card">
      <h3>① 选择测验方式</h3>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <button class="btn btn-primary" @click="mode='manual'" :class="{active: mode==='manual'}">手动作答（自己测）</button>
        <button class="btn" :class="{active: mode==='virtual'}" @click="mode='virtual'">虚拟被试合成评估</button>
      </div>
      <p class="text-muted" style="margin-top:10px">
        <template v-if="mode==='manual'">逐题作答后提交，系统按维度计分并给出应对倾向画像。</template>
        <template v-else>选择一种虚拟被试剖面，系统按其潜在特质生成贴合严重程度的作答并评估（合成数据，用于对照演示）。</template>
      </p>
    </div>

    <!-- 虚拟模式：选择剖面 -->
    <div class="card" v-if="mode==='virtual' && !virtualResult">
      <h3>② 选择虚拟被试剖面</h3>
      <div class="profile-grid">
        <div v-for="p in profiles" :key="p.id" class="profile-card" :class="severityOf(p.theta)">
          <div class="profile-header">
            <strong>{{ p.name }}</strong>
            <span class="severity-tag">{{ severityText(severityOf(p.theta)) }}</span>
          </div>
          <p class="profile-desc">{{ p.description }}</p>
          <div class="profile-tags"><span class="tag">θ={{ p.theta }}</span></div>
          <button class="btn btn-primary" @click="runVirtual(p.id)" :disabled="virtualLoading">
            {{ virtualLoading ? '评估中...' : '生成合成作答并评估' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 虚拟结果 -->
    <div class="card" v-if="virtualResult">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="margin:0">虚拟被试评估 · {{ virtualResult.profile_name }}</h3>
        <button class="btn btn-cancel" @click="virtualResult=null">重新选择</button>
      </div>
      <sjt-result :data="virtualResult"></sjt-result>
    </div>

    <!-- 手动模式：作答 -->
    <div class="card" v-if="mode==='manual'">
      <h3>② 逐题作答</h3>
      <p class="text-muted">{{ bank.instruction }}</p>
      <div v-if="bank.questions && bank.questions.length">
        <div v-for="(q, qi) in bank.questions" :key="q.id" class="sjt-item">
          <div class="sjt-q-head">
            <span class="sjt-q-no">{{ qi + 1 }}</span>
            <span class="sjt-q-dim">{{ bank.dimensions[q.dimension] }}</span>
          </div>
          <p class="sjt-scenario">{{ q.scenario }}</p>
          <div class="sjt-options">
            <label v-for="(opt, oi) in q.options" :key="oi" class="sjt-option"
                   :class="{selected: answers[q.id] === oi}">
              <input type="radio" :name="'q'+q.id" :value="oi" v-model="answers[q.id]" />
              <span class="opt-letter">{{ 'ABCD'[oi] }}</span>
              <span>{{ opt }}</span>
            </label>
          </div>
        </div>
        <div class="sjt-actions">
          <span class="text-muted" :class="{warn: answeredCount < bank.questions_count}">
            已作答 {{ answeredCount }} / {{ bank.questions_count }}
          </span>
          <button class="btn btn-primary" @click="submitAnswers" :disabled="submitLoading || answeredCount < bank.questions_count">
            {{ submitLoading ? '提交中...' : '提交并生成应对画像' }}
          </button>
        </div>
      </div>
      <p v-else class="text-muted">题库加载中...</p>
    </div>

    <!-- 手动结果 -->
    <div class="card" v-if="manualResult">
      <h3>③ 应对倾向画像</h3>
      <sjt-result :data="manualResult"></sjt-result>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import axios from "axios";
import SjtResult from "../components/SjtResult.vue";

const mode = ref("manual");
const bank = ref({});
const profiles = ref([]);
const answers = reactive({});
const manualResult = ref(null);
const virtualResult = ref(null);
const submitLoading = ref(false);
const virtualLoading = ref(false);

const answeredCount = computed(() => Object.keys(answers).filter(k => answers[k] !== undefined && answers[k] !== null).length);

onMounted(async () => {
  try {
    const [qResp, pResp] = await Promise.all([
      axios.get("/api/sjt/questions"),
      axios.get("/api/virtual-subjects/profiles"),
    ]);
    bank.value = qResp.data.data || {};
    profiles.value = pResp.data.data || [];
    // 初始化答案
    if (bank.value.questions) {
      bank.value.questions.forEach(q => { answers[q.id] = undefined; });
    }
  } catch (e) {
    alert("加载题库失败：" + (e.response?.data?.detail || e.message));
  }
});

async function submitAnswers() {
  submitLoading.value = true;
  try {
    const payload = Object.entries(answers)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([id, choice]) => ({ id: Number(id), choice }));
    const resp = await axios.post("/api/sjt/submit", { answers: payload });
    manualResult.value = resp.data.data;
  } catch (e) {
    alert("提交失败：" + (e.response?.data?.detail || e.message));
  } finally {
    submitLoading.value = false;
  }
}

async function runVirtual(profileId) {
  virtualLoading.value = true;
  try {
    const resp = await axios.post("/api/sjt/assess", { profile_id: profileId, seed: 42 });
    virtualResult.value = resp.data.data;
  } catch (e) {
    alert("虚拟评估失败：" + (e.response?.data?.detail || e.message));
  } finally {
    virtualLoading.value = false;
  }
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
.btn.active { outline: 2px solid #6366f1; outline-offset: 2px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.profile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; margin-top: 16px; }
.profile-card { border: 1px solid var(--border, #e5e7eb); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 10px; background: var(--card-bg, #fff); }
.profile-card.healthy { border-left: 4px solid #10b981; }
.profile-card.mild { border-left: 4px solid #f59e0b; }
.profile-card.moderate { border-left: 4px solid #f97316; }
.profile-card.severe { border-left: 4px solid #ef4444; }
.profile-header { display: flex; justify-content: space-between; align-items: center; }
.severity-tag { font-size: 11px; padding: 2px 8px; border-radius: 6px; background: var(--tag-bg, #f3f4f6); color: var(--tag-color, #6b7280); }
.profile-desc { font-size: 13px; color: var(--text-muted, #6b7280); margin: 0; flex: 1; }
.profile-tags { display: flex; gap: 4px; }
.tag { font-size: 11px; padding: 2px 6px; background: rgba(99,102,241,0.12); color: #6366f1; border-radius: 6px; }

.sjt-item { border: 1px solid var(--border, #e5e7eb); border-radius: 12px; padding: 16px; margin-bottom: 14px; }
.sjt-q-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.sjt-q-no { width: 26px; height: 26px; border-radius: 50%; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; }
.sjt-q-dim { font-size: 11px; padding: 2px 8px; background: rgba(99,102,241,0.12); color: #6366f1; border-radius: 6px; }
.sjt-scenario { font-size: 15px; font-weight: 600; color: var(--heading-color, #1f2937); margin: 0 0 12px; line-height: 1.6; }
.sjt-options { display: flex; flex-direction: column; gap: 8px; }
.sjt-option { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border: 1px solid var(--border, #e5e7eb); border-radius: 10px; cursor: pointer; font-size: 14px; transition: all .12s; }
.sjt-option:hover { border-color: #6366f1; background: rgba(99,102,241,0.04); }
.sjt-option.selected { border-color: #6366f1; background: rgba(99,102,241,0.1); }
.sjt-option input { display: none; }
.opt-letter { width: 24px; height: 24px; border-radius: 6px; background: var(--tag-bg, #f3f4f6); color: var(--tag-color, #6b7280); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }
.sjt-option.selected .opt-letter { background: #6366f1; color: #fff; }
.sjt-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; }
.warn { color: #d97706; }
</style>
