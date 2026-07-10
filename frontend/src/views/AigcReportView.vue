<template>
  <div class="aigc-report-page">
    <h1>✨ AIGC 内容生成</h1>
    <p class="subtitle">基于国产算力平台（沐曦MetaX GPU / Gitee.AI）的智能内容生成</p>

    <!-- 功能卡片 -->
    <div class="capability-grid">
      <div class="capability-card" v-for="cap in capabilities" :key="cap.id"
           @click="selectCapability(cap)"
           :class="{ active: selectedCap?.id === cap.id }">
        <span class="cap-icon">{{ cap.icon }}</span>
        <h3>{{ cap.name }}</h3>
        <p>{{ cap.description }}</p>
      </div>
    </div>

    <!-- 生成表单 -->
    <div class="generator-panel" v-if="selectedCap">
      <h2>{{ selectedCap.name }}</h2>

      <!-- 日报表单 -->
      <div v-if="selectedCap.id === 'daily_report'" class="form-group">
        <label>学生姓名</label>
        <input v-model="form.student_name" placeholder="输入学生姓名" />
        <label>日期</label>
        <input v-model="form.date" type="date" />
        <label>情绪概况 (JSON)</label>
        <textarea v-model="form.emotion_json" rows="4" placeholder='{"fused_emotion": "开心", "fused_score": 0.85}'></textarea>
      </div>

      <!-- 干预方案表单 -->
      <div v-else-if="selectedCap.id === 'intervention_plan'" class="form-group">
        <label>学生姓名</label>
        <input v-model="form.student_name" placeholder="输入学生姓名" />
        <label>风险等级</label>
        <select v-model="form.risk_level">
          <option value="green">🟢 绿色 - 正常</option>
          <option value="yellow">🟡 黄色 - 关注</option>
          <option value="red">🔴 红色 - 紧急</option>
        </select>
        <label>风险因素（每行一个）</label>
        <textarea v-model="form.risk_factors_text" rows="3" placeholder="负面情绪占比偏高&#10;情绪波动幅度较大"></textarea>
      </div>

      <!-- 家校沟通函表单 -->
      <div v-else-if="selectedCap.id === 'parent_letter'" class="form-group">
        <label>学生姓名</label>
        <input v-model="form.student_name" placeholder="输入学生姓名" />
        <label>班级</label>
        <input v-model="form.class_name" placeholder="输入班级" />
        <label>风险等级</label>
        <select v-model="form.risk_level">
          <option value="green">🟢 绿色</option>
          <option value="yellow">🟡 黄色</option>
          <option value="red">🔴 红色</option>
        </select>
        <label>情绪概况</label>
        <textarea v-model="form.emotion_summary" rows="3" placeholder="描述学生近期情绪状态..."></textarea>
      </div>

      <!-- 成长叙事表单 -->
      <div v-else-if="selectedCap.id === 'growth_narrative'" class="form-group">
        <label>学生姓名</label>
        <input v-model="form.student_name" placeholder="输入学生姓名" />
        <label>时间跨度（天）</label>
        <input v-model="form.period_days" type="number" min="7" max="365" />
      </div>

      <button class="btn-generate" @click="generate" :disabled="generating">
        {{ generating ? '⏳ 生成中...' : '🚀 开始生成' }}
      </button>

      <!-- 生成结果 -->
      <div class="result-panel" v-if="result">
        <h3>✅ 生成结果</h3>
        <div class="result-meta">
          <span class="badge">平台: {{ result.platform || '沐曦MetaX GPU' }}</span>
          <span class="badge">风险等级: {{ result.risk_level || 'N/A' }}</span>
        </div>
        <div class="result-content" v-html="renderedResult"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const capabilities = ref([
  { id: 'daily_report', name: '📊 心理评估日报', icon: '📊', description: '基于全天情绪数据生成结构化评估报告', endpoint: '/api/aigc/report/daily' },
  { id: 'intervention_plan', name: '📋 干预方案', icon: '📋', description: '针对黄/红色预警自动生成个性化干预计划', endpoint: '/api/aigc/plan/intervention' },
  { id: 'parent_letter', name: '✉️ 家校沟通函', icon: '✉️', description: '用温和措辞向家长传达学生情绪状态', endpoint: '/api/aigc/letter/parent' },
  { id: 'growth_narrative', name: '📈 成长叙事', icon: '📈', description: '基于长期数据生成学生心理成长轨迹', endpoint: '/api/aigc/narrative/growth' },
])

