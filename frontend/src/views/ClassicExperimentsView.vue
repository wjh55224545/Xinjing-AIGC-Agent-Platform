<template>
  <div>
    <h2>🧪 经典心理学实验</h2>
    <p class="text-muted">四个经典实验范式的在线实现：生成试次 → 逐题作答 → 自动分析（含文献依据的结果解释）</p>

    <!-- 实验类型选择 -->
    <div class="card">
      <div class="tabs">
        <button
          v-for="exp in experiments"
          :key="exp.type"
          class="tab"
          :class="{ active: expType === exp.type }"
          @click="switchExp(exp.type)"
        >
          {{ exp.name }}
        </button>
      </div>
      <p class="text-muted" style="margin-top:10px">{{ currentExp.desc }}</p>
      <p class="ref">文献依据：{{ currentExp.ref }}</p>
    </div>

    <!-- 实验区 -->
    <div class="card">
      <template v-if="!trials.length">
        <p class="text-muted">共 {{ trialsMeta.total || currentExp.defaultTrials }} 个试次，作答完成后自动生成分析报告。</p>
        <button class="btn btn-primary" @click="startExperiment" :disabled="running">
          {{ running ? "实验进行中..." : "开始实验" }}
        </button>
      </template>

      <template v-else-if="!finished">
        <div class="trial-bar">
          <span>第 {{ currentIndex + 1 }} / {{ trials.length }} 试次</span>
          <span class="progress">{{ progress }}%</span>
        </div>
        <div class="stimulus-area" :style="stimulusStyle">
          <!-- Stroop: 彩色词 -->
          <template v-if="expType === 'stroop'">
            <span :style="{ color: currentTrial.color_hex, fontSize: '72px', fontWeight: 800 }">
              {{ currentTrial.word_cn }}
            </span>
          </template>
          <!-- Flanker: 箭头 -->
          <template v-else-if="expType === 'flanker'">
            <div style="font-size:56px;letter-spacing:14px;user-select:none">
              <span style="color:#9ca3af">{{ arrowText(currentTrial.flankers) }}</span>
              <span style="color:#111827;font-weight:800">{{ arrowText(currentTrial.target) }}</span>
              <span style="color:#9ca3af">{{ arrowText(currentTrial.flankers) }}</span>
            </div>
          </template>
          <!-- Go/No-Go: 字母 -->
          <template v-else-if="expType === 'gonogo'">
            <span style="font-size:80px;font-weight:800;color:#111827">{{ currentTrial.stimulus }}</span>
            <div class="hint" v-if="currentTrial.is_go">Go 刺激 → 请按键</div>
            <div class="hint" v-else>No-Go 刺激 → 请抑制</div>
          </template>
          <!-- IAT: 词 + 类别 -->
          <template v-else-if="expType === 'iat'">
            <span style="font-size:48px;font-weight:700;color:#111827">{{ currentTrial.stimulus }}</span>
            <div class="hint">{{ currentTrial.block_type === "compatible" ? "相容配对：自我/积极 → 左，他人/消极 → 右" : "不相容配对：自我/消极 → 左，他人/积极 → 右" }}</div>
          </template>
        </div>
        <div class="answer-area">
          <!-- Stroop: 4 颜色按钮 -->
          <template v-if="expType === 'stroop'">
            <button
              v-for="(cn, key) in currentExp.answers"
              :key="key"
              class="btn answer"
              :style="{ background: colorHex(key), color: '#fff' }"
              @click="answer(key)"
            >{{ cn }}</button>
          </template>
          <!-- Flanker: 左右 -->
          <template v-else-if="expType === 'flanker'">
            <button class="btn answer" @click="answer('left')">← 左</button>
            <button class="btn answer" @click="answer('right')">→ 右</button>
          </template>
          <!-- Go/No-Go: 按键/抑制 -->
          <template v-else-if="expType === 'gonogo'">
            <button class="btn answer" @click="answer('go')">Go · 按键</button>
            <button class="btn answer" @click="answer('nogo')">No-Go · 抑制</button>
          </template>
          <!-- IAT: 左右 -->
          <template v-else-if="expType === 'iat'">
            <button class="btn answer" @click="answer('left')">← 左</button>
            <button class="btn answer" @click="answer('right')">→ 右</button>
          </template>
        </div>
      </template>

      <!-- 结果 -->
      <template v-else>
        <div class="result">
          <h3>📊 实验结果</h3>
          <div class="grid">
            <div v-for="(v, k) in resultMetrics" :key="k" class="metric">
              <div class="metric-name">{{ k }}</div>
              <div class="metric-value">{{ v }}</div>
            </div>
          </div>
          <div class="interp">{{ resultText }}</div>

          <!-- 群体对照：保存到班级 + 查看对照（方案三） -->
          <div class="group-box">
            <div class="input-row">
              <input v-model="groupClass" placeholder="输入班级名（如：高一(1)班），保存本次结果参与群体对照" />
              <button class="btn btn-primary" @click="saveToGroup" :disabled="savingGroup || !groupClass.trim()">
                {{ savingGroup ? '保存中...' : '💾 保存到群体对照' }}
              </button>
            </div>
            <p v-if="groupSaved" class="ok">✅ 已保存，可在下方「班级 vs 全校对照」查看群体画像</p>
          </div>

          <div class="row-actions">
            <button class="btn btn-primary" @click="reset">重新开始</button>
            <button class="btn" @click="exportReport">导出结果文本</button>
          </div>
        </div>
      </template>
    </div>

    <!-- 群体对照（方案三：班级 vs 全校，个体诊断+群体画像） -->
    <div class="card">
      <h3>📈 班级 vs 全校对照</h3>
      <p class="text-muted">
        把同一班级多次实验结果聚合为群体画像，与全校基准对照。依据：大学生心理风险筛查分层
        （Ebert et al., 2019, Depression and Anxiety）。
      </p>
      <div class="input-row" style="margin-bottom:10px">
        <input v-model="compareClass" placeholder="班级名（如：高一(1)班）" />
        <select v-model="compareType">
          <option value="stroop">Stroop</option>
          <option value="flanker">Flanker</option>
          <option value="gonogo">Go/No-Go</option>
          <option value="iat">IAT</option>
        </select>
        <button class="btn btn-primary" @click="loadGroupComparison" :disabled="!compareClass.trim()">查看对照</button>
      </div>
      <template v-if="comparison">
        <div class="grid">
          <div class="metric">
            <div class="metric-name">班级均值（n={{ comparison.class_stats.n }}）</div>
            <div class="metric-value">{{ comparison.class_stats.mean ?? '—' }}</div>
          </div>
          <div class="metric">
            <div class="metric-name">全校均值（n={{ comparison.school_stats.n }}）</div>
            <div class="metric-value">{{ comparison.school_stats.mean ?? '—' }}</div>
          </div>
          <div class="metric">
            <div class="metric-name">差值</div>
            <div class="metric-value">{{ comparison.delta ?? '—' }}</div>
          </div>
        </div>
        <div class="interp">{{ comparison.interpretation }}</div>
        <p v-if="comparison.sample_warning" class="warn">⚠️ {{ comparison.sample_warning }}</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import axios from "axios";

