<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ loading: boolean }>()
const emit = defineEmits<{ (e: 'search', query: string): void }>()

const input = ref('')

function submit() {
  const q = input.value.trim()
  if (!q || props.loading) return
  emit('search', q)
}
</script>

<template>
  <div class="search-bar">
    <input
      v-model="input"
      type="text"
      placeholder="e.g. sci-fi movies from the 80s, breaking bad, action films with keanu reeves…"
      :disabled="loading"
      @keydown.enter="submit"
    />
    <button :disabled="loading || !input.trim()" @click="submit">
      <span v-if="loading" class="spinner"></span>
      <span v-else>Search</span>
    </button>
  </div>
</template>

<style scoped>
.search-bar {
  display: flex;
  gap: 0.5rem;
  width: 100%;
  max-width: 800px;
}

input {
  flex: 1;
  background: #16213e;
  border: 2px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  color: #cdd6f4;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
}

input:focus { border-color: var(--plex-yellow); }
input::placeholder { color: var(--text-muted); }
input:disabled { opacity: 0.6; }

button {
  background: var(--plex-yellow);
  color: #000;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  min-width: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

button:hover:not(:disabled) { background: #f0b429; }
button:disabled { opacity: 0.6; cursor: not-allowed; }

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(0,0,0,0.3);
  border-top-color: #000;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
