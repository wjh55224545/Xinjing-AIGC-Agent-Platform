<template>
  <div>
    <div class="card">
      <h3>学生情绪监测</h3>
      <div class="filter-bar">
        <select v-model="selectedId" @change="load">
          <option v-for="s in students" :key="s.id" :value="s.id">{{ s.name }} ({{ s.student_code }})</option>
        </select>
        <input type="date" v-model="dateStr" @change="loadTimeline" />
        <button class="btn btn-primary" @click="onTrigger">触发采集</button>
      </div>
    </div>

    <div class="card">
      <h3>{{ dateStr }} 情绪时间线</h3>
      <EmotionTrendChart v-if="timeline.length" :data="timelineData" timeMode class="chart-box" />
      <p v-else style="color:#999">暂无数据</p>
    </div>

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
    </div>

    <SseStream v-if="runId" :runId="runId" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { fetchStudents, fetchRecentEmotions, fetchEmotionTimeline, triggerInner } from "../api";
import EmotionTrendChart from "../components/charts/EmotionTrendChart.vue";
import SseStream from "../components/common/SseStream.vue";

const students = ref([]);
const selectedId = ref(null);
const dateStr = ref(new Date().toISOString().slice(0, 10));
const records = ref([]);
const timeline = ref([]);
const runId = ref("");

const timelineData = computed(() =>
  timeline.value.map(r => ({ date: r.recorded_at, avg_score: r.fused_score }))
);

onMounted(async () => {
  students.value = await fetchStudents();
  if (students.value.length) { selectedId.value = students.value[0].id; await load(); }
});

async function load() {
  if (!selectedId.value) return;
  records.value = await fetchRecentEmotions(selectedId.value);
  await loadTimeline();
}

async function loadTimeline() {
  if (!selectedId.value) return;
  timeline.value = await fetchEmotionTimeline(selectedId.value, dateStr.value);
}

async function onTrigger() {
  const res = await triggerInner();
  runId.value = res.run_id;
}
</script>
