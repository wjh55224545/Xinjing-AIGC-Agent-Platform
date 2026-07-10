<template>
  <v-chart :option="option" autoresize />
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { PieChart } from "echarts/charts";
import { TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer]);

const props = defineProps({ green: Number, yellow: Number, red: Number });

const option = computed(() => ({
  tooltip: { trigger: "item" },
  legend: { bottom: 0 },
  series: [{
    type: "pie", radius: ["45%", "75%"], center: ["50%", "45%"],
    data: [
      { value: props.green, name: "绿色", itemStyle: { color: "#4caf50" } },
      { value: props.yellow, name: "黄色", itemStyle: { color: "#ff9800" } },
      { value: props.red, name: "红色", itemStyle: { color: "#f44336" } },
    ],
    label: { show: false },
  }],
}));
</script>
