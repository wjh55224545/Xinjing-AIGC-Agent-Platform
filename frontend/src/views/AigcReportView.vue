<template>
  <div>
    <h2>AIGC 内容生成</h2>

    <!-- 学生选择 -->
    <div class="card">
      <h3>1. 选择学生</h3>
      <div style="display:flex;gap:12px;align-items:center">
        <select v-model="selectedStudentId" style="padding:8px;font-size:14px;min-width:200px">
          <option :value="0" disabled>请选择学生...</option>
          <option v-for="s in students" :key="s.id" :value="s.id">
            {{ s.name }}（{{ s.class_name }}）
          </option>
        </select>
        <span v-if="selectedStudent" class="text-muted">
          基线情绪: {{ selectedStudent.baseline_mood }} |
          最近记录: {{ selectedStudent.emotion_count || 0 }}条
        </span>
      </div>
    </div>

    <!-- 一键生成 -->
    <div class="card">
      <h3>2. 生成报告</h3>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <button class="btn btn-primary" @click="autoGenerate('daily_report')" :disabled="!selectedStudentId || generating">
          {{ generating && activeCap === 'daily_report' ? '生成中...' : '📊 心理评估日报' }}
        </button>
        <button class="btn btn-primary" @click="autoGenerate('intervention_plan')" :disabled="!selectedStudentId || generating">
          {{ generating && activeCap === 'intervention_plan' ? '生成中...' : '📋 个性化干预方案' }}
        </button>
        <button class="btn btn-primary" @click="autoGenerate('parent_letter')" :disabled="!selectedStudentId || generating">
          {{ generating && activeCap === 'parent_letter' ? '生成中...' : '✉️ 家校沟通函' }}
        </button>
        <button class="btn btn-primary" @click="autoGenerate('growth_narrative')" :disabled="!selectedStudentId || generating">
          {{ generating && activeCap === 'growth_narrative' ? '生成中...' : '📈 成长叙事' }}
        </button>
      </div>
      <p class="text-muted" style="margin-top:8px">
        ⚡ 系统自动从数据库拉取最新情绪记录，无需手动填写数据
      </p>
    </div>

    <!-- 结果 -->
    <div class="card" v-if="result">
      <h3>3. 生成结果 <span class="tag">{{ result.generated_by }}</span></h3>
      <div class="report-text" v-html="renderedReport"></div>

      <!-- 日报专属操作：PDF 导出 + 多轮追问 -->
      <template v-if="result.report_type === 'daily'">
        <div class="row-actions" style="margin-top:14px">
          <button class="btn btn-success" @click="exportPdf" :disabled="exporting">
            {{ exporting ? '导出中...' : '⬇️ 导出 PDF 诊断报告' }}
          </button>
        </div>

        <div class="followup-box">
          <h4>❓ 对报告追问（多轮）</h4>
          <div class="chat" v-if="followups.length">
            <div v-for="(f, i) in followups" :key="i" class="msg">
              <div class="q"><b>追问：</b>{{ f.question }}</div>
              <div class="a" v-html="renderMarkdown(f.answer)"></div>
              <div class="meta">依据指标：{{ (f.evidence || []).map(e => e.metric).join('、') || '无' }}</div>
            </div>
          </div>
          <div class="input-row">
            <input v-model="question" placeholder="例如：为什么风险等级是黄色？积极情绪占比是怎么算的？"
              @keyup.enter="askFollowUp" :disabled="asking" />
            <button class="btn btn-primary" @click="askFollowUp" :disabled="asking || !question.trim()">
              {{ asking ? '回答中...' : '追问' }}
            </button>
          </div>
        </div>
      </template>
    </div>

    <!-- 错误 -->
    <div class="card error-card" v-if="errorMsg">
      <h3>⚠️ {{ errorMsg }}</h3>
      <p class="text-muted">请确保已为该学生上传视频并完成情绪分析</p>
    </div>

    <!-- 手动模式（折叠） -->
    <details style="margin-top:24px">
      <summary style="color:#78909C;cursor:pointer">🔧 高级：手动输入数据</summary>
      <div class="card" style="margin-top:8px">
        <textarea v-model="manualJson" rows="8" style="width:100%;font-family:monospace;font-size:12px"
          placeholder='手工填入完整 JSON（用于测试）'></textarea>
        <button class="btn btn-warning" @click="manualGenerate" :disabled="!manualJson.trim() || generating" style="margin-top:8px">
          手动发送
        </button>
      </div>
    </details>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import axios from "axios";

