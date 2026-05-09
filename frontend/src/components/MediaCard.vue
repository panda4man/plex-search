<script setup lang="ts">
import type { MediaResult } from '@/stores/search'

const props = defineProps<{ item: MediaResult }>()

function plexWebUrl(item: MediaResult): string {
  return item.plex_web_url
}

function thumbUrl(item: MediaResult): string {
  return `/api/media/thumb/${item.plex_key}`
}

function formatRating(r: number | null): string {
  if (r == null) return '—'
  return r.toFixed(1)
}
</script>

<template>
  <a class="card" :href="plexWebUrl(item)" target="_blank" rel="noopener">
    <div class="thumb-wrap">
      <img :src="thumbUrl(item)" :alt="item.title" loading="lazy" @error="($event.target as HTMLImageElement).style.display='none'" />
      <span class="type-badge">{{ item.media_type === 'movie' ? 'Movie' : 'TV' }}</span>
    </div>
    <div class="info">
      <h3 class="title">{{ item.title }}</h3>
      <div class="meta">
        <span v-if="item.year">{{ item.year }}</span>
        <span v-if="item.seasons">· {{ item.seasons }}S</span>
        <span v-if="item.rating" class="rating">★ {{ formatRating(item.rating) }}</span>
      </div>
      <div class="genres">
        <span v-for="g in item.genres.slice(0, 3)" :key="g" class="genre-tag">{{ g }}</span>
      </div>
      <p class="summary">{{ item.summary }}</p>
    </div>
  </a>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  text-decoration: none;
  color: inherit;
  transition: transform 0.15s, border-color 0.15s;
}

.card:hover {
  transform: translateY(-3px);
  border-color: var(--plex-yellow);
}

.thumb-wrap {
  position: relative;
  aspect-ratio: 2/3;
  background: #0d1b35;
  overflow: hidden;
}

.thumb-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.type-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(0,0,0,0.75);
  color: var(--plex-yellow);
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.info {
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  flex: 1;
}

.title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #cdd6f4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.meta {
  font-size: 0.8rem;
  color: var(--text-muted);
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.rating { color: var(--plex-yellow); }

.genres {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.genre-tag {
  background: #0f3460;
  color: #8e9bb5;
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
}

.summary {
  font-size: 0.78rem;
  color: #6e7d9a;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  margin-top: auto;
}
</style>
