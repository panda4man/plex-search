<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '@/api'

const status = ref<{
  state: string
  total: number
  indexed: number
  last_run: string | null
  error: string | null
} | null>(null)

const message = ref<string | null>(null)
const loading = ref(false)
let pollInterval: ReturnType<typeof setInterval> | null = null

async function fetchStatus() {
  try {
    const res = await api.get('/admin/index-status')
    status.value = res.data
  } catch {
    // non-fatal
  }
}

function startPolling() {
  if (pollInterval) return
  pollInterval = setInterval(fetchStatus, 3000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

async function reindex() {
  loading.value = true
  message.value = null
  try {
    const res = await api.post('/admin/reindex')
    message.value = res.data.message
    startPolling()
  } catch {
    message.value = 'Failed to start reindex.'
  } finally {
    loading.value = false
  }
}

async function clearReindex() {
  loading.value = true
  message.value = null
  try {
    const res = await api.post('/admin/clear-reindex')
    message.value = res.data.message
    startPolling()
  } catch {
    message.value = 'Failed to start clear-reindex.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchStatus()
  if (status.value?.state === 'running') startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div class="admin">
    <h1>Admin</h1>

    <section class="card">
      <h2>Search Index</h2>

      <div v-if="status" class="status-grid">
        <div class="stat">
          <span class="label">State</span>
          <span :class="['value', 'state-' + status.state]">{{ status.state }}</span>
        </div>
        <div class="stat">
          <span class="label">Indexed</span>
          <span class="value">{{ status.indexed }} / {{ status.total }}</span>
        </div>
        <div class="stat">
          <span class="label">Last run</span>
          <span class="value">{{ status.last_run ? new Date(status.last_run).toLocaleString() : '—' }}</span>
        </div>
        <div v-if="status.error" class="stat error-stat">
          <span class="label">Error</span>
          <span class="value error-text">{{ status.error }}</span>
        </div>
      </div>

      <div v-if="status?.state === 'running'" class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: status.total ? (status.indexed / status.total * 100) + '%' : '0%' }"
        ></div>
      </div>

      <p v-if="message" class="message">{{ message }}</p>

      <div class="actions">
        <button
          class="btn btn-primary"
          :disabled="loading || status?.state === 'running'"
          @click="reindex"
        >
          Reindex new items
        </button>
        <button
          class="btn btn-danger"
          :disabled="loading || status?.state === 'running'"
          @click="clearReindex"
        >
          Clear &amp; full reindex
        </button>
      </div>

      <p class="hint">
        <strong>Reindex new items</strong> — adds content added to Plex since last run.<br>
        <strong>Clear &amp; full reindex</strong> — wipes all vectors and rebuilds from scratch. Required after schema changes.
      </p>
    </section>
  </div>
</template>

<style scoped>
.admin {
  max-width: 700px;
  margin: 0 auto;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

h1 {
  font-size: 1.5rem;
  color: var(--plex-yellow);
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

h2 {
  font-size: 1rem;
  font-weight: 600;
  color: #cdd6f4;
  margin: 0;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.value {
  font-size: 0.95rem;
  color: #cdd6f4;
  font-weight: 500;
}

.state-running { color: var(--plex-yellow); }
.state-done    { color: #a6e3a1; }
.state-error   { color: #f38ba8; }
.state-idle    { color: var(--text-muted); }
.error-text    { color: #f38ba8; font-size: 0.8rem; }

.progress-bar {
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--plex-yellow);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.btn {
  border: none;
  border-radius: 8px;
  padding: 0.6rem 1.2rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary {
  background: var(--plex-yellow);
  color: #000;
}

.btn-primary:hover:not(:disabled) { background: #f0b429; }

.btn-danger {
  background: #f38ba8;
  color: #000;
}

.btn-danger:hover:not(:disabled) { background: #ff8fa5; }

.message {
  font-size: 0.85rem;
  color: #a6e3a1;
}

.hint {
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.6;
}
</style>