const experiments = [
  {
    type: "stroop", name: "Stroop 效应",
    desc: "测量词义自动加工对颜色命名的干扰（认知控制能力）。试次中判断「字的颜色」，忽略词义。",
    ref: "Stroop (1935); MacLeod (1991)",
    defaultTrials: 40,
    answers: { red: "红", blue: "蓝", green: "绿", yellow: "黄" },
  },
  {
    type: "flanker", name: "Flanker 任务",
    desc: "测量选择性注意与干扰抑制：判断中央箭头的方向，忽略两侧干扰箭头。",
    ref: "Eriksen & Eriksen (1974)",
    defaultTrials: 40,
  },
  {
    type: "gonogo", name: "Go/No-Go",
    desc: "测量反应抑制能力：对 Go 刺激按键，对 No-Go 刺激抑制反应。虚报率反映冲动控制。",
    ref: "Donders (1868); Newman & Kosson (1986)",
    defaultTrials: 40,
  },
  {
    type: "iat", name: "IAT 内隐联想测验",
    desc: "测量内隐自我态度联结（自我×积极/消极），输出 D 分数。",
    ref: "Greenwald, McGhee & Schwartz (1998); Greenwald et al. (2003)",
    defaultTrials: 32,
  },
];

const expType = ref("stroop");
const currentExp = computed(() => experiments.find(e => e.type === expType.value));
const trials = ref([]);
const answers = ref([]);
const currentIndex = ref(0);
const running = ref(false);
const finished = ref(false);
const resultText = ref("");
const resultMetrics = ref({});
const trialsMeta = ref({});
let startTime = 0;

// 群体对照（方案三）
const groupClass = ref("");
const savingGroup = ref(false);
const groupSaved = ref(false);
const compareClass = ref("");
const compareType = ref("stroop");
const comparison = ref(null);

