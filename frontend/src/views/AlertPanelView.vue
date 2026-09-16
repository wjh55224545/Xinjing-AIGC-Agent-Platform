<template>
  <div>
    <!-- 干预闭环统计（方案二：预警→建议→复测→闭环） -->
    <div class="card" v-if="stats">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="margin:0">干预闭环统计</h3>
        <div style="display:flex;gap:10px">
          <button class="btn btn-warning" @click="checkOverdue">检查逾期</button>
          <button class="btn" @click="loadStats">刷新</button>
        </div>
      </div>
      <div class="stat-grid">
        <div class="stat">
          <div class="num">{{ stats.total_cycles }}</div>
          <div class="label">闭环总数</div>
        </div>
        <div class="stat">
          <div class="num">{{ stats.completed_cycles }}</div>
          <div class="label">已完成</div>
        </div>
        <div class="stat">
          <div class="num">{{ stats.overdue_cycles }}</div>
          <div class="label">已逾期</div>
        </div>
        <div class="stat">
          <div class="num">{{ stats.improved_rate }}%</div>
          <div class="label">好转率</div>
        </div>
        <div class="stat">
          <div class="num">
            {{ stats.avg_score_before !== null ? stats.avg_score_before : '—' }}
            → {{ stats.avg_score_after !== null ? stats.avg_score_after : '—' }}
          </div>
          <div class="label">干预前后均值</div>
        </div>
      </div>
      <p class="text-muted" style="margin-top:8px">
        依据 JITAI 即时自适应干预框架（Nahumshani et al., 2018）：预警不是终点，
        而是「预警 → 干预建议 → 定时复测 → 闭环统计」的起点。
        <span v-if="stats.risk_transition_matrix && Object.keys(stats.risk_transition_matrix).length">
          ｜风险迁移：{{ Object.entries(stats.risk_transition_matrix).map(([k, v]) => `${k} ×${v}`).join('，') }}
        </span>
      </p>
    </div>

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
              <button class="btn btn-primary" @click="createCycle(a)">创建闭环</button>
              <span v-if="a.is_acknowledged" style="color:#999;margin-left:6px">已确认</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import axios from "axios";
import { fetchAlerts, acknowledgeAlert } from "../api";

const alerts = ref([]);
const filterSeverity = ref("");
const filterAck = ref(null);
const stats = ref(null);

onMounted(() => { load(); loadStats(); });
async function load() {
  alerts.value = await fetchAlerts(filterSeverity.value || undefined, filterAck.value);
}
async function ack(id) {
  await acknowledgeAlert(id);
  await load();
}
async function loadStats() {
  try {
    const resp = await axios.get("/api/intervention/cycles/statistics");
    stats.value = resp.data.data;
  } catch { stats.value = null; }
}
async function checkOverdue() {
  try {
    const resp = await axios.post("/api/intervention/cycles/check-overdue");
    alert(`检查完成，逾期 ${resp.data.data.overdue_count} 条`);
    await loadStats();
  } catch { alert("检查失败"); }
}
async function createCycle(alert) {
  try {
    const resp = await axios.post("/api/intervention/cycles", {
      student_id: alert.student_id,
      alert_id: alert.id,
      risk_level_before: alert.severity || "yellow",
      plan_text: "",
      metrics_before: { overall_score: alert.overall_score || 0.5 },
      follow_up_days: 14,
    });
    alert(`已创建干预闭环 #${resp.data.data.id}，复测日期 ${resp.data.data.follow_up_date}`);
    await loadStats();
  } catch (e) {
    alert(e.response?.data?.detail || "创建失败");
  }
}
</script>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.card h3 { margin: 0 0 12px; font-size: 16px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 12px; }
select { padding: 8px; font-size: 14px; border: 1px solid #e5e7eb; border-radius: 6px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #f1f5f9; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; color: #fff; }
.badge.green { background: #16a34a; }
.badge.yellow { background: #d97706; }
.badge.red { background: #dc2626; }
.btn { padding: 6px 12px; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; margin-right: 6px; }
.btn-primary { background: #4f46e5; color: #fff; }
.btn-success { background: #16a34a; color: #fff; }
.btn-warning { background: #d97706; color: #fff; }
.text-muted { color: #9e9e9e; font-size: 12px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-top: 14px; }
.stat { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; text-align: center; background: #fafafa; }
.stat .num { font-size: 20px; font-weight: 700; color: #1f2937; }
.stat .label { font-size: 12px; color: #6b7280; margin-top: 4px; }
</style>
