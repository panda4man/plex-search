import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<{ username: string } | null>(null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => user.value !== null)

  async function checkSession() {
    try {
      const res = await api.get('/auth/me')
      user.value = res.data.authenticated ? { username: res.data.username } : null
    } catch {
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  async function startLogin() {
    const res = await api.get('/auth/plex/start')
    sessionStorage.setItem('plex_pin_id', String(res.data.pin_id))
    window.location.href = res.data.auth_url
  }

  async function completeLogin(pinId: string) {
    const res = await api.get(`/auth/plex/callback?pinId=${pinId}`)
    if (res.data.success) {
      user.value = { username: res.data.username }
    }
  }

  async function logout() {
    await api.post('/auth/logout')
    user.value = null
  }

  return { user, initialized, isAuthenticated, checkSession, startLogin, completeLogin, logout }
})
