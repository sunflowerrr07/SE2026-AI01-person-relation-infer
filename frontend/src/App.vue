<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useDashboard } from './store'
import GraphView from './components/GraphView.vue'

const store = useDashboard()
const page = ref('tasks')
const file = ref(null)
const authorized = ref(false)
const hops = ref(2)
const selectedPerson = ref('')
const statusText = { queued: '排队中', running: '分析中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }
const selectedTask = computed(() => store.tasks.find(t => t.task_id === store.selected))
let timer

async function perform(action) {
  store.error = ''
  try { await action() } catch (error) { store.error = error.message || '服务暂不可用' }
}
async function connect() { await perform(async () => { await store.refreshTasks(); if (store.tasks.some(t => ['queued', 'running'].includes(t.status))) beginPolling() }) }
async function submit() {
  if (!file.value || !authorized.value) { store.error = '请选择文件并确认数据已获授权。'; return }
  store.busy = true
  await perform(async () => { await store.upload(file.value); beginPolling() })
  store.busy = false
}
function beginPolling() {
  clearInterval(timer)
  timer = setInterval(async () => {
    try {
      await store.refreshTasks()
      if (!store.tasks.some(t => ['queued', 'running'].includes(t.status))) clearInterval(timer)
    } catch (error) { clearInterval(timer); store.error = error.message }
  }, 1500)
}
async function showGraph(task) {
  await perform(async () => { await store.loadGraph(task.task_id); page.value = 'graph' })
}
async function selectPerson(id) {
  selectedPerson.value = id
  await perform(() => store.loadNeighbors(id, hops.value))
}
async function openAudit() { page.value = 'audit'; await perform(() => store.loadAudit()) }
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">◎</span><div><strong>关系图谱</strong><small>RESEARCH WORKSPACE</small></div></div>
      <div class="side-label">工作空间</div>
      <button :class="{ active: page === 'tasks' }" @click="page = 'tasks'">▦ <span>分析任务</span></button>
      <button :class="{ active: page === 'graph' }" @click="page = 'graph'">◇ <span>关系图谱</span></button>
      <button :class="{ active: page === 'audit' }" @click="openAudit">◉ <span>隐私与审计</span></button>
      <div class="side-foot"><span class="status-dot"></span> 本地实验环境 <small>数据经授权后使用</small></div>
    </aside>
    <main class="main">
      <header class="topbar"><div><span class="eyebrow">SE2026-AI-1 / 工作空间</span><h1>{{ page === 'tasks' ? '分析任务' : page === 'graph' ? '关系图谱' : '隐私与审计' }}</h1></div><div class="connection"><el-input v-model="store.token" type="password" show-password placeholder="输入访问令牌" aria-label="访问令牌" @keyup.enter="connect"/><el-button @click="connect">连接</el-button></div></header>
      <div class="content">
        <el-alert v-if="store.error" :title="store.error" type="error" show-icon closable @close="store.error = ''" />
        <div class="notice"><strong>实验演示模式</strong><span>上传文件仅用于演示处理；轨迹为模拟数据，GNN 模型未经训练，结果不代表真实人员关系。</span></div>
        <template v-if="page === 'tasks'">
          <div class="section-heading"><div><span class="eyebrow">01 / ANALYSIS</span><h2>创建分析任务</h2><p>上传已获授权的图像或短视频，查看演示处理状态。</p></div><span class="pill">MOCK PIPELINE</span></div>
          <div class="upload-card">
            <div class="upload-icon">↑</div><div><h3>选择媒体文件</h3><p>支持 PNG、JPG、MP4、AVI、MOV，单个文件不超过 16 MB。</p><input aria-label="选择媒体文件" type="file" accept=".png,.jpg,.jpeg,.mp4,.avi,.mov" @change="file = $event.target.files[0]"/></div>
            <div class="upload-actions"><el-checkbox v-model="authorized">我确认已获得数据使用授权</el-checkbox><el-button type="primary" :loading="store.busy" @click="submit">上传并运行演示</el-button></div>
          </div>
          <div class="section-heading compact"><div><span class="eyebrow">TASK HISTORY</span><h2>任务列表</h2></div><el-button @click="perform(() => store.refreshTasks())">刷新列表</el-button></div>
          <el-table :data="store.tasks" empty-text="暂无任务，连接后上传媒体开始演示">
            <el-table-column label="任务标识" min-width="230"><template #default="scope"><span class="mono">{{ scope.row.task_id }}</span></template></el-table-column>
            <el-table-column label="状态" width="120"><template #default="scope"><span class="state">{{ statusText[scope.row.status] || scope.row.status }}</span></template></el-table-column>
            <el-table-column label="处理进度" min-width="170"><template #default="scope"><el-progress :percentage="scope.row.progress || 0" /></template></el-table-column>
            <el-table-column label="操作" width="120"><template #default="scope"><el-button link type="primary" :disabled="scope.row.status !== 'succeeded'" @click="showGraph(scope.row)">查看图谱 →</el-button></template></el-table-column>
          </el-table>
          <p v-if="selectedTask?.error" class="error-text">{{ selectedTask.error }}</p>
        </template>
        <template v-else-if="page === 'graph'">
          <div class="section-heading"><div><span class="eyebrow">02 / GRAPH EXPLORER</span><h2>探索关联网络</h2><p>选择已完成任务，点击节点查看多跳关联。</p></div><el-select v-model="store.selected" placeholder="选择任务" style="width: 260px" @change="id => perform(() => store.loadGraph(id))"><el-option v-for="task in store.tasks.filter(t => t.status === 'succeeded')" :key="task.task_id" :label="task.task_id" :value="task.task_id" /></el-select></div>
          <div class="graph-layout"><div class="graph-panel"><div class="panel-top"><div><strong>人员关联网络</strong><small>支持拖动、缩放和节点选择</small></div><span class="pill">{{ store.people.length }} 个节点 / {{ store.relations.length }} 条关系</span></div><GraphView :people="store.people" :relations="store.relations" @select="selectPerson"/><div v-if="!store.people.length" class="graph-empty">选择任务后展示图谱</div></div>
            <div class="detail-panel"><span class="eyebrow">DETAILS</span><h3>关系详情</h3><p v-if="!store.relations.length">暂无可展示关系</p><div v-for="relation in store.relations" :key="relation.source + relation.target" class="relation"><strong>{{ relation.source }} ↔ {{ relation.target }}</strong><span>模型输出 {{ relation.confidence == null ? '—' : (relation.confidence * 100).toFixed(1) + '%' }}</span><small>未训练 · 不确定 · {{ relation.model_version || '无版本' }}</small></div><div class="divider"></div><h3>多跳关联</h3><p>点击图中节点后查询</p><el-select v-model="hops" style="width: 100%" @change="selectedPerson && selectPerson(selectedPerson)"><el-option v-for="n in 4" :key="n" :label="`${n} 跳`" :value="n" /></el-select><p v-if="selectedPerson">起点：{{ selectedPerson }}</p><div v-for="n in store.neighbors" :key="n.person_id" class="neighbor">{{ n.person_id }} <span>{{ n.hops }} 跳</span></div></div></div>
        </template>
        <template v-else>
          <div class="section-heading"><div><span class="eyebrow">03 / PRIVACY & AUDIT</span><h2>隐私与访问审计</h2><p>人员仅以匿名标识展示；审计记录由管理员或审计人员查看。</p></div><el-button @click="perform(() => store.loadAudit())">刷新记录</el-button></div>
          <div class="privacy-grid"><div><strong>匿名标识</strong><span>图谱不展示姓名或身份信息</span></div><div><strong>权限控制</strong><span>审计记录仅限授权角色</span></div><div><strong>操作留痕</strong><span>记录访问结果与请求标识</span></div></div>
          <el-table :data="store.events" empty-text="暂无记录，或当前令牌没有审计权限"><el-table-column prop="timestamp" label="时间" min-width="210"/><el-table-column prop="actor" label="操作者" width="130"/><el-table-column prop="action" label="操作" width="100"/><el-table-column prop="target" label="访问对象" min-width="220"/><el-table-column prop="outcome" label="结果" width="110"/></el-table>
        </template>
      </div>
    </main>
  </div>
</template>
