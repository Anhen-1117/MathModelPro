<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  option: any
  height?: string
  theme?: 'dark' | 'light'
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value, props.theme || 'dark')
  if (props.option) {
    chart.setOption(props.option)
  }
}

const handleResize = () => {
  chart?.resize()
}

watch(() => props.option, (newOption) => {
  if (chart && newOption) {
    chart.setOption(newOption, true)
  }
}, { deep: true })

onMounted(() => {
  nextTick(() => initChart())
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', handleResize)
})

// 暴露方法
defineExpose({
  getInstance: () => chart,
  resize: () => chart?.resize(),
})
</script>

<template>
  <div ref="chartRef" :style="{ width: '100%', height: height || '400px' }"></div>
</template>
