<template>
  <v-chart :option="option" autoresize />
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const props = defineProps({ data: { type: Array, default: () => [] }, timeMode: Boolean });

const option = computed(() => ({
  tooltip: { trigger: "axis" },
  legend: { bottom: 0 },
  grid: { left: 40, right: 20, top: 16, bottom: 30 },
  xAxis: { type: "category", data: props.data.map(d => props.timeMode ? d.date.slice(11, 19) : d.date) },
  yAxis: { type: "value", min: 0, max: 1 },
  series: [{
    name: "情绪得分", type: "line", data: props.data.map(d => d.avg_score),
    smooth: true, areaStyle: { opacity: 0.15 },
    lineStyle: { color: "#2d6a4f" }, itemStyle: { color: "#2d6a4f" },
  }],
}));
</script>
