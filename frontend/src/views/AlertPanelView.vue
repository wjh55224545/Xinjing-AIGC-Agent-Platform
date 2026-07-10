<template>
  <div>
    <div class="card">
      <h3>预警列表</h3>
      <div class="filter-bar">
        <select v-model="filterSeverity" @change="load">
          <option value="">全部等级</option>
          <option value="green">绿色</option>
          <option value="yellow">黄色</option>
          <option value="red">红色</option>
        </select>
        <select v-model="filterAck" @change="load">
          <option :value="null">全部状态</option>
          <option :value="0">未确认</option>
          <option :value="1">已确认</option>
        </select>
      </div>
      <table>
        <thead><tr><th>等级</th><th>学生</th><th>原因</th><th>渠道</th><th>时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="a in alerts" :key="a.id">
            <td><span class="badge" :class="a.severity">{{ a.severity.toUpperCase() }}</span></td>
            <td>{{ a.student_id }}</td><td>{{ a.alert_reason }}</td><td>{{ a.feedback_channel }}</td>
            <td>{{ a.triggered_at }}</td>
            <td>
              <button v-if="!a.is_acknowledged" class="btn btn-success" @click="ack(a.id)">确认</button>
              <span v-else style="color:#999">已确认</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { fetchAlerts, acknowledgeAlert } from "../api";

const alerts = ref([]);
const filterSeverity = ref("");
const filterAck = ref(null);

onMounted(() => load());
async function load() {
  alerts.value = await fetchAlerts(filterSeverity.value || undefined, filterAck.value);
}
async function ack(id) {
  await acknowledgeAlert(id);
  await load();
}
</script>
