<template>
  <div id="app-layout">
    <aside class="sidebar">
      <div class="logo">🧠 心镜 MindMirror</div>
      <nav>
        <router-link to="/">仪表盘</router-link>
        <router-link to="/emotions">情绪监测</router-link>
        <router-link to="/alerts">预警面板</router-link>
        <router-link to="/upload">视频上传</router-link>
      </nav>
    </aside>

    <div class="main-area">
      <header class="header">
        <span class="page-title">{{ pageTitle }}</span>
        <span class="status"><span class="dot"></span>系统运行中</span>
      </header>
      <div class="page">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const titles = {
  Dashboard: "仪表盘",
  EmotionMonitor: "实时情绪监测",
  AlertPanel: "预警管理",
  StudentDetail: "学生详情",
  VideoUpload: "视频上传",
};
const pageTitle = computed(() => titles[route.name] || "心镜");
</script>