const students = ref([]);
const selectedStudentId = ref(0);
const generating = ref(false);
const activeCap = ref("");
const result = ref(null);
const errorMsg = ref("");
const manualJson = ref("");
const currentDate = ref(new Date().toISOString().split("T")[0]);
const analysisCache = ref(null);   // 最近一次自动拉取的分析结果（供追问证据链）
const followups = ref([]);
const question = ref("");
const asking = ref(false);
const exporting = ref(false);

const selectedStudent = computed(() =>
  students.value.find(s => s.id === selectedStudentId.value)
);

const renderedReport = computed(() => {
  if (!result.value?.report_text) return "";
  return renderMarkdown(result.value.report_text);
});

// 本地轻量 Markdown 渲染（无外部依赖，离线可用）
function renderMarkdown(text) {
  if (!text) return "";
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = String(text).split("\n");
  const html = [];
  let inList = false;
  const closeList = () => { if (inList) { html.push("</ul>"); inList = false; } };
  for (const raw of lines) {
    const line = esc(raw);
    const h3 = line.match(/^###\s+(.*)/);
    const h2 = line.match(/^##\s+(.*)/);
    const h1 = line.match(/^#\s+(.*)/);
    const li = line.match(/^[-*]\s+(.*)/);
    if (h1) { closeList(); html.push(`<h3>${h1[1]}</h3>`); }
    else if (h2) { closeList(); html.push(`<h4>${h2[1]}</h4>`); }
    else if (h3) { closeList(); html.push(`<h5>${h3[1]}</h5>`); }
    else if (li) { if (!inList) { html.push("<ul>"); inList = true; } html.push(`<li>${li[1]}</li>`); }
    else if (!line.trim()) { closeList(); }
    else {
      closeList();
      const bolded = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      html.push(`<p>${bolded}</p>`);
    }
  }
  closeList();
  return html.join("");
}

onMounted(async () => {
  try {
    const resp = await axios.get("/api/students");
    students.value = Array.isArray(resp.data) ? resp.data : (resp.data.data || []);
  } catch (e) {
    errorMsg.value = "无法加载学生列表";
  }
});

async function fetchAutoData() {
  const date = currentDate.value;
  const resp = await axios.post(
    `/api/aigc/report/daily/auto?student_id=${selectedStudentId.value}&date=${date}`
  );
  if (resp.data.success) {
    analysisCache.value = resp.data.data;
  }
  return resp;
}

async function autoGenerate(type) {
  if (!selectedStudentId.value) return;
  generating.value = true;
  activeCap.value = type;
  result.value = null;
  errorMsg.value = "";
  followups.value = [];

  try {
    const date = currentDate.value;
    const endpointMap = {
      daily_report: "/api/aigc/report/daily/auto",
      intervention_plan: "/api/aigc/plan/intervention",
      parent_letter: "/api/aigc/letter/parent",
      growth_narrative: "/api/aigc/narrative/growth",
    };

    if (type === "daily_report") {
      const resp = await axios.post(
        `${endpointMap[type]}?student_id=${selectedStudentId.value}&date=${date}`
      );
      if (resp.data.success) {
        result.value = resp.data.data;
        // 拉取分析结果供追问使用（同日自动接口）
        try {
          const auto = await fetchAutoData();
          result.value.analysis_result = auto.data.data?.analysis_result || null;
        } catch { /* 追问证据链可降级为空 */ }
      } else {
        errorMsg.value = resp.data?.detail || "生成失败";
      }
    } else {
      const autoResp = await fetchAutoData();
      if (!autoResp.data.success) {
        errorMsg.value = autoResp.data?.detail || "无法获取情绪数据";
        generating.value = false;
        return;
      }
      const autoData = autoResp.data.data;

      let body = {};
      if (type === "intervention_plan") {
        body = {
          student_name: autoData.student_name || selectedStudent.value.name,
          risk_level: autoData.risk_level || "green",
          risk_factors: autoData.analysis_result?.risk_factors || [],
          indicators: autoData.analysis_result?.indicators || {},
        };
      } else if (type === "parent_letter") {
        body = {
          student_name: autoData.student_name || selectedStudent.value.name,
          class_name: selectedStudent.value?.class_name || "",
          risk_level: autoData.risk_level || "green",
          emotion_summary: `${autoData.emotion_data?.fused_emotion || "平稳"}，综合评分${autoData.emotion_data?.fused_score || 0}`,
          suggestions: [],
        };
      } else if (type === "growth_narrative") {
        body = {
          student_name: autoData.student_name || selectedStudent.value.name,
          period_days: 30,
          historical_data: {},
        };
      }
      const resp = await axios.post(endpointMap[type], body);
      if (resp.data.success) {
        result.value = resp.data.data;
      } else {
        errorMsg.value = "生成失败";
      }
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || `生成失败: 学生暂无情绪数据`;
  } finally {
    generating.value = false;
  }
}

async function manualGenerate() {
  generating.value = true;
  result.value = null;
  errorMsg.value = "";
  try {
    const body = JSON.parse(manualJson.value);
    const resp = await axios.post("/api/aigc/report/daily", body);
    if (resp.data.success) {
      result.value = resp.data.data;
    } else {
      errorMsg.value = "生成失败";
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || "JSON 格式错误";
  } finally {
    generating.value = false;
  }
}

// ---- 方案五：PDF 导出 ----
async function exportPdf() {
  if (!selectedStudentId.value) return;
  exporting.value = true;
  try {
    const resp = await axios.get(
      `/api/aigc/report/${selectedStudentId.value}/${currentDate.value}/pdf`,
      { responseType: "blob" }
    );
    const blob = new Blob([resp.data], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `心镜诊断报告_${selectedStudent.value?.name || selectedStudentId.value}_${currentDate.value}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || "PDF 导出失败，请确认该学生当日有情绪数据";
  } finally {
    exporting.value = false;
  }
}

// ---- 方案四：多轮追问 ----
async function askFollowUp() {
  const q = question.value.trim();
  if (!q || asking.value || !result.value?.report_text) return;
  asking.value = true;
  try {
    const history = followups.value.flatMap(f => [
      { role: "user", content: f.question },
      { role: "assistant", content: f.answer },
    ]);
    const resp = await axios.post("/api/aigc/report/followup", {
      report_text: result.value.report_text,
      question: q,
      analysis_result: result.value.analysis_result || {},
      history,
    });
    if (resp.data.success) {
      followups.value.push({
        question: q,
        answer: resp.data.data.answer,
        evidence: resp.data.data.evidence || [],
        generated_by: resp.data.data.generated_by,
      });
      question.value = "";
    } else {
      errorMsg.value = "追问失败";
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || "追问失败";
  } finally {
    asking.value = false;
  }
}
</script>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.card h3 { margin: 0 0 12px; font-size: 16px; }
.btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-primary { background: #4f46e5; color: #fff; }
.btn-warning { background: #d97706; color: #fff; }
.btn-success { background: #16a34a; color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.tag { background: #e8eaf6; color: #4f46e5; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.text-muted { color: #9e9e9e; font-size: 13px; }
.report-text { background: #fafafa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 16px; max-height: 600px; overflow-y: auto; line-height: 1.8; }
.error-card { border: 1px solid #fca5a5; background: #fef2f2; }
.error-card h3 { color: #dc2626; }
.row-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.followup-box { margin-top: 18px; border-top: 1px solid #e5e7eb; padding-top: 14px; }
.followup-box h4 { margin: 0 0 10px; font-size: 15px; color: #374151; }
.chat { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.msg { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 12px; }
.msg .q { font-size: 13px; color: #374151; margin-bottom: 6px; }
.msg .a { font-size: 14px; line-height: 1.7; color: #111827; }
.msg .meta { font-size: 11px; color: #9ca3af; margin-top: 6px; }
.input-row { display: flex; gap: 10px; }
.input-row input { flex: 1; padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 14px; }
select { padding: 8px; font-size: 14px; min-width: 200px; border: 1px solid #e5e7eb; border-radius: 6px; }
</style>
