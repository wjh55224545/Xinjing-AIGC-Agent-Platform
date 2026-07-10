<template>
  <div class="agent-panel-page">
    <h1>🤖 多智能体协作面板</h1>
    <p class="subtitle">实时查看基于国产算力平台的多Agent协作状态</p>

    <!-- 平台信息 -->
    <div class="platform-info" v-if="platformInfo">
      <span class="badge gpu">🇨🇳 国产算力: {{ platformInfo.domestic_gpu }}</span>
      <span class="badge current">当前平台: {{ platformInfo.current_platform }}</span>
    </div>

    <!-- 智能体卡片 -->
    <div class="agent-grid" v-if="agentsInfo">
      <div class="agent-card" v-for="agent in allAgents" :key="agent.name"
           :class="{ active: activeAgent === agent.name }">
        <div class="agent-header">
          <span class="agent-icon">{{ agent.icon }}</span>
          <div>
            <h3>{{ agent.name }}</h3>
            <p>{{ agent.description }}</p>
          </div>
        </div>
        <div class="agent-tools">
          <span class="tool-tag" v-for="tool in agent.tools" :key="tool">{{ tool }}</span>
        </div>
        <div class="agent-status">
          <span class="status-dot" :class="agent.status"></span>
          {{ agent.statusText }}
        </div>
      </div>
    </div>

    <!-- 手动触发按钮 -->
    <div class="trigger-section">
      <button class="btn trigger-inner" @click="triggerInner" :disabled="running">
        🔄 手动触发情绪采集（内环）
      </button>
      <button class="btn trigger-outer" @click="triggerOuter" :disabled="running">
        🌙 手动触发每日分析（外环 - 完整AIGC流程）
      </button>
    </div>

    <!-- SSE流式日志 -->
    <div class="stream-log" v-if="logEntries.length > 0">
      <h3>📡 实时协作日志 (SSE)</h3>
      <div class="log-entries">
        <div class="log-entry" v-for="(entry, i) in logEntries" :key="i"
             :class="'log-' + entry.event">
          <span class="log-time">{{ entry.timestamp?.substring(11, 19) || '' }}</span>
          <span class="log-agent">[{{ entry.agent || entry.agent_name || '系统' }}]</span>
          <span class="log-event">{{ entry.event }}</span>
          <span class="log-content">{{ truncate(entry.content || entry.result || '', 200) }}</span>
        </div>
      </div>
    </div>

    <!-- 运行状态 -->
    <div class="status-bar" v-if="running">
      <span class="spinner"></span> 智能体协作进行中...
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const platformInfo = ref(null)
const agentsInfo = ref(null)
const activeAgent = ref(null)
const running = ref(false)
const logEntries = ref([])

const allAgents = computed(() => {
  if (!agentsInfo.value) return []
  return [
    { name: '协调智能体', icon: '🎯', description: '多Agent总调度器', tools: ['任务分配', '消息路由', '结果汇总'], status: 'online', statusText: '就绪' },
    { name: '感知智能体', icon: '👁️', description: '多模态情绪识别', tools: ['多模态情绪识别'], status: 'online', statusText: '就绪' },
    { name: '分析智能体', icon: '🧠', description: '心理健康深度分析', tools: ['时序心理分析'], status: 'online', statusText: '就绪' },
    { name: 'AIGC报告智能体', icon: '✨', description: '智能内容生成', tools: ['生成日报', '干预方案', '家校沟通函', '成长叙事'], status: 'online', statusText: '就绪' },
    { name: '预警智能体', icon: '🔔', description: '分级预警与反馈', tools: ['多渠道反馈'], status: 'online', statusText: '就绪' },
  ]
})

onMounted(async () => {
  try {
    const [pRes, aRes] = await Promise.all([
      fetch('/api/agents/platform'),
      fetch('/api/agents/info'),
    ])
    platformInfo.value = (await pRes.json()).data
    agentsInfo.value = (await aRes.json()).data
  } catch (e) {
    console.error('加载智能体信息失败:', e)
  }
})

async function triggerInner() {
  running.value = true
  logEntries.value = []
  try {
    const res = await fetch('/api/agents/trigger/inner', { method: 'POST' })
    const data = await res.json()
    if (data.run_id) {
      connectSSE(data.run_id)
    }
    addLog('system', '内环已触发', `涉及 ${data.students_count} 名学生`)
  } catch (e) {
    addLog('error', '触发失败', e.message)
    running.value = false
  }
}

