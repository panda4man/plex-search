<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="app">
    <nav v-if="auth.isAuthenticated" class="top-nav">
      <span class="brand">PlexSearch</span>
      <span class="user">{{ auth.user?.username }}</span>
      <button class="logout-btn" @click="auth.logout()">Sign out</button>
    </nav>
    <RouterView />
  </div>
</template>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: #1a1a2e;
  color: #cdd6f4;
  font-family: system-ui, -apple-system, sans-serif;
  line-height: 1.5;
}

:root {
  --plex-yellow: #e5a00d;
  --bg-deep: #1a1a2e;
  --bg-card: #16213e;
  --bg-surface: #0f3460;
  --text-muted: #8e9bb5;
  --border: #2a3a5e;
}
</style>

<style scoped>
.app { min-height: 100vh; }

.top-nav {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.5rem;
  background: #0f3460;
  border-bottom: 1px solid var(--border);
}

.brand { font-weight: 700; color: var(--plex-yellow); font-size: 1.1rem; flex: 1; }
.user { color: var(--text-muted); font-size: 0.9rem; }

.logout-btn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-muted);
  border-radius: 6px;
  padding: 0.3rem 0.8rem;
  cursor: pointer;
  font-size: 0.85rem;
  transition: color 0.2s;
  white-space: nowrap;
  flex-shrink: 0;
}
.logout-btn:hover { color: #cdd6f4; }

@media (max-width: 480px) {
  .top-nav { padding: 0.6rem 1rem; gap: 0.5rem; }
  .user { display: none; }
}
</style>
