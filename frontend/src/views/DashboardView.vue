<template>
  <div>
    <div class="stat-grid">
      <div class="stat-card">
        <div class="label">学生总数</div>
        <div class="value">{{ summary?.total_students ?? "-" }}</div>
      </div>
      <div class="stat-card">
        <div class="label">今日平均情绪</div>
        <div class="value" :class="emotionClass">{{ summary?.today_avg_emotion ?? "-" }}</div>
      </div>
      <div class="stat-card">
        <div class="label">活跃预警</div>
        <div class="value" :class="summary?.active_alerts > 0 ? 'red' : 'green'">
          {{ summary?.active_alerts ?? 0 }}
        </div>
      </div>
    </div>

    <div class="flex-row mt-6">
      <div class="card">
        <h3>7日情绪趋势</h3>
        <EmotionTrendChart :data="trendData" class="chart-box" />
      </div>
      <div class="card">
        <h3>预警分布</h3>
        <AlertGauge :green="summary?.green_count??0" :yellow="summary?.yellow_count??0"
          :red="summary?.red_count??0" class="chart-box" />
      </div>
    </div>

    <div class="card">
      <h3>最近情绪记录</h3>
      <table>
        <thead><tr><th>学生ID</th><th>情绪</th><th>得分</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="r in summary?.recent_records ?? []" :key="r.id">
            <td>{{ r.student_id }}</td><td>{{ r.fused_emotion }}</td>
            <td>{{ r.fused_score }}</td><td>{{ r.recorded_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>系统控制</h3>
      <div style="display:flex;gap:12px">
        <button class="btn btn-primary" @click="onTriggerInner">触发实时采集</button>
        <button class="btn btn-warning" @click="onTriggerOuter">触发每日分析</button>
      </div>
      <SseStream v-if="runId" :runId="runId" style="margin-top:16px" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { fetchDashboard, triggerInner, triggerOuter } from "../api";
import EmotionTrendChart from "../components/charts/EmotionTrendChart.vue";
import AlertGauge from "../components/charts/AlertGauge.vue";
import SseStream from "../components/common/SseStream.vue";

const summary = ref(null);
const runId = ref("");

const trendData = computed(() => summary.value?.trend_data ?? []);
const emotionClass = computed(() => {
  const v = summary.value?.today_avg_emotion;
  if (v == null) return "";
  return v >= 0.7 ? "green" : v >= 0.4 ? "yellow" : "red";
});

onMounted(async () => { summary.value = await fetchDashboard(); });

async function onTriggerInner() {
  const res = await triggerInner();
  runId.value = res.run_id;
}

async function onTriggerOuter() {
  const res = await triggerOuter();
  runId.value = res.run_id;
}
</script>
