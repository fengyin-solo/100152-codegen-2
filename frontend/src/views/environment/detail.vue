<template>
  <section class="page" data-module="environment-detail">
    <header class="page-head">
      <div>
        <h2>备案详情 {{ entry?.备案编号 ?? '' }}</h2>
        <p class="page-desc">查看备案明细、现场照片与核实整改记录；从清单进入再返回，遮挡方位与整改记录保持一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回备案清单</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    <p v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</p>

    <template v-if="entry">
      <div class="panel">
        <h3 class="panel-title">备案信息</h3>
        <dl class="detail-grid">
          <div v-for="field in detailFields" :key="field" class="detail-item">
            <dt>{{ field }}</dt>
            <dd>{{ entry[field] || '—' }}</dd>
          </div>
          <div class="detail-item">
            <dt>重复上报次数</dt>
            <dd>{{ entry['重复上报次数'] ?? 0 }}</dd>
          </div>
        </dl>
        <div class="panel-actions">
          <button
            v-for="action in availableActions"
            :key="action"
            class="btn primary"
            type="button"
            @click="openAction(action)"
          >
            {{ action }}
          </button>
          <span v-if="!availableActions.length" class="muted-text">已销号，不可再核实或变更</span>
        </div>
      </div>

      <div class="panel">
        <h3 class="panel-title">现场照片（文件附件）</h3>
        <table class="data-table">
          <thead>
            <tr><th>文件名</th><th>大小</th><th>上传时刻</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in attachments" :key="item.stored">
              <td>{{ item.filename }}</td>
              <td>{{ formatSize(item.size) }}</td>
              <td>{{ item.uploaded_at }}</td>
              <td>
                <a class="link" :href="`${ENDPOINT}/${entryId}/attachments/${item.stored}`">下载</a>
              </td>
            </tr>
            <tr v-if="!attachments.length">
              <td colspan="4" class="empty-state">暂无现场照片，可下方上传</td>
            </tr>
          </tbody>
        </table>
        <div class="panel-actions upload-row">
          <input type="file" accept="image/*" @change="uploadPhoto" />
        </div>
      </div>
    </template>

    <div v-if="actionDialog" class="modal-mask" @click.self="closeAction">
      <div class="modal">
        <h3 class="panel-title">{{ actionDialog.action }} · {{ entry?.备案编号 }}</h3>
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
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Attachment = { filename: string; stored: string; size: number; uploaded_at: string }
type Entry = Record<string, string | number | Attachment[] | null>
type ActionDialog = { action: string; field: string | null; text: string; error: string }

const ENDPOINT = '/api/environment'
const detailFields = ["备案编号", "所属站点", "干扰源类型", "发现时刻", "遮挡方位", "上报人", "登记时刻", "核实结论", "整改记录", "备案状态"]
const ACTION_FIELDS: Record<string, string | null> = { 核实: '核实结论', 整改: '整改记录', 销号: null }

const route = useRoute()
const router = useRouter()
const entryId = String(route.params.id)

const entry = ref<Entry | null>(null)
const errorMessage = ref('')
const noticeMessage = ref('')
const actionDialog = ref<ActionDialog | null>(null)

const attachments = computed<Attachment[]>(() => {
  const value = entry.value?.attachments
  return Array.isArray(value) ? (value as Attachment[]) : []
})

const availableActions = computed<string[]>(() => {
  const status = String(entry.value?.['备案状态'] ?? '')
  if (status === '待核实') return ['核实']
  if (status === '已核实') return ['整改']
  if (status === '已整改') return ['销号']
  return []
})

function formatSize(size: number) {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${size} B`
}

function goBack() {
  void router.push({ name: 'environment', query: route.query })
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}`)
    if (!response.ok) throw new Error(`备案 ${entryId} 不存在或已归档`)
    entry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '备案详情读取失败'
  }
}

function openAction(action: string) {
  actionDialog.value = { action, field: ACTION_FIELDS[action] ?? null, text: '', error: '' }
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
    const response = await request(`${ENDPOINT}/${entryId}/actions`, {
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

async function uploadPhoto(event: Event) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  try {
    // 文件上传不能带 JSON 头，置空让浏览器自己拼 multipart 边界
    const response = await request(`${ENDPOINT}/${entryId}/attachments`, {
      method: 'POST',
      headers: {},
      body: form,
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '照片上传未生效'
      return
    }
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '照片上传失败'
  } finally {
    input.value = ''
  }
}

onMounted(reload)
</script>

<style scoped>
.panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.panel-title { margin: 0 0 10px; font-size: 14px; }
.detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin: 0; }
.detail-item dt { color: var(--muted); font-size: 12px; }
.detail-item dd { margin: 2px 0 0; font-size: 13px; }
.panel-actions { display: flex; gap: 8px; margin-top: 10px; align-items: center; }
.muted-text { color: var(--muted); font-size: 12px; }
.notice-text { color: #067647; }
.upload-row input { font-size: 13px; }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.4); display: flex; align-items: center; justify-content: center; }
.modal { background: #fff; border-radius: 8px; padding: 16px; width: 420px; }
.modal-field textarea { width: 100%; }
.modal-tip { font-size: 13px; color: var(--muted); }
</style>