function arrowText(d) { return d === "left" ? "←" : "→"; }
function colorHex(key) {
  return { red: "#ef4444", blue: "#3b82f6", green: "#10b981", yellow: "#f59e0b" }[key] || "#6b7280";
}

function switchExp(type) {
  if (running.value || finished.value) reset();
  expType.value = type;
}

async function startExperiment() {
  running.value = true;
  answers.value = [];
  currentIndex.value = 0;
  finished.value = false;
  try {
    let resp;
    if (expType.value === "stroop") {
      resp = await axios.get(`/api/experiments/stroop/trials?n_per_condition=20`);
    } else if (expType.value === "flanker") {
      resp = await axios.get(`/api/experiments/flanker/trials?n_per_condition=20`);
    } else if (expType.value === "gonogo") {
      resp = await axios.get(`/api/experiments/gonogo/trials?n_go=30&n_nogo=10`);
    } else {
      resp = await axios.get(`/api/experiments/iat/trials?n_per_block=16`);
    }
    trials.value = resp.data.data.trials;
    trialsMeta.value = resp.data.data;
    currentIndex.value = 0;
    startTime = Date.now();
  } catch (e) {
    alert(e.response?.data?.detail || "生成试次失败");
    running.value = false;
  }
}

const currentTrial = computed(() => trials.value[currentIndex.value] || {});
const progress = computed(() => (trials.value.length ? Math.round((currentIndex.value / trials.value.length) * 100) : 0));

const stimulusStyle = computed(() => {
  if (expType.value === "stroop") {
    return { background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "40px", textAlign: "center" };
  }
  return { background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "40px", textAlign: "center" };
});

function answer(chosen) {
  const t = currentTrial.value;
  const rt = Math.round(Date.now() - startTime);
  let correct;
  if (expType.value === "gonogo") {
    correct = (chosen === "go") === !!t.is_go;
    answers.value.push({
      trial_id: t.trial_id,
      is_go: t.is_go,
      rt: correct && !t.is_go ? null : rt,
      correct,
    });
  } else if (expType.value === "stroop") {
    correct = chosen === t.correct_answer;
    answers.value.push({ trial_id: t.trial_id, congruent: t.congruent, rt, correct });
  } else if (expType.value === "flanker") {
    correct = chosen === t.correct_answer;
    answers.value.push({ trial_id: t.trial_id, flanker_type: t.flanker_type, rt, correct });
  } else {
    correct = chosen === t.correct_answer;
    answers.value.push({ trial_id: t.trial_id, block_type: t.block_type, rt, correct });
  }
  currentIndex.value += 1;
  if (currentIndex.value >= trials.value.length) {
    submitAnalysis();
  } else {
    startTime = Date.now();
  }
}

async function submitAnalysis() {
  running.value = false;
  try {
    let resp;
    if (expType.value === "stroop") {
      resp = await axios.post("/api/experiments/stroop/analyze", { trials: answers.value });
      resultMetrics.value = {
        "Stroop 效应量": `${resp.data.data.stroop_effect} ms`,
        "一致条件反应时": `${resp.data.data.congruent_rt_mean} ms`,
        "不一致条件反应时": `${resp.data.data.incongruent_rt_mean} ms`,
        "总正确率": `${resp.data.data.accuracy}%`,
      };
    } else if (expType.value === "flanker") {
      resp = await axios.post("/api/experiments/flanker/analyze", { trials: answers.value });
      resultMetrics.value = {
        "Flanker 干扰效应": `${resp.data.data.flanker_effect} ms`,
        "一致条件反应时": `${resp.data.data.congruent_rt_mean} ms`,
        "不一致条件反应时": `${resp.data.data.incongruent_rt_mean} ms`,
        "总正确率": `${resp.data.data.accuracy}%`,
      };
    } else if (expType.value === "gonogo") {
      resp = await axios.post("/api/experiments/gonogo/analyze", { trials: answers.value });
      resultMetrics.value = {
        "Go 平均反应时": `${resp.data.data.go_rt_mean} ms`,
        "命中率": `${resp.data.data.hit_rate}%`,
        "虚报率": `${resp.data.data.false_alarm_rate}%`,
        "抑制正确率": `${resp.data.data.inhibition_score}%`,
      };
    } else {
      resp = await axios.post("/api/experiments/iat/analyze", { trials: answers.value });
      resultMetrics.value = {
        "IAT D 分数": resp.data.data.d_score,
        "相容反应时": `${resp.data.data.compatible_rt_mean} ms`,
        "不相容反应时": `${resp.data.data.incompatible_rt_mean} ms`,
        "总正确率": `${resp.data.data.accuracy}%`,
      };
    }
    resultText.value = resp.data.data.interpretation;
    finished.value = true;
  } catch (e) {
    alert(e.response?.data?.error || "分析失败");
    reset();
  }
}

