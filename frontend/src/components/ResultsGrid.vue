<script setup lang="ts">
import type { MediaResult } from '@/stores/search'
import MediaCard from './MediaCard.vue'

defineProps<{
  results: MediaResult[]
  query: string
  filtersUsed: Record<string, unknown> | null
  loading: boolean
  error: string | null
}>()
</script>

<template>
  <div class="results-section">
    <div v-if="filtersUsed && query" class="filter-summary">
      <span>Results for <strong>"{{ query }}"</strong></span>
      <span v-if="filtersUsed.media_type" class="filter-pill">
        {{ (filtersUsed.media_type as string) === 'movie' ? 'Movies' : 'TV Shows' }}
      </span>
      <span v-if="filtersUsed.genres" class="filter-pill">
        {{ (filtersUsed.genres as string[]).join(', ') }}
      </span>
      <span v-if="filtersUsed.year_from || filtersUsed.year_to" class="filter-pill">
        {{ filtersUsed.year_from ?? '…' }}–{{ filtersUsed.year_to ?? 'now' }}
      </span>
      <span v-if="filtersUsed.min_rating" class="filter-pill">
        ★ ≥ {{ filtersUsed.min_rating }}
      </span>
    </div>

    <p v-if="error" class="error-msg">{{ error }}</p>

    <div v-else-if="loading" class="loading-grid">
      <div v-for="i in 12" :key="i" class="skeleton-card"></div>
    </div>

    <div v-else-if="results.length === 0 && query" class="empty-state">
      No results found for "{{ query }}". Try a different query.
    </div>

    <div v-else class="grid">
      <MediaCard v-for="item in results" :key="item.plex_key" :item="item" />
    </div>
  </div>
</template>

<style scoped>
.results-section { width: 100%; }

.filter-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.filter-pill {
  background: #0f3460;
  color: #8e9bb5;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.8rem;
}

.error-msg {
  color: #ff6b6b;
  text-align: center;
  padding: 2rem;
}

.empty-state {
  color: var(--text-muted);
  text-align: center;
  padding: 4rem 2rem;
  font-size: 1rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
}

.loading-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
}

.skeleton-card {
  aspect-ratio: 2/3;
  background: linear-gradient(90deg, #16213e 25%, #1e2d50 50%, #16213e 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 10px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
