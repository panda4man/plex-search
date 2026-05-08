<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const error = ref<string | null>(null)

const route = new URLSearchParams(window.location.search)
if (route.get('error') === 'auth_failed') {
  error.value = 'Plex authorization failed. Please try again.'
}

async function signIn() {
  loading.value = true
  error.value = null
  try {
    await auth.startLogin()
  } catch {
    error.value = 'Failed to start login. Check that the backend is running.'
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1>PlexSearch</h1>
      <p class="subtitle">Natural language search for your Plex library</p>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="plex-btn" :disabled="loading" @click="signIn">
        <span v-if="loading">Redirecting to Plex…</span>
        <span v-else>Sign in with Plex</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a2e;
}

.login-card {
  background: #16213e;
  border-radius: 12px;
  padding: 3rem;
  text-align: center;
  max-width: 380px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

h1 {
  color: #e5a00d;
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: #8e9bb5;
  margin-bottom: 2rem;
  font-size: 0.95rem;
}

.error {
  color: #ff6b6b;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

.plex-btn {
  background: #e5a00d;
  color: #000;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 2rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
  width: 100%;
}

.plex-btn:hover:not(:disabled) {
  background: #f0b429;
}

.plex-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
