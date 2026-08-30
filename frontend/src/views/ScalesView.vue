<template>
  <div>
    <h2>心理量表自评</h2>
    <p class="text-muted">标准化心理量表：为 AI 情绪识别提供效度基准，形成"面部+前庭+量表"多模态评估体系</p>

    <!-- 选择量表 -->
    <div class="card" v-if="!selectedScale && !catScale">
      <h3>选择量表</h3>
      <div v-for="s in scaleList" :key="s.code" class="scale-item">
        <div class="scale-info">
          <strong>{{ s.name }} ({{ s.code }})</strong>
          <span class="scale-desc">{{ s.description }}</span>
        </div>
        <div class="scale-actions">
          <button class="btn btn-primary" @click="loadScale(s.code)">完整测评 ({{ s.question_count }}题)</button>
          <button class="btn btn-cat" @click="catStart(s.code)">CAT 简版</button>
        </div>
      </div>
    </div>

    <!-- 完整测评 -->
    <div class="card" v-if="selectedScale && !result">
      <h3>{{ selectedScale.name }} ({{ selectedScale.code }})</h3>
      <p>{{ selectedScale.description }}</p>
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <span v-for="(lbl,i) in selectedScale.options" :key="i" class="opt-tag">
          {{ i+1 }}={{ lbl }}
        </span>
      </div>

      <div v-for="(q,i) in selectedScale.questions" :key="q.id" class="question-row">
        <div class="q-num">{{ q.id }}</div>
        <div class="q-text">{{ q.text }}</div>
        <div class="q-opts">
          <label v-for="(lbl,oi) in selectedScale.options" :key="oi" :class="{ active: answers[i] === oi+1 }">
            <input type="radio" :name="'q'+q.id" :value="oi+1" v-model="answers[i]" />{{ oi+1 }}
          </label>
        </div>
      </div>

      <div style="display:flex;gap:12px;margin-top:16px">
        <select v-model="studentId" style="padding:8px;font-size:14px">
          <option value="0" disabled>选择学生</option>
          <option v-for="s in students" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <button class="btn btn-primary" @click="submit" :disabled="!studentId || submitting">
          {{ submitting ? '提交中...' : '提交自评' }}
        </button>
        <button class="btn btn-cancel" @click="selectedScale=null;answers=[]">取消</button>
      </div>
    </div>

    <!-- CAT 简版测验 -->
    <div class="card" v-if="catScale">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="margin:0">CAT 自适应简版 · {{ catScale.name }} ({{ catScale.code }})</h3>
        <button class="btn btn-cancel" @click="catExit" v-if="!catResult">退出</button>
      </div>
      <p class="text-muted">基于 IRT 3PL 模型按「最大信息量」逐题推送，通常仅需 {{ catScale.question_count }} 题的约 1/3 即可出结果</p>

      <!-- 进度 -->
      <div class="cat-progress" v-if="!catResult">
        <div class="cat-progress-bar" :style="{ width: (catAnswered.length / catMax) * 100 + '%' }"></div>
        <span class="cat-progress-text">已答 {{ catAnswered.length }} / 预计 {{ catMax }} 题</span>
      </div>

      <!-- 当前题目 -->
      <div class="cat-question" v-if="catQuestion && !catResult">
        <div class="cat-q-num">第 {{ catAnswered.length + 1 }} 题</div>
        <div class="cat-q-text">{{ catQuestion.text }}</div>
        <div class="cat-opts">
          <button
            v-for="(lbl,oi) in catOptions" :key="oi"
            class="cat-opt-btn" :class="{ active: catSelected === oi+1 }"
            @click="catAnswer(oi+1)">
            {{ oi+1 }}. {{ lbl }}
          </button>
        </div>
        <div class="cat-actions">
          <button class="btn btn-primary" @click="catSubmitAnswer" :disabled="!catSelected || catLoading">
            {{ catLoading ? '计算中...' : '确认作答' }}
          </button>
        </div>
      </div>

      <!-- CAT 结果 -->
      <div class="cat-result" v-if="catResult">
        <div class="result-main">
          <span class="score">{{ catResult.score_estimate.theta_index }}</span>
          <span class="score-label">能力指数（θ 映射 0-100）</span>
        </div>
        <div class="result-level" :class="catResult.score_estimate.level">
          趋势等级：{{ levelText(catResult.score_estimate.level) }}
        </div>
        <p class="cat-theta">θ 估计：{{ catResult.session.theta }}（SE={{ catResult.session.se }}），共作答 {{ catResult.session.answered_count }} 题</p>
        <p class="text-muted">{{ catResult.score_estimate.note }}</p>
        <button class="btn btn-primary" @click="catExit" style="margin-top:12px">完成</button>
      </div>
    </div>

    <!-- 完整测评结果 -->
    <div class="card" v-if="result">
      <h3>测评结果</h3>
      <div class="result-box">
        <div class="result-main">
          <span class="score">{{ result.standard_score }}</span>
          <span class="score-label">标准分</span>
        </div>
        <div class="result-level" :class="result.level">
          等级：{{ levelText(result.level) }}
        </div>
        <div class="result-dims" v-if="Object.keys(result.dimension_scores||{}).length > 0">
          <h4>维度得分</h4>
          <div v-for="(v,k) in result.dimension_scores" :key="k" class="dim-row">
            <span class="dim-name">{{ k }}</span>
            <span class="dim-bar" :style="{width:v*50+'px',background:v>2?'#ef4444':v>1.5?'#f59e0b':'#10b981'}"></span>
            <span>{{ v }}</span>
          </div>
        </div>
      </div>
      <button class="btn btn-primary" @click="selectedScale=null;result=null;answers=[]" style="margin-top:12px">
        再做一次
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import axios from "axios";

