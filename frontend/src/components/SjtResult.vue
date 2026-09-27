<template>
  <div>
    <!-- 总分卡 -->
    <div class="score-banner" :class="totalLevelClass">
      <div class="score-num">{{ data.total_score }}</div>
      <div class="score-info">
        <strong>{{ data.total_level.label }}</strong>
        <span class="text-muted">总分（0-100，越高应对越积极）· 已答 {{ data.answered_count }} 题</span>
      </div>
    </div>

    <div class="sjt-grid">
      <!-- 维度雷达图 -->
      <div class="sjt-chart">
        <h4>六维应对倾向画像</h4>
        <v-chart :option="radarOption" autoresize style="height:320px"></v-chart>
      </div>

      <!-- 维度明细 -->
      <div class="sjt-dims">
        <h4>维度明细</h4>
        <div v-for="(d, key) in data.dimension_levels" :key="key" class="dim-row">
          <div class="dim-head">
            <span class="dim-name">{{ data.dimension_notes[key].slice(0, data.dimension_notes[key].indexOf('：')) }}</span>
            <span class="dim-badge" :class="d.level">{{ d.label }}</span>
            <span class="dim-score">{{ d.score }}</span>
          </div>
          <div class="dim-bar">
            <div class="dim-fill" :class="d.level" :style="{ width: d.score + '%' }"></div>
          </div>
          <p class="dim-note">{{ data.dimension_notes[key] }}</p>
        </div>
      </div>
    </div>

    <!-- 风险信号 -->
    <div class="risk-box" v-if="data.risk_signals.low_dims.length || data.risk_signals.watch_dims.length">
      <h4>⚠️ 风险信号</h4>
      <p v-if="data.risk_signals.low_dims.length" class="risk-line risk-low-text">
        应对不足维度：{{ data.risk_signals.low_dims.join('、') }}
      </p>
      <p v-if="data.risk_signals.watch_dims.length" class="risk-line risk-watch-text">
        需观察维度：{{ data.risk_signals.watch_dims.join('、') }}
      </p>
    </div>

    <!-- 建议 -->
    <div class="recs" v-if="data.recommendations.length">
      <h4>建议</h4>
      <ul>
        <li v-for="(r, i) in data.recommendations" :key="i">{{ r }}</li>
      </ul>
    </div>

    <p class="text-muted method">{{ data.method_note }}</p>
    <p v-if="data.profile_name" class="text-muted method">合成被试：{{ data.profile_name }}（θ={{ data.theta }}，is_synthetic=true）</p>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { RadarChart } from "echarts/charts";
import { RadarComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
use([RadarChart, RadarComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const props = defineProps({ data: { type: Object, required: true } });
const data = computed(() => props.data || {});

const totalLevelClass = computed(() => {
  const lv = (data.value.total_level || {}).level;
  return lv === "healthy" ? "lv-healthy" : lv === "moderate" ? "lv-moderate" : "lv-concern";
});

const radarOption = computed(() => {
  const ds = data.value.dimension_scores || {};
  const names = Object.keys(ds);
  return {
    tooltip: { trigger: "item" },
    legend: { show: false },
    radar: {
      indicator: names.map(n => ({ name: n, max: 100 })),
      radius: "65%",
      splitNumber: 4,
      axisName: { fontSize: 11 },
    },
    series: [{
      type: "radar",
      data: [{
        value: names.map(n => ds[n]),
        name: "应对倾向",
        areaStyle: { color: "rgba(99,102,241,0.25)" },
        lineStyle: { color: "#6366f1" },
        itemStyle: { color: "#6366f1" },
      }],
    }],
  };
});
</script>

<style scoped>
.score-banner { display: flex; align-items: center; gap: 18px; padding: 16px 20px; border-radius: 12px; margin-bottom: 16px; }
.score-banner.lv-healthy { background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); }
.score-banner.lv-moderate { background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); }
.score-banner.lv-concern { background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3); }
.score-num { font-size: 40px; font-weight: 800; color: #6366f1; line-height: 1; }
.score-info { display: flex; flex-direction: column; gap: 4px; }
.score-info strong { font-size: 18px; }
.text-muted { color: var(--text-muted, #9e9e9e); font-size: 13px; }

.sjt-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 900px) { .sjt-grid { grid-template-columns: 1fr; } }
.sjt-chart, .sjt-dims { background: var(--section-bg, #f9fafb); border-radius: 12px; padding: 16px; }
h4 { margin: 0 0 12px; font-size: 15px; }

.dim-row { margin-bottom: 12px; }
.dim-head { display: flex; align-items: center; gap: 10px; font-size: 13px; margin-bottom: 6px; }
.dim-name { flex: 1; font-weight: 600; }
.dim-badge { font-size: 11px; padding: 2px 8px; border-radius: 6px; font-weight: 600; }
.dim-badge.high { background: #d1fae5; color: #059669; }
.dim-badge.medium { background: #fef3c7; color: #d97706; }
.dim-badge.low { background: #fee2e2; color: #dc2626; }
.dim-score { font-weight: 700; color: #6366f1; width: 36px; text-align: right; }
.dim-bar { height: 8px; background: var(--tag-bg, #f3f4f6); border-radius: 4px; overflow: hidden; }
.dim-fill { height: 100%; border-radius: 4px; }
.dim-fill.high { background: linear-gradient(90deg, #34d399, #10b981); }
.dim-fill.medium { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.dim-fill.low { background: linear-gradient(90deg, #f87171, #ef4444); }
.dim-note { font-size: 12px; color: var(--text-muted, #6b7280); margin: 4px 0 0; line-height: 1.5; }

.risk-box { margin-top: 16px; padding: 14px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; }
.risk-box h4 { color: #b91c1c; }
.risk-line { margin: 4px 0; font-size: 13px; }
.risk-low-text { color: #dc2626; font-weight: 600; }
.risk-watch-text { color: #d97706; }

.recs { margin-top: 16px; }
.recs h4 { margin-bottom: 8px; }
.recs ul { margin: 0; padding-left: 18px; }
.recs li { font-size: 13px; color: var(--text, #4b5563); margin: 4px 0; }

.method { margin-top: 12px; font-size: 12px; line-height: 1.6; }
</style>
