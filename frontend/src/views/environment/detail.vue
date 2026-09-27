<template>
  <section class="page" data-module="environment-detail">
    <header class="page-head">
      <div>
        <h2>环境备案详情</h2>
        <p class="page-desc">查看单条备案的遮挡方位、核实结论与整改记录，并在状态允许时推进核实、整改、销号。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回备案清单</button>
      </div>
    </header>

    <template v-if="entry">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">备案状态</span>
          <strong class="stat-value">{{ entry.status }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">遮挡方位</span>
          <strong class="stat-value">{{ entry.遮挡方位 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">现场照片</span>
          <strong class="stat-value">{{ entry.attachments.length }} 张</strong>
        </article>
      </div>

      <table class="data-table detail-table">
        <tbody>
          <tr><th>备案编号</th><td>{{ entry.备案编号 }}</td></tr>
          <tr><th>所属站点</th><td>{{ entry.所属站点 }}</td></tr>
          <tr><th>干扰源类型</th><td>{{ entry.干扰源类型 }}</td></tr>
          <tr><th>发现时刻</th><td>{{ entry.发现时刻 }}</td></tr>
          <tr><th>遮挡方位</th><td>{{ entry.遮挡方位 }}</td></tr>
          <tr><th>上报人</th><td>{{ entry.上报人 || '—' }}</td></tr>
          <tr><th>核实结论</th><td>{{ entry.核实结论 || '—' }}</td></tr>
          <tr><th>整改记录</th><td>{{ entry.整改记录 || '—' }}</td></tr>
          <tr><th>备案状态</th><td>{{ entry.status }}</td></tr>
        </tbody>
      </table>

      <section class="detail-section">
        <h3>现场照片附件</h3>
        <ul v-if="entry.attachments.length" class="attachment-list">
          <li v-for="item in entry.attachments" :key="item.stored">
            <a :href="`${ENDPOINT}/${entry.id}/attachments/${item.stored}`" target="_blank" rel="noopener">
              {{ item.name }}
            </a>
            <span class="form-hint">（{{ formatSize(item.size) }}）</span>
          </li>
        </ul>
        <p v-else class="form-hint">暂无现场照片，可在此补传。</p>
        <label class="form-item upload-item">
          <span>补传照片</span>
          <input type="file" accept="image/*" multiple @change="uploadAttachments" />
        </label>
      </section>

      <section class="detail-section">
        <h3>备案推进</h3>
        <p v-if="entry.status === '已销号'" class="form-hint">该备案已销号，干扰源不得再被重新核实。</p>
        <div v-else class="modal-actions">
          <template v-if="entry.status === '待核实'">
            <textarea v-model="actionText" rows="3" placeholder="现场核实后填写核实结论"></textarea>
            <button class="btn primary" type="button" @click="runAction('核实')">核实</button>
          </template>
          <template v-else-if="entry.status === '已核实'">
            <textarea v-model="actionText" rows="3" placeholder="记录整改措施与完成时间"></textarea>
            <button class="btn primary" type="button" @click="runAction('整改')">整改</button>
          </template>
          <template v-else-if="entry.status === '已整改'">
            <button class="btn primary" type="button" @click="runAction('销号')">销号</button>
          </template>
        </div>
      </section>
    </template>

    <footer class="page-foot">
      <span v-if="noticeMessage" class="ok-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

interface Attachment {
  name: string
  stored: string
  size: number
}

interface EnvDetail {
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

const ENDPOINT = '/api/environment'

const route = useRoute()
const router = useRouter()

const entry = ref<EnvDetail | null>(null)
const actionText = ref('')
const noticeMessage = ref('')
const errorMessage = ref('')

function goBack() {
  void router.push('/environment')
}

function formatSize(size: number) {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${size} B`
}

async function runAction(action: string) {
  if (!entry.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  const values: Record<string, string> = { action }
  if (action === '核实') values.核实结论 = actionText.value
  if (action === '整改') values.整改记录 = actionText.value
  try {
    const response = await request(`${ENDPOINT}/${entry.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? `${action}未生效`
      return
    }
    actionText.value = ''
    noticeMessage.value = payload.message ?? `备案已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '备案操作失败'
  }
}

async function uploadAttachments(event: Event) {
  if (!entry.value) return
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    for (const file of files) {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch(`${ENDPOINT}/${entry.value.id}/attachments`, { method: 'POST', body: form })
      if (!response.ok) {
        throw new Error(`现场照片 ${file.name} 留存失败`)
      }
    }
    if (files.length) {
      noticeMessage.value = `已留存 ${files.length} 张现场照片`
    }
    input.value = ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '照片留存失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const id = String(route.params.id ?? '')
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    if (!response.ok) {
      throw new Error(`备案 ${id} 不存在或已归档`)
    }
    entry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '备案详情读取失败'
  }
}

onMounted(reload)
</script>
