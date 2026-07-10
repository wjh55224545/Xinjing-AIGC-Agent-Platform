<template>
  <div>
    <div class="card">
      <h3>视频上传与情绪分析</h3>
      <div class="filter-bar">
        <select v-model="studentId">
          <option v-for="s in students" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>
      <div class="upload-zone" @click="openFile" @dragover.prevent @drop.prevent="onDrop">
        <p v-if="!file" style="color:#999">点击或拖拽视频到此处上传</p>
        <p v-else style="color:#5b8def">{{ file.name }} ({{ formatSize(file.size) }})</p>
        <input ref="inputRef" type="file" accept="video/*" style="display:none" @change="onSelect" />
      </div>
      <button class="btn btn-primary" style="margin-top:12px" :disabled="!file || uploading" @click="upload">
        {{ uploading ? "上传中..." : "上传并分析" }}
      </button>
    </div>

    <div v-if="result" class="card">
      <h3>分析结果</h3>
      <p>视频路径: {{ result.image_path }}</p>
      <p>Run ID: {{ result.run_id }}</p>
    </div>
    <SseStream v-if="result?.run_id" :runId="result.run_id" />
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { fetchStudents, uploadVideo } from "../api";
import SseStream from "../components/common/SseStream.vue";

const students = ref([]);
const studentId = ref(null);
const file = ref(null);
const inputRef = ref(null);
const uploading = ref(false);
const result = ref(null);

onMounted(async () => {
  students.value = await fetchStudents();
  if (students.value.length) studentId.value = students.value[0].id;
});

function formatSize(bytes) {
  const mb = bytes / 1048576;
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
}
function openFile() { inputRef.value?.click(); }
function onSelect(e) { file.value = e.target.files?.[0] ?? null; }
function onDrop(e) { file.value = e.dataTransfer?.files?.[0] ?? null; }

async function upload() {
  if (!file.value || !studentId.value) return;
  uploading.value = true;
  const fd = new FormData();
  fd.append("file", file.value);
  fd.append("student_id", studentId.value);
  result.value = await uploadVideo(fd);
  uploading.value = false;
}
</script>