const scaleList = ref([]);
const selectedScale = ref(null);
const students = ref([]);
const answers = ref([]);
const studentId = ref(0);
const result = ref(null);
const submitting = ref(false);

// CAT 状态
const catScale = ref(null);
const catQuestion = ref(null);
const catOptions = ref([]);
const catAnswered = ref([]);   // [{id, score}]
const catSelected = ref(0);
const catMax = ref(10);
const catResult = ref(null);
const catLoading = ref(false);

onMounted(async () => {
  const [sl, st] = await Promise.all([
    axios.get("/api/scales/list/all"),
    axios.get("/api/students"),
  ]);
  scaleList.value = sl.data.data;
  students.value = Array.isArray(st.data) ? st.data : (st.data.data || []);
});

async function loadScale(code) {
  const resp = await axios.get(`/api/scales/${code}`);
  selectedScale.value = resp.data.data;
  answers.value = new Array(selectedScale.value.questions.length).fill(0);
  result.value = null;
}

async function catStart(code) {
  const resp = await axios.post("/api/scales/cat/start", { scale_type: code });
  const d = resp.data.data;
  catScale.value = d;
  catOptions.value = d.options;
  catMax.value = d.session.max_items;
  catQuestion.value = d.question;
  catAnswered.value = [];
  catSelected.value = 0;
  catResult.value = null;
}

async function catSubmitAnswer() {
  if (!catSelected.value) return;
  catLoading.value = true;
  try {
    // 带上当前题答案，交由后端估计并推下一题
    const answered = [...catAnswered.value, { id: catQuestion.value.id, score: catSelected.value }];
    const resp = await axios.post("/api/scales/cat/next", {
      scale_type: catScale.value.code,
      answered,
    });
    const d = resp.data.data;
    if (d.done) {
      catResult.value = d;
      catQuestion.value = null;
    } else {
      catQuestion.value = d.question;
      catAnswered.value = answered;
      catMax.value = d.session.max_items;
    }
    catSelected.value = 0;
  } catch (e) {
    alert(e.response?.data?.detail || "CAT 请求失败");
  } finally {
    catLoading.value = false;
  }
}

function catExit() {
  catScale.value = null;
  catQuestion.value = null;
  catAnswered.value = [];
  catSelected.value = 0;
  catResult.value = null;
}

function levelText(lv) {
  const map = { normal: "正常", mild: "轻度异常", moderate: "中度异常", severe: "偏重" };
  return map[lv] || lv;
}

async function submit() {
  submitting.value = true;
  try {
    const resp = await axios.post("/api/scales/submit", {
      student_id: studentId.value,
      scale_type: selectedScale.value.code,
      answers: answers.value,
    });
    result.value = resp.data.data;
  } catch (e) {
    alert(e.response?.data?.detail || "提交失败");
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.text-muted { color: #9e9e9e; font-size: 13px; }
.btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-primary { background: #4f46e5; color: #fff; }
.btn-cancel { background: #e5e7eb; color: #374151; }
.btn-cat { background: #0ea5e9; color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.scale-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0; gap: 12px; }
.scale-info { display: flex; flex-direction: column; }
.scale-desc { font-size: 12px; color: #9e9e9e; margin-top: 2px; }
.scale-actions { display: flex; gap: 8px; flex-shrink: 0; }
.opt-tag { padding: 2px 8px; background: #e8eaf6; border-radius: 4px; font-size: 12px; color: #4f46e5; }
.question-row { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.q-num { width: 28px; height: 28px; border-radius: 50%; background: #4f46e5; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; flex-shrink: 0; }
.q-text { flex: 1; font-size: 14px; }
.q-opts { display: flex; gap: 8px; }
.q-opts label { cursor: pointer; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.q-opts label.active { background: #4f46e5; color: #fff; }
.q-opts input { display: none; }
.result-box { background: #fafafa; border-radius: 8px; padding: 20px; text-align: center; }
.result-main .score { font-size: 48px; font-weight: bold; color: #4f46e5; }
.score-label { font-size: 14px; color: #9e9e9e; margin-left: 8px; }
.result-level { margin-top: 8px; padding: 4px 12px; border-radius: 4px; display: inline-block; font-size: 14px; }
.result-level.normal { background: #d1fae5; color: #059669; }
.result-level.mild { background: #fef3c7; color: #d97706; }
.result-level.moderate { background: #ffedd5; color: #ea580c; }
.result-level.severe { background: #fee2e2; color: #dc2626; }
.result-dims { text-align: left; margin-top: 16px; }
.result-dims h4 { margin: 0 0 8px; }
.dim-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.dim-name { width: 120px; }
.dim-bar { height: 12px; border-radius: 6px; display: inline-block; min-width: 4px; transition: width 0.3s; }
/* CAT 样式 */
.cat-progress { height: 8px; background: #e5e7eb; border-radius: 4px; margin: 12px 0; position: relative; }
.cat-progress-bar { height: 8px; background: #0ea5e9; border-radius: 4px; transition: width 0.3s; }
.cat-progress-text { position: absolute; right: 0; top: -18px; font-size: 12px; color: #9e9e9e; }
.cat-question { padding: 16px 0; border-top: 1px solid #f0f0f0; }
.cat-q-num { font-size: 12px; color: #0ea5e9; margin-bottom: 8px; }
.cat-q-text { font-size: 16px; font-weight: 600; margin-bottom: 16px; }
.cat-opts { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
.cat-opt-btn { padding: 10px 18px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; cursor: pointer; font-size: 14px; }
.cat-opt-btn.active { border-color: #0ea5e9; background: #e0f2fe; color: #0369a1; }
.cat-actions { display: flex; gap: 8px; }
.cat-theta { margin-top: 12px; font-size: 13px; color: #6b7280; }
</style>