function reset() {
  trials.value = [];
  answers.value = [];
  currentIndex.value = 0;
  running.value = false;
  finished.value = false;
  resultText.value = "";
  resultMetrics.value = {};
  groupSaved.value = false;
}

// ---- 方案三：保存到群体对照 / 查看班级对照 ----
async function saveToGroup() {
  savingGroup.value = true;
  groupSaved.value = false;
  try {
    // 复用最近一次分析结果（answers 仍保留），带班级名重新提交入库
    let resp;
    const params = { class_name: groupClass.value.trim() };
    if (expType.value === "stroop") {
      resp = await axios.post(`/api/experiments/stroop/analyze?class_name=${encodeURIComponent(groupClass.value.trim())}`, { trials: answers.value });
    } else if (expType.value === "flanker") {
      resp = await axios.post(`/api/experiments/flanker/analyze?class_name=${encodeURIComponent(groupClass.value.trim())}`, { trials: answers.value });
    } else if (expType.value === "gonogo") {
      resp = await axios.post(`/api/experiments/gonogo/analyze?class_name=${encodeURIComponent(groupClass.value.trim())}`, { trials: answers.value });
    } else {
      resp = await axios.post(`/api/experiments/iat/analyze?class_name=${encodeURIComponent(groupClass.value.trim())}`, { trials: answers.value });
    }
    if (resp.data.success) {
      groupSaved.value = true;
      compareClass.value = groupClass.value.trim();
      compareType.value = expType.value;
      await loadGroupComparison();
    } else {
      alert(resp.data.error || "保存失败");
    }
  } catch (e) {
    alert(e.response?.data?.detail || "保存失败");
  } finally {
    savingGroup.value = false;
  }
}

async function loadGroupComparison() {
  try {
    const resp = await axios.get(
      `/api/experiments/group-comparison?class_name=${encodeURIComponent(compareClass.value.trim())}&experiment_type=${compareType.value}`
    );
    comparison.value = resp.data.data;
  } catch (e) {
    alert(e.response?.data?.detail || "对照查询失败");
  }
}

function exportReport() {
  const lines = [
    `【${currentExp.value.name}】实验结果`,
    ...Object.entries(resultMetrics.value).map(([k, v]) => `${k}：${v}`),
    "",
    "结果解释：",
    resultText.value,
    "",
    `文献依据：${currentExp.value.ref}`,
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${expType.value}_实验报告.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.text-muted { color: #9e9e9e; font-size: 13px; }
.ref { font-size: 12px; color: #6b7280; margin-top: 6px; }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.tab { padding: 8px 16px; border: 1px solid #e5e7eb; border-radius: 20px; background: #fff; font-size: 14px; cursor: pointer; }
.tab.active { background: #4f46e5; color: #fff; border-color: #4f46e5; }
.btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-primary { background: #4f46e5; color: #fff; }
.trial-bar { display: flex; justify-content: space-between; font-size: 13px; color: #6b7280; margin-bottom: 12px; }
.stimulus-area { min-height: 180px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.hint { font-size: 13px; color: #6b7280; margin-top: 16px; }
.answer-area { display: flex; gap: 12px; justify-content: center; margin-top: 20px; flex-wrap: wrap; }
.answer { min-width: 96px; font-size: 15px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 14px 0; }
.metric { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; text-align: center; }
.metric-name { font-size: 12px; color: #6b7280; }
.metric-value { font-size: 20px; font-weight: 700; color: #1f2937; margin-top: 6px; }
.interp { background: #f5f3ff; border-left: 4px solid #4f46e5; padding: 14px; border-radius: 6px; font-size: 14px; line-height: 1.8; color: #374151; }
.row-actions { display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.group-box { margin-top: 14px; border-top: 1px solid #e5e7eb; padding-top: 12px; }
.input-row { display: flex; gap: 10px; flex-wrap: wrap; }
.input-row input { flex: 1; min-width: 220px; padding: 9px 12px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 13px; }
.input-row select { padding: 9px 12px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 13px; }
.ok { color: #16a34a; font-size: 13px; margin-top: 8px; }
.warn { color: #d97706; font-size: 13px; margin-top: 8px; }
</style>
