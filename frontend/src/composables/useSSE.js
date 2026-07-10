import { ref } from "vue";

export function useSSE() {
  const events = ref([]);
  const connected = ref(false);

  function connect(runId) {
    const url = `/api/agent/stream/${runId}`;
    const es = new EventSource(url);
    connected.value = true;

    es.addEventListener("thought", e => events.value.push({ type: "thought", ...JSON.parse(e.data) }));
    es.addEventListener("action", e => events.value.push({ type: "action", ...JSON.parse(e.data) }));
    es.addEventListener("observation", e => events.value.push({ type: "observation", ...JSON.parse(e.data) }));
    es.addEventListener("final", e => {
      events.value.push({ type: "final", ...JSON.parse(e.data) });
      es.close();
      connected.value = false;
    });
    es.addEventListener("error", e => {
      try { events.value.push({ type: "error", ...JSON.parse(e.data) }); } catch (_) {}
      es.close();
      connected.value = false;
    });
    es.onerror = () => { connected.value = false; es.close(); };

    return () => { es.close(); connected.value = false; };
  }

  return { events, connected, connect };
}
