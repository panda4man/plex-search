<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api'
import SearchBar from '@/components/SearchBar.vue'
import ResultsGrid from '@/components/ResultsGrid.vue'
import { useSearchStore } from '@/stores/search'

const search = useSearchStore()
const indexStatus = ref<{ state: string; total: number; indexed: number } | null>(null)

onMounted(async () => {
  await search.loadRecent()
  try {
    const res = await api.get('/admin/index-status')
    indexStatus.value = res.data
  } catch {
    // non-critical
  }
})

function handleSearch(query: string) {
  search.search(query)
}
</script>

<template>
  <div class="home">
    <div class="search-section">
      <SearchBar :loading="search.loading" @search="handleSearch" />
      <div v-if="indexStatus" class="index-status">
        <template v-if="indexStatus.state === 'running'">
          Indexing library… {{ indexStatus.indexed }}/{{ indexStatus.total }}
        </template>
        <template v-else-if="indexStatus.state === 'done'">
          {{ indexStatus.total }} items indexed
        </template>
      </div>
    </div>

    <div class="results-section">
      <h2 v-if="!search.query" class="section-title">Recently Added</h2>
      <ResultsGrid
        :results="search.results"
        :query="search.query"
        :filters-used="search.filtersUsed"
        :loading="search.loading"
        :error="search.error"
      />
    </div>
  </div>
</template>

<style scoped>
.home {
  max-width: 1400px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.search-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.index-status {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.section-title {
  color: var(--text-muted);
  font-size: 1rem;
  font-weight: 500;
  margin-bottom: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.results-section { width: 100%; }
</style>
