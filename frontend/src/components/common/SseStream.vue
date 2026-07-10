<template>
  <div class="card">
    <h3>Agent 实时日志</h3>
    <div class="sse-panel" ref="panelRef">
      <div v-for="(e, i) in events" :key="i" :class="e.type">
        <strong>[{{ e.type.toUpperCase() }}]</strong>
        {{ e.content || e.answer || (e.result ? JSON.stringify(e.result).slice(0, 120) : "") }}
      </div>
      <div v-if="events.length === 0" style="color:#666">等待事件...</div>
    </div>
  </div>
</template>

<script setup>
import { watch, ref, onUnmounted, nextTick } from "vue";
import { useSSE } from "../../composables/useSSE";

const props = defineProps({ runId: String });
const { events, connect } = useSSE();
const panelRef = ref(null);

let disconnect = null;

watch(() => props.runId, (id) => {
  if (id) {
    disconnect?.();
    events.value = [];
    disconnect = connect(id);
  }
}, { immediate: true });

watch(events, async () => {
  await nextTick();
  if (panelRef.value) {
    panelRef.value.scrollTop = panelRef.value.scrollHeight;
  }
}, { deep: true });

onUnmounted(() => disconnect?.());
</script>
