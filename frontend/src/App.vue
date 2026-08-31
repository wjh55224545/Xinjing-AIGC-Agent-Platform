<template>
  <div id="app-layout">
    <aside class="sidebar">
      <div class="logo">🧠 心镜 MindMirror</div>
      <nav>
        <router-link to="/">📊 仪表盘</router-link>
        <router-link to="/emotions">😊 情绪监测</router-link>
        <router-link to="/alerts">🔔 预警面板</router-link>
        <router-link to="/upload">📹 视频上传</router-link>
        <router-link to="/aigc">✨ AIGC报告</router-link>
        <router-link to="/agents">🤖 智能体面板</router-link>
        <router-link to="/scales">📋 心理量表</router-link>
        <router-link to="/experiment">🧪 经典实验</router-link>
        <router-link to="/virtual-subject">🎓 虚拟被试</router-link>
      </nav>
      <div class="sidebar-footer">
        <div class="footer-version">v2.1 · 心理健康评估平台</div>
        <div class="footer-status">
          <span class="status-dot"></span>
          系统运行中
        </div>
      </div>
    </aside>

    <div class="main-area">
      <header class="header">
        <div class="header-left">
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <span class="header-time">{{ currentTime }}</span>
          <span class="status"><span class="dot"></span>在线</span>
        </div>
      </header>
      <div class="page">
        <router-view />
      </div>
    </div>
    <FeedbackWidget />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import FeedbackWidget from "./components/common/FeedbackWidget.vue";

const route = useRoute();
const titles = {
  Dashboard: "仪表盘",
  EmotionMonitor: "实时情绪监测",
  AlertPanel: "预警管理",
  StudentDetail: "学生详情",
  VideoUpload: "视频上传",
  AigcReport: "AIGC内容生成",
  AgentPanel: "多智能体协作",
  ScalesView: "心理量表自评",
  ExperimentView: "心理教学实验",
  VirtualSubject: "虚拟被试教学演练",
};
const pageTitle = computed(() => titles[route.name] || "心镜");

const currentTime = ref("");
let timer = null;
function updateTime() {
  const now = new Date();
  currentTime.value = now.toLocaleString("zh-CN", {
    month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}
onMounted(() => { updateTime(); timer = setInterval(updateTime, 30000); });
onUnmounted(() => { if (timer) clearInterval(timer); });
</script>

<style scoped>
.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255,255,255,0.08);
  position: relative;
  z-index: 1;
}
.footer-version {
  font-size: 11px;
  color: rgba(200, 214, 229, 0.5);
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}
.footer-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(200, 214, 229, 0.7);
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.header-time {
  font-size: 13px;
  font-weight: 500;
  color: #8fa3b8;
}

@media (max-width: 800px) {
  .sidebar-footer { display: none; }
  .header-time { display: none; }
}
</style>
