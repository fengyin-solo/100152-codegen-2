<template>
  <section class="page" data-module="environment">
    <header class="page-head">
      <div>
        <h2>探测环境变化备案</h2>
        <p class="page-desc">登记站址周边新建建筑、树木生长等环境变化，围绕所属站点、干扰源类型、发现时刻、遮挡方位做备案、核实、整改与销号。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记环境备案</button>
        <button class="btn" type="button" @click="openBatch">批量上报</button>
        <button class="btn" type="button" @click="exportRows">导出备案清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>备案编号</span>
        <input v-model="filters.keyword" placeholder="按备案编号检索" />
      </label>
      <label class="filter-item">
        <span>所属站点</span>
        <input v-model="filters.station" placeholder="按所属站点检索" />
      </label>
      <label class="filter-item">
        <span>干扰源类型</span>
        <input v-model="filters.sourceType" placeholder="按干扰源类型检索" />
      </label>
      <label class="filter-item">
        <span>备案状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td><button class="link" type="button" @click="goDetail(row)">{{ row.备案编号 }}</button></td>
          <td>{{ row.所属站点 }}</td>
          <td>{{ row.干扰源类型 }}</td>
          <td>{{ row.发现时刻 }}</td>
          <td>{{ row.遮挡方位 }}</td>
          <td>{{ row.核实结论 || '—' }}</td>
          <td>{{ row.整改记录 || '—' }}</td>
          <td>{{ row.attachments.length ? `${row.attachments.length} 张` : '—' }}</td>
          <td>{{ row.status }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="goDetail(row)">详情</button>
            <button
              v-for="action in availableActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(row, action)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无环境备案数据，可先登记环境备案</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条环境备案记录</span>
      <span v-if="noticeMessage" class="ok-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记环境备案</h3>
        <label class="form-item">
          <span>所属站点 *</span>
          <input v-model="createForm.所属站点" placeholder="发生环境变化的站点" />
        </label>
        <label class="form-item">
          <span>干扰源类型 *</span>
          <select v-model="createForm.干扰源类型">
            <option value="">请选择</option>
            <option v-for="item in sourceTypes" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="form-item">
          <span>发现时刻 *</span>
          <input v-model="createForm.发现时刻" type="datetime-local" />
        </label>
        <label class="form-item">
          <span>遮挡方位 *</span>
          <select v-model="createForm.遮挡方位">
            <option value="">请选择</option>
            <option v-for="item in directions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="form-item">
          <span>上报人</span>
          <input v-model="createForm.上报人" placeholder="上报人姓名" />
        </label>
        <label class="form-item">
          <span>现场照片</span>
          <input type="file" accept="image/*" multiple @change="onPickPhotos" />
        </label>
        <p v-if="createPhotos.length" class="form-hint">已选 {{ createPhotos.length }} 张照片，登记成功后随附件留存</p>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="submit">提交备案</button>
          <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
        </div>
      </form>
    </div>

    <div v-if="showBatch" class="modal-mask" @click.self="showBatch = false">
      <div class="modal-card wide">
        <h3>批量上报环境备案</h3>
        <p class="form-hint">多人同时上报时逐条填写，提交后每条都会给出回执；同一站点同一干扰源只保留一条。</p>
        <table class="data-table">
          <thead>
            <tr><th>所属站点</th><th>干扰源类型</th><th>发现时刻</th><th>遮挡方位</th><th>上报人</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in batchRows" :key="index">
              <td><input v-model="item.所属站点" placeholder="站点" /></td>
              <td>
                <select v-model="item.干扰源类型">
                  <option value="">请选择</option>
                  <option v-for="type in sourceTypes" :key="type" :value="type">{{ type }}</option>
                </select>
              </td>
              <td><input v-model="item.发现时刻" type="datetime-local" /></td>
              <td>
                <select v-model="item.遮挡方位">
                  <option value="">请选择</option>
                  <option v-for="direction in directions" :key="direction" :value="direction">{{ direction }}</option>
                </select>
              </td>
              <td><input v-model="item.上报人" placeholder="上报人" /></td>
              <td><button class="link" type="button" @click="batchRows.splice(index, 1)">移除</button></td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn" type="button" @click="addBatchRow">再加一条</button>
          <button class="btn primary" type="button" @click="submitBatch">逐条上报</button>
          <button class="btn ghost" type="button" @click="showBatch = false">关闭</button>
        </div>
        <ul v-if="receipts.length" class="receipt-list">
          <li v-for="receipt in receipts" :key="receipt.index" :class="receipt.ok ? 'ok-text' : 'error-text'">
            {{ receipt.message }}
          </li>
        </ul>
      </div>
    </div>

    <div v-if="actionDialog" class="modal-mask" @click.self="actionDialog = null">
      <form class="modal-card" @submit.prevent="submitAction">
        <h3>{{ actionDialog.action }}备案 {{ actionDialog.row.备案编号 }}</h3>
        <p class="form-hint">所属站点：{{ actionDialog.row.所属站点 }} · 干扰源：{{ actionDialog.row.干扰源类型 }} · 遮挡方位：{{ actionDialog.row.遮挡方位 }}</p>
        <label v-if="actionDialog.action === '核实'" class="form-item">
          <span>核实结论 *</span>
          <textarea v-model="actionText" rows="3" placeholder="现场核实后填写结论"></textarea>
        </label>
        <label v-else-if="actionDialog.action === '整改'" class="form-item">
          <span>整改记录 *</span>
          <textarea v-model="actionText" rows="3" placeholder="记录整改措施与完成时间"></textarea>
        </label>
        <p v-else class="form-hint">销号前请确认核实结论已登记：{{ actionDialog.row.核实结论 || '（缺失，无法销号）' }}</p>
        <p v-if="actionError" class="error-text">{{ actionError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="submit">确认{{ actionDialog.action }}</button>
          <button class="btn ghost" type="button" @click="actionDialog = null">取消</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'

interface Attachment {
  name: string
  stored: string
  size: number
}

interface EnvRow {
  id: number
  备案编号: string
  所属站点: string
  干扰源类型: string
  发现时刻: string
  遮挡方位: string
  上报人: string
  核实结论: string
  整改记录: string
  status: string
  attachments: Attachment[]
}

interface Receipt {
  index: number
  ok: boolean
  message: string
}

const ENDPOINT = '/api/environment'
const columns = ['备案编号', '所属站点', '干扰源类型', '发现时刻', '遮挡方位', '核实结论', '整改记录', '现场照片', '备案状态']
const statuses = ['待核实', '已核实', '已整改', '已销号']
const sourceTypes = ['新建建筑物', '树木生长', '施工围挡', '新增杆塔', '堆积物', '其他']
const directions = ['东', '东南', '南', '西南', '西', '西北', '北', '东北']
const ACTION_BY_STATUS: Record<string, string[]> = {
  待核实: ['核实'],
  已核实: ['整改'],
  已整改: ['销号'],
  已销号: [],
}

const router = useRouter()

const rows = ref<EnvRow[]>([])
const total = ref(0)
const stats = ref([
  { label: '待核实', value: 0 },
  { label: '已核实', value: 0 },
  { label: '已整改', value: 0 },
  { label: '已销号', value: 0 },
])
const filters = ref({ keyword: '', station: '', sourceType: '', status: '' })
// 导出以上一次查询生效的条件为准，保证导出条数与页面统计对得上。
const appliedFilters = ref({ ...filters.value })
const noticeMessage = ref('')
const errorMessage = ref('')

const showCreate = ref(false)
const createForm = ref({ 所属站点: '', 干扰源类型: '', 发现时刻: '', 遮挡方位: '', 上报人: '' })
const createPhotos = ref<File[]>([])
const createError = ref('')

const showBatch = ref(false)
const batchRows = ref<Array<{ 所属站点: string; 干扰源类型: string; 发现时刻: string; 遮挡方位: string; 上报人: string }>>([])
const receipts = ref<Receipt[]>([])

const actionDialog = ref<{ row: EnvRow; action: string } | null>(null)
const actionText = ref('')
const actionError = ref('')

function availableActions(row: EnvRow) {
  return ACTION_BY_STATUS[row.status] ?? []
}

function buildQuery(source: Record<string, string>, withStatus = true) {
  const params = new URLSearchParams()
  if (source.keyword) params.set('keyword', source.keyword)
  if (source.station) params.set('station', source.station)
  if (source.sourceType) params.set('source_type', source.sourceType)
  if (withStatus && source.status) params.set('status', source.status)
  return params.toString()
}

function resetFilters() {
  filters.value = { keyword: '', station: '', sourceType: '', status: '' }
  void reload()
}

function openCreate() {
  createForm.value = { 所属站点: '', 干扰源类型: '', 发现时刻: '', 遮挡方位: '', 上报人: '' }
  createPhotos.value = []
  createError.value = ''
  showCreate.value = true
}

function onPickPhotos(event: Event) {
  const input = event.target as HTMLInputElement
  createPhotos.value = Array.from(input.files ?? [])
}

function openBatch() {
  batchRows.value = [emptyBatchRow()]
  receipts.value = []
  showBatch.value = true
}

function emptyBatchRow() {
  return { 所属站点: '', 干扰源类型: '', 发现时刻: '', 遮挡方位: '', 上报人: '' }
}

function addBatchRow() {
  batchRows.value.push(emptyBatchRow())
}

function goDetail(row: EnvRow) {
  void router.push(`/environment/${row.id}`)
}

async function uploadPhotos(entryId: number, files: File[]) {
  for (const file of files) {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`${ENDPOINT}/${entryId}/attachments`, { method: 'POST', body: form })
    if (!response.ok) {
      throw new Error(`现场照片 ${file.name} 留存失败`)
    }
  }
}

async function submitCreate() {
  createError.value = ''
  const values = { ...createForm.value, 发现时刻: createForm.value.发现时刻.replace('T', ' ') }
  try {
    const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values }) })
    const payload = await response.json()
    if (!payload.ok) {
      createError.value = payload.message ?? '备案登记未生效'
      return
    }
    const entryId = Number(payload.entry?.id)
    if (createPhotos.value.length && entryId) {
      await uploadPhotos(entryId, createPhotos.value)
    }
    showCreate.value = false
    noticeMessage.value = payload.message ?? '环境备案已登记'
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '备案登记失败'
  }
}

