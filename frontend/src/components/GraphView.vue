<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { graphOption } from '../api'
const props = defineProps({ people: { type: Array, default: () => [] }, relations: { type: Array, default: () => [] } })
const emit = defineEmits(['select'])
const container = ref(null)
let chart
const resize = () => chart?.resize()
onMounted(() => {
  chart = echarts.init(container.value)
  chart.on('click', event => { if (event.dataType === 'node') emit('select', event.data.id) })
  chart.setOption(graphOption(props.people, props.relations), true)
  window.addEventListener('resize', resize)
})
watch(() => [props.people, props.relations], () => chart?.setOption(graphOption(props.people, props.relations), true), { deep: true })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>
<template><div ref="container" class="graph" role="img" aria-label="人员关系图谱"></div></template>
