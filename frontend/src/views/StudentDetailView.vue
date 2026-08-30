<template>
  <div v-if="student">
    <div class="stat-grid">
      <div class="stat-card">
        <div class="label">姓名</div>
        <div class="value" style="font-size:22px">{{ student.name }}</div>
      </div>
      <div class="stat-card">
        <div class="label">班级</div>
        <div class="value" style="font-size:18px">{{ student.class_name }}</div>
      </div>
      <div class="stat-card">
        <div class="label">学号</div>
        <div class="value" style="font-size:18px">{{ student.student_code }}</div>
      </div>
      <div class="stat-card">
        <div class="label">情绪基线</div>
        <div class="value" style="font-size:22px">{{ student.baseline_mood }}</div>
      </div>
    </div>

    <div class="card" style="margin-top:20px">
      <h3>近期情绪记录</h3>
      <table>
        <thead><tr><th>时间</th><th>情绪</th><th>得分</th><th>类型</th></tr></thead>
        <tbody>
          <tr v-for="r in student.recent_records" :key="r.id">
            <td>{{ r.recorded_at }}</td><td>{{ r.fused_emotion }}</td><td>{{ r.fused_score }}</td>
            <td>{{ r.is_manual ? '手动' : '自动' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>预警历史</h3>
      <table>
        <thead><tr><th>等级</th><th>原因</th><th>时间</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="a in student.recent_alerts" :key="a.id">
            <td><span class="badge" :class="a.severity">{{ a.severity.toUpperCase() }}</span></td>
            <td>{{ a.alert_reason }}</td><td>{{ a.triggered_at }}</td>
            <td>{{ a.is_acknowledged ? '已确认' : '未确认' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { fetchStudent } from "../api";

const route = useRoute();
const student = ref(null);

onMounted(async () => {
  student.value = await fetchStudent(route.params.id);
});
</script>
