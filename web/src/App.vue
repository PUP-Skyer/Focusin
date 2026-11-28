<script setup>
import { computed, onMounted, provide, ref, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import Mascot from './components/Mascot.vue'
import Overview from './pages/Overview.vue'
import Messages from './pages/Messages.vue'
import CalendarPage from './pages/CalendarPage.vue'
import Chat from './pages/Chat.vue'
import Connectors from './pages/Connectors.vue'
import Settings from './pages/Settings.vue'
import { get } from './api.js'

const TABS = [
  { key: 'overview', label: '纵览' },
  { key: 'messages', label: '消息流' },
  { key: 'calendar', label: '日历' },
  { key: 'chat', label: '新对话' },
  { key: 'connectors', label: '渠道接入' },
  { key: 'settings', label: '设置' }
]
function tabFromUrl() {
  const requested = new URLSearchParams(window.location.search).get('tab')
  return TABS.some(t => t.key === requested) ? requested : 'overview'
}
const tab = ref(tabFromUrl())
let restoring = false
const theme = ref(localStorage.getItem('fi-theme') || 'light')
const notif = ref({ n: 0, items: [] })
const mascotMood = ref('idle')
const jumpConv = ref(null) // {channel, conv, account} 跨页跳转

watch(tab, next => {
  if (restoring) return
  const url = new URL(window.location.href)
  url.searchParams.set('tab', next)
  window.history.pushState({ focusinTab: next }, '', url)
})

function setTheme(t) {
  theme.value = t
  localStorage.setItem('fi-theme', t)
  document.documentElement.dataset.theme = t
}
document.documentElement.dataset.theme = theme.value

function go(conv) {
  jumpConv.value = { ...conv, stamp: Date.now() }
  tab.value = 'messages'
}

async function pollNotif() {
  try { notif.value = await get('/notifications') } catch { /* 服务未启动 */ }
}

const page = computed(() => ({
  overview: Overview, messages: Messages, calendar: CalendarPage,
  chat: Chat, connectors: Connectors, settings: Settings
}[tab.value]))

provide('gotoMessages', go)
provide('setMood', (m) => { mascotMood.value = m })
provide('goChat', () => { tab.value = 'chat' })
provide('goTab', (key) => { if (TABS.some(t => t.key === key)) tab.value = key })

onMounted(() => {
  pollNotif(); setInterval(pollNotif, 30000)
  window.addEventListener('popstate', () => {
    restoring = true
    tab.value = tabFromUrl()
    queueMicrotask(() => { restoring = false })
  })
})
</script>

<template>
  <div class="shell">
    <Sidebar :tab="tab" @select="(k) => (tab = k)" />

    <div class="main">
      <header class="topbar">
        <div class="logo-mini">聚光<span>FocusIn</span></div>
        <nav class="capsules">
          <button v-for="t in TABS" :key="t.key" class="cap"
            :class="{ on: tab === t.key }" @click="tab = t.key">
            {{ t.label }}
          </button>
        </nav>
        <div class="top-right">
          <div class="bell" :title="`${notif.n} 个日程待确认`">
            🔔<em v-if="notif.n" class="bell-n badge-pop">{{ notif.n }}</em>
          </div>
          <button class="cap" @click="setTheme(theme === 'light' ? 'dark' : 'light')">
            {{ theme === 'light' ? '暗色' : '亮色' }}
          </button>
          <Mascot :mood="mascotMood" :size="28" />
        </div>
      </header>

      <main class="page">
        <component :is="page" :jump="jumpConv" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell { display: flex; height: 100%; }
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; }

.topbar {
  display: flex; align-items: center; gap: 18px; min-height: 56px;
  padding: 10px clamp(16px, 2vw, 28px); background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.logo-mini { font-family: var(--font-display); font-size: 15px; font-weight: 750; color: var(--brand-strong); white-space: nowrap; }
.logo-mini span { color: var(--text-3); font-weight: 500; font-size: var(--text-2xs); margin-left: 5px; letter-spacing: .01em; }

.capsules { flex: 1; min-width: 0; display: flex; gap: 4px; background: var(--surface-2); border-radius: 999px; padding: 4px; overflow-x: auto; scrollbar-width: none; }
.capsules::-webkit-scrollbar { display: none; }
.cap {
  flex-shrink: 0; border: none; background: transparent; color: var(--text-2);
  border-radius: 999px; padding: 7px 15px; font-size: var(--text-sm); line-height: 1.2;
  white-space: nowrap; transition: background var(--dur-1) var(--ease-out), color var(--dur-1) var(--ease-out);
}
.cap.on { background: #241f1a; color: #fff; box-shadow: 0 1px 3px rgba(29, 28, 26, .16); }
.cap:not(.on):hover { color: var(--brand-strong); background: var(--brand-weak); }

.top-right { margin-left: auto; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.bell { position: relative; cursor: default; }
.bell-n {
  position: absolute; top: -6px; right: -10px; font-style: normal;
  background: var(--warn); color: #fff; border-radius: 999px;
  font-size: var(--text-2xs); padding: 0 5px; line-height: 15px;
}
.page {
  flex: 1; overflow: auto; width: 100%; max-width: 1320px; margin: 0 auto;
  padding: clamp(16px, 2vw, 24px);
}

@media (max-width: 1100px) {
  .logo-mini { display: none; }
  .topbar { gap: 10px; }
}
@media (max-width: 760px) {
  .shell :deep(.side) { display: none; }
  .main { width: 100%; }
  .topbar { padding-inline: 12px; }
  .top-right { gap: 6px; }
  .top-right .cap { padding-inline: 10px; }
  .bell { display: none; }
  .page { padding: 12px; }
}
@media (prefers-reduced-motion: reduce) {
  .cap { transition: none; }
}
</style>
