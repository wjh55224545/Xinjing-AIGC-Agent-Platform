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
import { marked } from "https://esm.sh/marked@12";
import axios from "axios";

const students = ref([]);
const selectedStudentId = ref(0);
const generating = ref(false);
const activeCap = ref("");
const result = ref(null);
const errorMsg = ref("");
const manualJson = ref("");

const selectedStudent = computed(() =>
  students.value.find(s => s.id === selectedStudentId.value)
);

const renderedReport = computed(() => {
  if (!result.value?.report_text) return "";
  try {
    return marked.parse(result.value.report_text);
  } catch { return result.value.report_text; }
});

onMounted(async () => {
  try {
    const resp = await axios.get("/api/students");
    students.value = Array.isArray(resp.data) ? resp.data : (resp.data.data || []);
  } catch (e) {
    errorMsg.value = "无法加载学生列表";
  }
});

async function autoGenerate(type) {
  if (!selectedStudentId.value) return;
  generating.value = true;
  activeCap.value = type;
  result.value = null;
  errorMsg.value = "";

  try {
    const date = new Date().toISOString().split("T")[0];
    const endpointMap = {
      daily_report: "/api/aigc/report/daily/auto",
      intervention_plan: "/api/aigc/plan/intervention",
      parent_letter: "/api/aigc/letter/parent",
      growth_narrative: "/api/aigc/narrative/growth",
    };

    if (type === "daily_report") {
      // 使用自动端点
      const resp = await axios.post(
        `${endpointMap[type]}?student_id=${selectedStudentId.value}&date=${date}`
      );
      if (resp.data.success) {
        result.value = resp.data.data;
      } else {
        errorMsg.value = resp.data?.detail || "生成失败";
      }
    } else {
      // 其他类型：先拉取自动数据再生成
      const autoResp = await axios.post(
        `/api/aigc/report/daily/auto?student_id=${selectedStudentId.value}&date=${date}`
      );
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
</script>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.card h3 { margin: 0 0 12px; font-size: 16px; }
.btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-primary { background: #4f46e5; color: #fff; }
.btn-warning { background: #d97706; color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.tag { background: #e8eaf6; color: #4f46e5; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.text-muted { color: #9e9e9e; font-size: 13px; }
.report-text { background: #fafafa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 16px; max-height: 600px; overflow-y: auto; line-height: 1.8; }
.error-card { border: 1px solid #fca5a5; background: #fef2f2; }
.error-card h3 { color: #dc2626; }
select { padding: 8px; font-size: 14px; min-width: 200px; border: 1px solid #e5e7eb; border-radius: 6px; }
</style>
