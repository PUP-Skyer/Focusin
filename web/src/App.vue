<script setup>
import { computed, onMounted, provide, ref } from 'vue'
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
  { key: 'chat', label: '对话' },
  { key: 'connectors', label: '渠道接入' },
  { key: 'settings', label: '设置' }
]
const tab = ref('overview')
const theme = ref(localStorage.getItem('fi-theme') || 'light')
const notif = ref({ n: 0, items: [] })
const mascotMood = ref('idle')
const jumpConv = ref(null) // {channel, conv} 跨页跳转

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

onMounted(() => { pollNotif(); setInterval(pollNotif, 30000) })
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
  display: flex; align-items: center; gap: 18px;
  padding: 10px 20px; background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.logo-mini { font-weight: 700; color: var(--brand-strong); white-space: nowrap; }
.logo-mini span { color: var(--text-3); font-weight: 500; font-size: 11px; margin-left: 4px; }

.capsules { display: flex; gap: 6px; background: var(--surface-2); border-radius: 999px; padding: 4px; }
.cap {
  border: none; background: transparent; color: var(--text-2);
  border-radius: 999px; padding: 6px 16px; font-size: 13px;
}
.cap.on { background: #241f1a; color: #fff; }
.cap:not(.on):hover { color: var(--brand-strong); }

.top-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.bell { position: relative; cursor: default; }
.bell-n {
  position: absolute; top: -6px; right: -10px; font-style: normal;
  background: var(--warn); color: #fff; border-radius: 999px;
  font-size: 10px; padding: 0 5px; line-height: 15px;
}
.page { flex: 1; overflow: auto; padding: 20px; }

@media (max-width: 900px) {
  .capsules { display: none; }
}
</style>
