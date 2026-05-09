import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'

export interface MediaResult {
  plex_key: string
  title: string
  year: number | null
  genres: string[]
  summary: string
  rating: number | null
  duration_minutes: number | null
  thumb_url: string | null
  media_type: 'movie' | 'show'
  machine_id: string
  plex_web_url: string
  plex_app_url: string
  seasons: number | null
  studio: string | null
}

export const useSearchStore = defineStore('search', () => {
  const query = ref('')
  const results = ref<MediaResult[]>([])
  const filtersUsed = ref<Record<string, unknown> | null>(null)
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function search(q: string) {
    query.value = q
    loading.value = true
    error.value = null
    try {
      const res = await api.post('/search', { query: q })
      results.value = res.data.results
      filtersUsed.value = res.data.filters_used
      total.value = res.data.total
    } catch {
      error.value = 'Search failed. Please try again.'
      results.value = []
    } finally {
      loading.value = false
    }
  }

  async function loadRecent() {
    loading.value = true
    error.value = null
    try {
      const res = await api.get('/search/recent')
      results.value = res.data.results
      total.value = res.data.total
      filtersUsed.value = null
    } catch {
      error.value = 'Failed to load recent items.'
    } finally {
      loading.value = false
    }
  }

  return { query, results, filtersUsed, total, loading, error, search, loadRecent }
})