async function submitBatch() {
  receipts.value = []
  const reports = batchRows.value.map((item) => ({ ...item, 发现时刻: item.发现时刻.replace('T', ' ') }))
  try {
    const response = await request(`${ENDPOINT}/batch`, { method: 'POST', body: JSON.stringify({ reports }) })
    const payload = await response.json()
    receipts.value = payload.receipts ?? []
    await reload()
  } catch (error) {
    receipts.value = [{ index: 0, ok: false, message: error instanceof Error ? error.message : '批量上报失败' }]
  }
}

function openAction(row: EnvRow, action: string) {
  actionDialog.value = { row, action }
  actionText.value = ''
  actionError.value = ''
}

async function submitAction() {
  if (!actionDialog.value) return
  const { row, action } = actionDialog.value
  actionError.value = ''
  const values: Record<string, string> = { action }
  if (action === '核实') values.核实结论 = actionText.value
  if (action === '整改') values.整改记录 = actionText.value
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      actionError.value = payload.message ?? `${action}未生效`
      return
    }
    actionDialog.value = null
    noticeMessage.value = payload.message ?? `备案已${action}`
    await reload()
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : '备案操作失败'
  }
}

async function exportRows() {
  errorMessage.value = ''
  noticeMessage.value = ''
  const query = buildQuery(appliedFilters.value)
  try {
    const response = await request(`${ENDPOINT}/export?${query}`)
    if (!response.ok) {
      throw new Error('备案清单导出失败')
    }
    const text = await response.text()
    const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0)
    const exported = Math.max(lines.length - 1, 0)
    const blob = new Blob([text], { type: 'text/csv;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = '探测环境变化备案清单.csv'
    link.click()
    URL.revokeObjectURL(link.href)
    noticeMessage.value = exported === total.value
      ? `已导出 ${exported} 条备案，与页面统计一致`
      : `导出 ${exported} 条，与页面统计 ${total.value} 条不一致，请重新查询后再导出`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '备案清单导出失败'
  }
}

async function reload() {
  errorMessage.value = ''
  noticeMessage.value = ''
  appliedFilters.value = { ...filters.value }
  try {
    const response = await request(`${ENDPOINT}?${buildQuery(filters.value)}`)
    if (!response.ok) {
      throw new Error('环境备案列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await loadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '环境备案列表读取失败'
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats?${buildQuery(filters.value, false)}`)
    if (!response.ok) return
    const payload = await response.json()
    const byStatus = (payload.byStatus ?? {}) as Record<string, number>
    stats.value = stats.value.map((item) => ({ ...item, value: byStatus[item.label] ?? 0 }))
  } catch {
    // 统计卡片失败不阻塞列表
  }
}

onMounted(reload)
</script>
