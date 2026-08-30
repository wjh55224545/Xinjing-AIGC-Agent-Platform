<template>
  <div>
    <h2>心理教学实验 · 前庭振动情绪测量</h2>
    <p class="text-muted">面向心理测量课程的实验组件：E1–E12 参数解释、个体 vs 常模（N=10,266）对照、实验报告生成</p>

    <!-- 数据源选择 -->
    <div class="card">
      <h3>实验数据源</h3>
      <div style="display:flex;gap:12px;align-items:center">
        <select v-model="studentId" style="padding:8px;font-size:14px">
          <option :value="0">全库最近记录</option>
          <option v-for="s in students" :key="s.id" :value="s.id">{{ s.name }}（{{ s.class_name }}）</option>
        </select>
        <button class="btn btn-primary" @click="loadRecord" :disabled="loading">{{ loading ? '加载中...' : '加载实验数据' }}</button>
        <span v-if="record && record.fused_emotion" class="badge">{{ record.fused_emotion }} · 融合分 {{ record.fused_score }}</span>
        <span v-if="record && record.demo" class="badge badge-demo">演示数据</span>
      </div>
      <p v-if="loadError" class="error">{{ loadError }}</p>
    </div>

    <!-- 实验指导书 -->
    <div class="card">
      <h3>📖 实验指导书</h3>
      <ol class="guide">
        <li><strong>实验目的</strong>：理解非侵入式前庭振动技术（VibraImage）测量情绪的心理学原理；掌握"客观生理测量 × 主观量表自评"的多模态评估范式。</li>
        <li><strong>实验设备</strong>：普通摄像头（≥720p）+ 心镜·VibraImage 引擎（支持国产 GPU 加速）。</li>
        <li><strong>实验程序</strong>：被试静坐平视摄像头约 30 秒 → 引擎逐帧分析头部微振动 → 输出 E1–E12 十二项参数与 K 值 → 被试完成量表自评 → 生成个体 vs 常模对照与交叉验证报告。</li>
        <li><strong>记录表</strong>：填写下表参数实测值、Z 分与课堂解读。</li>
        <li><strong>结果解释</strong>：Z 分 = (实测 − 常模均值) / 常模标准差；|Z| ≥ 1.5 提示偏离常模，值得课堂讨论。</li>
      </ol>
    </div>

    <!-- E1-E12 参数卡 + 常模雷达 -->
    <template v-if="record && normParams.length">
      <div class="card">
        <h3>🧩 E1–E12 参数解释卡（含个体 Z 分）</h3>
        <p v-if="record.demo" class="text-muted">当前为演示数据（基于常模均值生成），接入真实采集后显示实测值。</p>
        <div class="grid">
          <div v-for="p in normParams" :key="p.key" class="param-card" :class="p.group">
            <div class="param-name">{{ p.name_zh }}</div>
            <div class="param-key">{{ p.key }}</div>
            <div class="param-value">{{ fmt(record.e_params[p.key]) }}</div>
            <div class="param-z" :class="zClass(z(p))">Z = {{ fmt(z(p)) }}</div>
            <div class="param-group">{{ groupText(p.group) }}</div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3>📊 个体 vs 常模 雷达图（Z 分）</h3>
        <p class="text-muted">以常模为 0 基线，个体 Z 分 ±2 范围内；正值表示该参数高于常模。</p>
        <v-chart :option="radarOption" autoresize style="height:420px" />
      </div>

      <div class="card">
        <h3>🧭 情绪状态指数 K 值</h3>
        <div class="k-box">
          <span class="k-value">{{ fmt(record.k_value) }}</span>
          <span class="k-desc">{{ record.k_interpretation || '—' }}</span>
        </div>
        <div class="k-scale">
          <div class="k-band k-stable">|K|&lt;3 稳定</div>
          <div class="k-band k-attn">3≤|K|&lt;6 关注</div>
          <div class="k-band k-warn">|K|≥6 预警</div>
        </div>
      </div>

      <div class="card">
        <h3>📄 实验报告</h3>
        <p class="text-muted">一键生成符合心理测量课程规范的《情绪测量实验报告》（含实验目的/方法/结果/讨论/结论）。</p>
        <button class="btn btn-primary" @click="genReport" :disabled="reportLoading">
          {{ reportLoading ? '生成中...' : '生成实验报告' }}
        </button>
        <pre v-if="reportText" class="report">{{ reportText }}</pre>
      </div>
    </template>

    <div class="card" v-else-if="!loading && !loadError">
      <p class="text-muted">点击「加载实验数据」获取最近一条情绪记录用于教学演示；试点部署后可指定学生。</p>
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

const students = ref([]);
const studentId = ref(0);
const record = ref(null);
const norms = ref([]);
const normParams = ref([]);
const loading = ref(false);
const loadError = ref("");
const reportText = ref("");
const reportLoading = ref(false);