async function triggerOuter() {
  running.value = true
  logEntries.value = []
  try {
    const res = await fetch('/api/agents/trigger/outer', { method: 'POST' })
    const data = await res.json()
    if (data.run_id) {
      connectSSE(data.run_id)
    }
    addLog('system', '外环已触发（完整AIGC流程）', `目标日期: ${data.target_date}`)
  } catch (e) {
    addLog('error', '触发失败', e.message)
    running.value = false
  }
}

function connectSSE(runId) {
  const eventSource = new EventSource(`/api/agents/stream/${runId}`)

  eventSource.addEventListener('thought', (e) => {
    const data = JSON.parse(e.data)
    addLog('thought', data.agent || 'Agent', data.content)
  })
  eventSource.addEventListener('action', (e) => {
    const data = JSON.parse(e.data)
    addLog('action', data.agent || 'Agent', `调用工具: ${data.tool}`)
    activeAgent.value = data.agent
  })
  eventSource.addEventListener('observation', (e) => {
    const data = JSON.parse(e.data)
    addLog('observation', data.agent || 'Agent', data.result)
  })
  eventSource.addEventListener('final', (e) => {
    const data = JSON.parse(e.data)
    addLog('final', data.agent || '系统', data.content)
    running.value = false
    eventSource.close()
  })
  eventSource.addEventListener('error', () => {
    running.value = false
    eventSource.close()
  })
}

function addLog(event, agent, content) {
  logEntries.value.push({
    event, agent, content,
    timestamp: new Date().toISOString(),
  })
}

function truncate(text, maxLen) {
  if (!text) return ''
  const str = typeof text === 'object' ? JSON.stringify(text) : String(text)
  return str.length > maxLen ? str.substring(0, maxLen) + '...' : str
}
</script>

<style scoped>
.agent-panel-page { padding: 24px; max-width: 1400px; margin: 0 auto; }
.subtitle { color: #666; margin-bottom: 16px; }

.platform-info { display: flex; gap: 12px; margin-bottom: 24px; }
.badge { padding: 6px 14px; border-radius: 16px; font-size: 13px; }
.badge.gpu { background: #fff3e0; color: #e65100; font-weight: bold; }
.badge.current { background: #e3f2fd; color: #1565c0; }

.agent-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
.agent-card { padding: 16px; border: 2px solid #e0e0e0; border-radius: 12px; background: #fff; transition: all 0.2s; }
.agent-card.active { border-color: #409EFF; background: #ecf5ff; }
.agent-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.agent-icon { font-size: 36px; }
.agent-header h3 { margin: 0; font-size: 15px; }
.agent-header p { margin: 2px 0 0; font-size: 12px; color: #666; }
.agent-tools { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.tool-tag { padding: 2px 8px; background: #f0f0f0; border-radius: 10px; font-size: 11px; color: #666; }

.agent-status { font-size: 12px; color: #666; display: flex; align-items: center; gap: 6px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.online { background: #67c23a; }

.trigger-section { display: flex; gap: 16px; margin-bottom: 24px; }
.btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.trigger-inner { background: #409EFF; }
.trigger-outer { background: #E6A23C; }

.stream-log { background: #1e1e1e; border-radius: 8px; padding: 16px; max-height: 400px; overflow-y: auto; }
.stream-log h3 { color: #fff; margin: 0 0 12px; }
.log-entries { font-family: 'Courier New', monospace; font-size: 13px; }
.log-entry { padding: 4px 0; border-bottom: 1px solid #333; display: flex; gap: 10px; }
.log-time { color: #888; min-width: 70px; }
.log-agent { color: #409EFF; min-width: 120px; }
.log-event { color: #E6A23C; min-width: 60px; }
.log-content { color: #ccc; flex: 1; }
.log-thought { border-left: 2px solid #409EFF; padding-left: 8px; }
.log-action { border-left: 2px solid #E6A23C; padding-left: 8px; }
.log-final { border-left: 2px solid #67c23a; padding-left: 8px; }

.status-bar { text-align: center; padding: 12px; color: #409EFF; display: flex; align-items: center; justify-content: center; gap: 8px; }
.spinner { width: 16px; height: 16px; border: 2px solid #409EFF; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
