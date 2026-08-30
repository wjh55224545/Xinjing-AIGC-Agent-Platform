<template>
  <div>
    <!-- 筛选区 -->
    <div class="card">
      <h3>学生情绪监测</h3>
      <div class="filter-bar">
        <select v-model="selectedId" @change="load">
          <option v-for="s in students" :key="s.id" :value="s.id">{{ s.name }} ({{ s.student_code }})</option>
        </select>
        <input type="date" v-model="dateStr" @change="loadTimeline" />
        <button class="btn btn-primary" @click="onTrigger">触发采集</button>
        <button class="btn btn-secondary" @click="runForecast" :disabled="!emotionSeries.length">
          📈 趋势预测
        </button>
      </div>
    </div>

    <!-- 情绪时间线 -->
    <div class="card">
      <h3>{{ dateStr }} 情绪时间线</h3>
      <EmotionTrendChart v-if="timeline.length" :data="timelineData" timeMode class="chart-box" />
      <p v-else class="text-muted text-center" style="padding:40px 0">暂无数据，请先触发采集或选择其他日期</p>
    </div>

    <!-- 情绪趋势预测 + 异常检测 -->
    <div class="card" v-if="forecastResult">
      <h3>📈 情绪趋势预测与异常检测</h3>

      <!-- 预测概览 -->
      <div class="stat-grid" style="margin-bottom:20px">
        <div class="stat-card">
          <div class="label">趋势方向</div>
          <div class="value" :class="forecastResult.forecast.trend_slope > 0.005 ? 'green' : forecastResult.forecast.trend_slope < -0.005 ? 'red' : ''">
            {{ forecastResult.forecast.trend_direction }}
          </div>
          <div class="sub">斜率: {{ forecastResult.forecast.trend_slope }}</div>
        </div>
        <div class="stat-card">
          <div class="label">预测步数</div>
          <div class="value">{{ forecastResult.forecast.values.length }}</div>
          <div class="sub">置信度 {{ (forecastResult.forecast.confidence * 100).toFixed(0) }}%</div>
        </div>
        <div class="stat-card">
          <div class="label">情绪突变点</div>
          <div class="value" :class="forecastResult.anomalies.point_anomalies.length ? 'red' : 'green'">
            {{ forecastResult.anomalies.point_anomalies.length }}
          </div>
          <div class="sub">{{ forecastResult.anomalies.point_anomalies.length ? '检测到突变' : '无突变' }}</div>
        </div>
        <div class="stat-card">
          <div class="label">情绪漂移段</div>
          <div class="value" :class="forecastResult.anomalies.drift_anomalies.length ? 'yellow' : 'green'">
            {{ forecastResult.anomalies.drift_anomalies.length }}
          </div>
          <div class="sub">{{ forecastResult.anomalies.drift_anomalies.length ? '检测到漂移' : '无漂移' }}</div>
        </div>
      </div>

      <!-- 预测曲线 -->
      <div class="forecast-chart">
        <h4>未来 {{ forecastResult.forecast.values.length }} 步预测（含置信区间）</h4>
        <div class="forecast-bars">
          <div class="forecast-bar" v-for="(v, i) in forecastResult.forecast.values" :key="i">
            <div class="bar-conf" :style="{
              height: ((forecastResult.forecast.upper[i] - forecastResult.forecast.lower[i]) * 160) + 'px',
              bottom: (forecastResult.forecast.lower[i] * 160) + 'px'
            }"></div>
            <div class="bar-value" :style="{
              height: (v * 160) + 'px',
              background: v > 0.6 ? 'linear-gradient(180deg,#10b981,#34d399)' : v > 0.4 ? 'linear-gradient(180deg,#f59e0b,#fbbf24)' : 'linear-gradient(180deg,#ef4444,#f87171)'
            }"></div>
            <span class="bar-label">+{{ i + 1 }}</span>
            <span class="bar-val">{{ v.toFixed(2) }}</span>
          </div>
        </div>
        <div class="forecast-legend">
          <span><i class="dot green"></i>积极 (≥0.6)</span>
          <span><i class="dot yellow"></i>中性 (0.4-0.6)</span>
          <span><i class="dot red"></i>负性 (<0.4)</span>
          <span><i class="dot conf"></i>置信区间</span>
        </div>
      </div>

      <!-- 异常详情 -->
      <div class="anomaly-detail" v-if="forecastResult.anomalies.point_anomalies.length || forecastResult.anomalies.drift_anomalies.length">
        <h4>⚠️ 异常检测详情</h4>
        <div class="alert warning" v-if="forecastResult.anomalies.point_anomalies.length">
          检测到 {{ forecastResult.anomalies.point_anomalies.length }} 个情绪突变点（位置: {{ forecastResult.anomalies.point_anomalies.join(', ') }}），建议关注这些时间点的情绪波动。
        </div>
        <div class="alert danger" v-if="forecastResult.anomalies.drift_anomalies.length">
          检测到 {{ forecastResult.anomalies.drift_anomalies.length }} 段情绪持续漂移（起始位置: {{ forecastResult.anomalies.drift_anomalies.join(', ') }}），可能存在情绪状态的持续性变化，建议进一步评估。
        </div>
      </div>

      <!-- 风险提示 -->
      <div class="alert info" v-if="forecastResult.summary.warnings.length">
        <strong>智能提示：</strong>
        <ul style="margin-top:6px;padding-left:20px">
          <li v-for="(w, i) in forecastResult.summary.warnings" :key="i">{{ w }}</li>
        </ul>
      </div>
    </div>

    <!-- 近期记录 -->
    <div class="card">
      <h3>近期记录</h3>
      <table>
        <thead><tr><th>时间</th><th>面部情绪</th><th>置信度</th><th>K系数</th><th>综合情绪</th><th>得分</th></tr></thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td>{{ r.recorded_at }}</td><td>{{ r.facial_emotion }}</td><td>{{ r.facial_conf }}</td>
            <td>{{ r.vestibular_valence?.toFixed(2) }}</td><td>{{ r.fused_emotion }}</td><td>{{ r.fused_score }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!records.length" class="text-muted text-center" style="padding:24px 0">暂无记录</p>
    </div>

    <SseStream v-if="runId" :runId="runId" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import axios from "axios";
import { fetchStudents, fetchRecentEmotions, fetchEmotionTimeline, triggerInner } from "../api";
import EmotionTrendChart from "../components/charts/EmotionTrendChart.vue";
import SseStream from "../components/common/SseStream.vue";

const students = ref([]);
const selectedId = ref(null);
const dateStr = ref(new Date().toISOString().slice(0, 10));
const records = ref([]);
const timeline = ref([]);
const runId = ref("");
const forecastResult = ref(null);

const timelineData = computed(() =>
  timeline.value.map(r => ({ date: r.recorded_at, avg_score: r.fused_score }))
);

// 从近期记录中提取情绪得分序列（用于预测）
const emotionSeries = computed(() =>
  records.value.map(r => typeof r.fused_score === "number" ? r.fused_score / 100 : 0.5).slice(-20)
);

onMounted(async () => {
  students.value = await fetchStudents();
  if (students.value.length) { selectedId.value = students.value[0].id; await load(); }
});

async function load() {
  if (!selectedId.value) return;
  records.value = await fetchRecentEmotions(selectedId.value);
  await loadTimeline();
  forecastResult.value = null;
}

async function loadTimeline() {
  if (!selectedId.value) return;
  timeline.value = await fetchEmotionTimeline(selectedId.value, dateStr.value);
}

async function runForecast() {
  if (!emotionSeries.value.length) return;
  try {
    const resp = await axios.post("/api/emotion/forecast", {
      series: emotionSeries.value,
      steps: 5,
    });
    forecastResult.value = resp.data.data;
  } catch (e) {
    alert("预测失败：" + (e.response?.data?.detail || e.message));
  }
}

async function onTrigger() {
  const res = await triggerInner();
  runId.value = res.run_id;
}
</script>

<style scoped>
.forecast-chart {
  margin: 20px 0;
  padding: 20px;
  background: #f8fafc;
  border-radius: 12px;
}
.forecast-bars {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 24px;
  height: 200px;
  padding: 20px 0;
  position: relative;
}
.forecast-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  width: 48px;
  height: 100%;
  justify-content: flex-end;
}
.bar-conf {
  position: absolute;
  width: 100%;
  background: rgba(74, 144, 217, 0.15);
  border-radius: 4px;
  left: 0;
}
.bar-value {
  width: 32px;
  border-radius: 6px 6px 0 0;
  position: relative;
  z-index: 1;
  transition: all 0.3s ease;
  box-shadow: 0 -2px 8px rgba(0,0,0,0.1);
}
.bar-value:hover {
  transform: scaleY(1.05);
  filter: brightness(1.1);
}
.bar-label {
  font-size: 12px;
  color: #8fa3b8;
  margin-top: 8px;
  font-weight: 600;
}
.bar-val {
  font-size: 11px;
  color: #5a6a7e;
  font-weight: 700;
}
.forecast-legend {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 16px;
  font-size: 12px;
  color: #5a6a7e;
}
.forecast-legend .dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 3px;
  margin-right: 5px;
  vertical-align: middle;
}
.forecast-legend .dot.green { background: #10b981; }
.forecast-legend .dot.yellow { background: #f59e0b; }
.forecast-legend .dot.red { background: #ef4444; }
.forecast-legend .dot.conf { background: rgba(74,144,217,0.3); }

.anomaly-detail {
  margin-top: 16px;
}
</style>