const selectedCap = ref(null)
const generating = ref(false)
const result = ref(null)

const form = ref({
  student_name: '张三',
  date: new Date().toISOString().split('T')[0],
  risk_level: 'green',
  class_name: '计算机科学2024',
  emotion_json: '{"fused_emotion": "开心", "fused_score": 0.85}',
  emotion_summary: '近期情绪总体稳定，偶尔有轻微波动。',
  risk_factors_text: '',
  period_days: 30,
})

function selectCapability(cap) {
  selectedCap.value = cap
  result.value = null
}

async function generate() {
  generating.value = true
  result.value = null

  try {
    let body = {}
    const cap = selectedCap.value

    if (cap.id === 'daily_report') {
      let emotionData = {}
      try { emotionData = JSON.parse(form.value.emotion_json) } catch(e) {}
      body = {
        student_name: form.value.student_name,
        date: form.value.date,
        emotion_data: emotionData,
        analysis_result: {},
      }
    } else if (cap.id === 'intervention_plan') {
      const factors = form.value.risk_factors_text.split('\n').filter(f => f.trim())
      body = {
        student_name: form.value.student_name,
        risk_level: form.value.risk_level,
        risk_factors: factors,
        indicators: {},
      }
    } else if (cap.id === 'parent_letter') {
      body = {
        student_name: form.value.student_name,
        class_name: form.value.class_name,
        risk_level: form.value.risk_level,
        emotion_summary: form.value.emotion_summary,
        suggestions: [],
      }
    } else if (cap.id === 'growth_narrative') {
      body = {
        student_name: form.value.student_name,
        period_days: parseInt(form.value.period_days) || 30,
        historical_data: {},
      }
    }

    const res = await fetch(cap.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    if (data.success) {
      result.value = data.data
    } else {
      result.value = { error: data.detail || '生成失败' }
    }
  } catch (e) {
    result.value = { error: e.message }
  } finally {
    generating.value = false
  }
}

const renderedResult = computed(() => {
  if (!result.value) return ''
  if (result.value.error) return `<p style="color:red">错误: ${result.value.error}</p>`
  const text = result.value.report_text || result.value.plan_text ||
               result.value.letter_text || result.value.narrative_text || ''
  // 简单Markdown渲染
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n- /g, '\n<li>')
    .replace(/\n/g, '<br>')
})
</script>

<style scoped>
.aigc-report-page { padding: 24px; max-width: 1400px; margin: 0 auto; }
.subtitle { color: #666; margin-bottom: 24px; }

.capability-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 32px; }
.capability-card {
  padding: 20px; border: 2px solid #e0e0e0; border-radius: 12px;
  cursor: pointer; transition: all 0.2s; background: #fff;
}
.capability-card:hover { border-color: #409EFF; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.capability-card.active { border-color: #409EFF; background: #ecf5ff; }
.capability-card h3 { margin: 8px 0 4px; font-size: 16px; }
.capability-card p { color: #666; font-size: 13px; margin: 0; }
.cap-icon { font-size: 32px; }

.generator-panel { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.form-group { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.form-group label { font-weight: 600; font-size: 14px; color: #333; }
.form-group input, .form-group select, .form-group textarea {
  padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px;
}
.form-group textarea { resize: vertical; font-family: monospace; }

.btn-generate {
  padding: 12px 32px; background: #409EFF; color: #fff; border: none;
  border-radius: 8px; font-size: 16px; cursor: pointer; margin-top: 8px;
}
.btn-generate:hover { background: #337ECC; }
.btn-generate:disabled { background: #a0cfff; cursor: not-allowed; }

.result-panel { margin-top: 24px; padding: 20px; background: #f8fafc; border-radius: 8px; }
.result-meta { display: flex; gap: 8px; margin-bottom: 12px; }
.badge { padding: 4px 12px; background: #409EFF; color: #fff; border-radius: 12px; font-size: 12px; }
.result-content { line-height: 1.8; white-space: pre-wrap; font-size: 14px; }
</style>
