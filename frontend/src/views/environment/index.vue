<template>
  <section class="page" data-module="environment">
    <header class="page-head">
      <div>
        <h2>探测环境变化备案</h2>
        <p class="page-desc">登记站址周边新建建筑、树木生长等环境变化，按待核实、已核实、已整改、已销号推进，现场照片随备案留存。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="toggleCreate">登记环境备案</button>
        <button class="btn" type="button" @click="toggleBatch">批量上报</button>
        <button class="btn" type="button" @click="exportRows">导出备案清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="panel" @submit.prevent="submitCreate">
      <h3 class="panel-title">登记环境备案</h3>
      <div class="form-grid">
        <label class="filter-item">
          <span>所属站点</span>
          <input v-model="createForm.所属站点" placeholder="如：城东国家基本气象站" />
        </label>
        <label class="filter-item">
          <span>干扰源类型</span>
          <select v-model="createForm.干扰源类型">
            <option value="">请选择</option>
            <option v-for="item in sourceTypes" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>发现时刻</span>
          <input v-model="createForm.发现时刻" type="datetime-local" />
        </label>
        <label class="filter-item">
          <span>遮挡方位</span>
          <select v-model="createForm.遮挡方位">
            <option value="">请选择</option>
            <option v-for="item in directions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>上报人</span>
          <input v-model="createForm.上报人" placeholder="上报人姓名" />
        </label>
      </div>
      <div class="panel-actions">
        <button class="btn primary" type="submit">提交备案</button>
        <button class="btn ghost" type="button" @click="showCreate = false">收起</button>
      </div>
    </form>

    <div v-if="showBatch" class="panel">
      <h3 class="panel-title">批量上报（多人同时上报，逐条回执）</h3>
      <table class="data-table batch-table">
        <thead>
          <tr>
            <th>所属站点</th>
            <th>干扰源类型</th>
            <th>发现时刻</th>
            <th>遮挡方位</th>
            <th>上报人</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in batchRows" :key="index">
            <td><input v-model="row.所属站点" placeholder="站点名称" /></td>
            <td>
              <select v-model="row.干扰源类型">
                <option value="">请选择</option>
                <option v-for="item in sourceTypes" :key="item" :value="item">{{ item }}</option>
              </select>
            </td>
            <td><input v-model="row.发现时刻" type="datetime-local" /></td>
            <td>
              <select v-model="row.遮挡方位">
                <option value="">请选择</option>
                <option v-for="item in directions" :key="item" :value="item">{{ item }}</option>
              </select>
            </td>
            <td><input v-model="row.上报人" placeholder="上报人" /></td>
            <td>
              <button class="link" type="button" @click="batchRows.splice(index, 1)">移除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="panel-actions">
        <button class="btn" type="button" @click="addBatchRow">添加一行</button>
        <button class="btn primary" type="button" @click="submitBatch">提交批量上报</button>
        <button class="btn ghost" type="button" @click="showBatch = false">收起</button>
      </div>
      <ul v-if="receipts.length" class="receipt-list">
        <li v-for="receipt in receipts" :key="receipt.序号" :class="receipt.ok ? 'receipt-ok' : 'receipt-fail'">
          第 {{ receipt.序号 }} 条：{{ receipt.message }}
        </li>
      </ul>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>所属站点</span>
        <input v-model="filters.station" placeholder="按站点检索" />
      </label>
      <label class="filter-item">
        <span>干扰源类型</span>
        <input v-model="filters.source_type" placeholder="按干扰源类型检索" />
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actionsFor(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!actionsFor(row).length" class="muted-text">已办结</span>
            <RouterLink
              class="link"
              :to="{ name: 'environment-detail', params: { id: row.id }, query: route.query }"
            >
              详情
            </RouterLink>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无环境备案数据，可先登记环境备案</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条环境备案记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="actionDialog" class="modal-mask" @click.self="closeAction">
      <div class="modal">
        <h3 class="panel-title">{{ actionDialog.action }} · {{ actionDialog.row['备案编号'] }}</h3>
        <template v-if="actionDialog.field">
          <label class="filter-item modal-field">
            <span>{{ actionDialog.field }}</span>
            <textarea v-model="actionDialog.text" rows="3" :placeholder="`请填写${actionDialog.field}`"></textarea>
          </label>
        </template>
        <p v-else class="modal-tip">确认对该备案执行销号？销号后不可再核实或变更。</p>
        <p v-if="actionDialog.error" class="error-text">{{ actionDialog.error }}</p>
        <div class="panel-actions">
          <button class="btn primary" type="button" @click="confirmAction">确认{{ actionDialog.action }}</button>
          <button class="btn ghost" type="button" @click="closeAction">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Receipt = { 序号: number; ok: boolean; message: string }
type ActionDialog = { action: string; row: Row; field: string | null; text: string; error: string }

const ENDPOINT = '/api/environment'
const columns = ["备案编号", "所属站点", "干扰源类型", "发现时刻", "遮挡方位", "上报人", "整改记录", "备案状态"]
const statuses = ["待核实", "已核实", "已整改", "已销号"]
const sourceTypes = ["新建建筑物", "树木生长", "构筑物施工", "施工围挡", "广告牌", "其他"]
const directions = ["东", "东南", "南", "西南", "西", "西北", "北", "东北"]
const ACTION_FIELDS: Record<string, string | null> = { 核实: '核实结论', 整改: '整改记录', 销号: null }

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const stats = ref([{ label: '待核实', value: 0 }, { label: '已核实', value: 0 }, { label: '已整改', value: 0 }, { label: '已销号', value: 0 }])
const filters = ref<Record<string, string>>({
  station: String(route.query.station ?? ''),
  source_type: String(route.query.source_type ?? ''),
  status: String(route.query.status ?? ''),
})

const showCreate = ref(false)
const showBatch = ref(false)
const emptyForm = () => ({ 所属站点: '', 干扰源类型: '', 发现时刻: '', 遮挡方位: '', 上报人: '' })
const createForm = ref(emptyForm())
const batchRows = ref<Record<string, string>[]>([emptyForm()])
const receipts = ref<Receipt[]>([])
const actionDialog = ref<ActionDialog | null>(null)

function toggleCreate() {
  showCreate.value = !showCreate.value
  if (showCreate.value) showBatch.value = false
}

function toggleBatch() {
  showBatch.value = !showBatch.value
  if (showBatch.value) showCreate.value = false
}

function addBatchRow() {
  batchRows.value.push(emptyForm())
}

function activeFilters() {
  return Object.fromEntries(Object.entries(filters.value).filter(([, value]) => value.trim() !== ''))
}

function applyFilters() {
  void router.replace({ query: activeFilters() })
  void reload()
}

function resetFilters() {
  filters.value = { station: '', source_type: '', status: '' }
  void router.replace({ query: {} })
  void reload()
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(activeFilters()).toString()
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok) throw new Error('环境备案列表读取失败')
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (statsResponse.ok) {
      const statPayload = await statsResponse.json()
      stats.value = stats.value.map((item) => ({ ...item, value: Number(statPayload[item.label] ?? 0) }))
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '环境备案列表读取失败'
  }
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '备案登记未生效'
      return
    }
    noticeMessage.value = payload.message
    createForm.value = emptyForm()
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '备案登记失败'
  }
}