onMounted(async () => {
  try {
    const [st, nm] = await Promise.all([
      axios.get("/api/students"),
      axios.get("/api/vibraimage/norms"),
    ]);
    students.value = Array.isArray(st.data) ? st.data : ((st.data && st.data.data) || []);
    const normData = (nm.data && nm.data.data) || {};
    normParams.value = normData.params || [];
    await loadRecord();
  } catch (e) {
    loadError.value = (e.response && e.response.data && e.response.data.detail) || "加载失败（请确认后端已启动）";
  }
});

async function loadRecord() {
  loading.value = true;
  loadError.value = "";
  reportText.value = "";
  try {
    const url = studentId.value ? `/api/vibraimage/latest?student_id=${studentId.value}` : "/api/vibraimage/latest";
    const resp = await axios.get(url);
    if (!resp.data.success) {
      loadError.value = resp.data.detail || "暂无数据";
      record.value = null;
    } else {
      record.value = resp.data.data;
      record.value.demo = !!resp.data.demo;
    }
  } catch (e) {
    loadError.value = (e.response && e.response.data && e.response.data.detail) || "加载失败（请确认后端已启动）";
    record.value = null;
  } finally {
    loading.value = false;
  }
}

function z(p) {
  if (!record.value || record.value.e_params[p.key] == null) return 0;
  const v = record.value.e_params[p.key];
  const m = p.norm_mean, s = p.norm_sd;
  if (m == null || s == null || s === 0) return 0;
  return (v - m) / s;
}

const radarOption = computed(() => {
  const indicators = normParams.value.map(p => ({
    name: p.name_zh,
    max: 2.5,
    min: -2.5,
  }));
  const values = normParams.value.map(p => Math.max(-2.5, Math.min(2.5, z(p))));
  return {
    tooltip: {},
    legend: { bottom: 0, data: ["个体 Z 分"] },
    radar: {
      indicator: indicators,
      radius: "65%",
      axisName: { color: "#4b5563", fontSize: 11 },
      splitArea: { areaStyle: { color: ["#fafafa", "#f3f4f6"] } },
    },
    series: [{
      type: "radar",
      data: [{ value: values, name: "个体 Z 分", areaStyle: { color: "rgba(79,70,229,0.25)" }, lineStyle: { color: "#4f46e5" }, itemStyle: { color: "#4f46e5" } }],
    }],
  };
});

async function genReport() {
  if (!record.value) return;
  reportLoading.value = true;
  try {
    const resp = await axios.post("/api/aigc/report/experiment", {
      e_params: record.value.e_params,
      k_value: record.value.k_value,
      student_name: "被试-" + record.value.student_id,
    });
    reportText.value = resp.data.data.report_text;
  } catch (e) {
    alert(e.response?.data?.detail || "报告生成失败");
  } finally {
    reportLoading.value = false;
  }
}

function fmt(v) {
  if (v == null) return "—";
  return Number(v).toFixed(2);
}
function zClass(v) {
  return Math.abs(v) >= 1.5 ? "z-extreme" : "";
}
function groupText(g) {
  return { negative: "负性情绪参数", positive: "正性情绪参数", physiological: "生理状态参数" }[g] || "";
}
</script>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.text-muted { color: #9e9e9e; font-size: 13px; }
.btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-primary { background: #4f46e5; color: #fff; }
.error { color: #dc2626; font-size: 13px; margin-top: 8px; }
.badge { padding: 4px 10px; background: #e0e7ff; color: #4338ca; border-radius: 12px; font-size: 13px; }
.badge-demo { background: #fef3c7; color: #b45309; }
.guide li { margin: 8px 0; font-size: 14px; line-height: 1.7; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.param-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
.param-card.negative { border-left: 4px solid #ef4444; }
.param-card.positive { border-left: 4px solid #10b981; }
.param-card.physiological { border-left: 4px solid #3b82f6; }
.param-name { font-weight: 600; font-size: 14px; }
.param-key { font-size: 11px; color: #9e9e9e; }
.param-value { font-size: 22px; font-weight: bold; color: #1f2937; margin: 4px 0; }
.param-z { font-size: 13px; color: #6b7280; }
.param-z.z-extreme { color: #dc2626; font-weight: bold; }
.param-group { font-size: 11px; color: #9e9e9e; margin-top: 4px; }
.k-box { display: flex; align-items: center; gap: 16px; }
.k-value { font-size: 40px; font-weight: bold; color: #4f46e5; }
.k-desc { font-size: 14px; color: #374151; }
.k-scale { display: flex; gap: 8px; margin-top: 12px; }
.k-band { flex: 1; text-align: center; padding: 8px; border-radius: 6px; font-size: 13px; }
.k-stable { background: #d1fae5; color: #059669; }
.k-attn { background: #fef3c7; color: #d97706; }
.k-warn { background: #fee2e2; color: #dc2626; }
.report { background: #fafafa; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-top: 12px; white-space: pre-wrap; font-size: 13px; line-height: 1.7; max-height: 500px; overflow: auto; }
</style>
