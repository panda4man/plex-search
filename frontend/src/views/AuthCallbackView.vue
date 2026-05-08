<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const error = ref<string | null>(null)

onMounted(async () => {
  const pinId = route.query.pinId as string
  if (!pinId) {
    router.replace('/login?error=auth_failed')
    return
  }

  try {
    await auth.completeLogin(pinId)
    if (auth.isAuthenticated) {
      router.replace('/')
    } else {
      router.replace('/login?error=auth_failed')
    }
  } catch {
    error.value = 'Authorization failed. Please try again.'
    setTimeout(() => router.replace('/login?error=auth_failed'), 2000)
  }
})
</script>

<template>
  <div class="callback-page">
    <div v-if="!error" class="spinner-container">
      <div class="spinner"></div>
      <p>Completing sign-in…</p>
    </div>
    <div v-else class="error-container">
      <p class="error">{{ error }}</p>
      <p>Redirecting to login…</p>
    </div>
  </div>
</template>

<style scoped>
.callback-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a2e;
  color: #cdd6f4;
  flex-direction: column;
  gap: 1rem;
}

.spinner-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #2a2a4e;
  border-top-color: #e5a00d;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error { color: #ff6b6b; }
</style>