async function submitBatch() {
  errorMessage.value = ''
  noticeMessage.value = ''
  receipts.value = []
  const reports = batchRows.value.filter((row) => Object.values(row).some((value) => value.trim() !== ''))
  if (!reports.length) {
    errorMessage.value = '批量上报内容为空'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/batch`, {
      method: 'POST',
      body: JSON.stringify({ reports }),
    })
    const payload = await response.json()
    receipts.value = payload.receipts ?? []
    noticeMessage.value = `批量上报完成：共 ${payload.total} 条，登记成功 ${payload.accepted} 条`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批量上报失败'
  }
}

function actionsFor(row: Row): string[] {
  const status = String(row['备案状态'] ?? '')
  if (status === '待核实') return ['核实']
  if (status === '已核实') return ['整改']
  if (status === '已整改') return ['销号']
  return []
}

function openAction(action: string, row: Row) {
  actionDialog.value = { action, row, field: ACTION_FIELDS[action] ?? null, text: '', error: '' }
}

function closeAction() {
  actionDialog.value = null
}

async function confirmAction() {
  const dialog = actionDialog.value
  if (!dialog) return
  dialog.error = ''
  if (dialog.field && !dialog.text.trim()) {
    dialog.error = `${dialog.field}缺失，不能执行${dialog.action}`
    return
  }
  const values: Record<string, string> = { action: dialog.action }
  if (dialog.field) values[dialog.field] = dialog.text.trim()
  try {
    const response = await request(`${ENDPOINT}/${dialog.row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      dialog.error = payload.message ?? '动作未生效'
      return
    }
    noticeMessage.value = payload.message
    actionDialog.value = null
    await reload()
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '动作执行失败'
  }
}

async function exportRows() {
  errorMessage.value = ''
  noticeMessage.value = ''
  const query = new URLSearchParams(activeFilters()).toString()
  try {
    const response = await request(`${ENDPOINT}/export?${query}`)
    if (!response.ok) throw new Error('备案清单导出失败')
    const exported = Number(response.headers.get('X-Total-Count') ?? '0')
    const blob = await response.blob()
    const text = await blob.text()
    const fileRows = Math.max(text.split(/\r?\n/).filter((line) => line.trim() !== '').length - 1, 0)
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const match = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
    const filename = match ? decodeURIComponent(match[1]) : 'environment-filings.csv'
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
    if (exported === total.value && fileRows === total.value) {
      noticeMessage.value = `已导出 ${exported} 条，与页面统计一致`
    } else {
      errorMessage.value = `导出条数（回执 ${exported}、文件 ${fileRows}）与页面统计 ${total.value} 不一致，请重试`
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '备案清单导出失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.panel-title { margin: 0 0 10px; font-size: 14px; }
.form-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.panel-actions { display: flex; gap: 8px; margin-top: 10px; }
.batch-table input, .batch-table select { width: 100%; }
.receipt-list { margin: 10px 0 0; padding-left: 18px; font-size: 13px; }
.receipt-ok { color: #067647; }
.receipt-fail { color: #b42318; }
.muted-text { color: var(--muted); font-size: 12px; }
.notice-text { color: #067647; }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.4); display: flex; align-items: center; justify-content: center; }
.modal { background: #fff; border-radius: 8px; padding: 16px; width: 420px; }
.modal-field textarea { width: 100%; }
.modal-tip { font-size: 13px; color: var(--muted); }
</style>
