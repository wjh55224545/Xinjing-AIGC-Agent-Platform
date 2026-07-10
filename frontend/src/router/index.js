import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", name: "Dashboard", component: () => import("../views/DashboardView.vue") },
  { path: "/emotions", name: "EmotionMonitor", component: () => import("../views/EmotionMonitorView.vue") },
  { path: "/alerts", name: "AlertPanel", component: () => import("../views/AlertPanelView.vue") },
  { path: "/students/:id", name: "StudentDetail", component: () => import("../views/StudentDetailView.vue") },
  { path: "/upload", name: "VideoUpload", component: () => import("../views/ImageUploadView.vue") },
  { path: "/aigc", name: "AigcReport", component: () => import("../views/AigcReportView.vue") },
  { path: "/agents", name: "AgentPanel", component: () => import("../views/AgentPanelView.vue") },
];

export default createRouter({ history: createWebHistory(), routes });
