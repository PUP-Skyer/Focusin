<script setup>
import { onMounted, computed, ref } from 'vue'
import Mascot from './Mascot.vue'
import ChannelIcon from './ChannelIcon.vue'
import { get, groupConversations, conversationGroupKey } from '../api.js'

const props = defineProps({ tab: String })
const emit = defineEmits(['select'])
const convs = ref([])
const emailAccounts = ref([])
const collapsed = ref(new Set())

const channelGroups = computed(() => groupConversations(convs.value, emailAccounts.value))

function toggleChannel(key) {
  collapsed.value = new Set(collapsed.value.has(key)
    ? [...collapsed.value].filter(k => k !== key)
    : [...collapsed.value, key])
}

async function load() {
  const [items, accounts] = await Promise.all([get('/conversations'), get('/email-accounts')])
  convs.value = items
  emailAccounts.value = accounts
}

onMounted(() => {
  load()
  window.addEventListener('fi-conversations-changed', load)
})

function jumpTo(c) {
  collapsed.value.delete(conversationGroupKey(c))
  emit('select', 'messages')
  window.dispatchEvent(new CustomEvent('fi-jump', {
    detail: { channel: c.channel_key, conv: c.conv_key, account: c.account_key || '', stamp: Date.now() }
  }))
}
</script>

<template>
  <aside class="side">
    <div class="brand">
      <span class="mark">◉</span>
      <b>聚光</b><i>FocusIn</i>
    </div>

    <nav class="nav">
      <button :class="{ on: tab === 'overview' }" @click="emit('select', 'overview')">纵览</button>
      <button :class="{ on: tab === 'messages' }" @click="emit('select', 'messages')">消息流</button>

      <div class="sub">
        <section v-for="g in channelGroups" :key="g.key" class="ch-group">
          <button class="ch-hd" :aria-expanded="!collapsed.has(g.key)" :title="g.title || g.label" @click="toggleChannel(g.key)">
            <ChannelIcon :channel="g.channel" />
            <span class="ch-name">{{ g.label }}</span>
            <em v-if="g.important" class="ch-important">{{ g.important }}</em>
            <span class="chevron" :class="{ shut: collapsed.has(g.key) }">⌄</span>
          </button>
          <div v-if="!collapsed.has(g.key)" class="conv-list">
            <button v-for="c in g.items" :key="`${c.channel_key}:${c.account_key || ''}:${c.conv_key}`" class="conv"
              @click="jumpTo(c)" :title="c.account_label ? `${c.conv_title} · ${c.account_label}` : c.conv_title">
              <span class="t">{{ c.conv_title.split('｜')[0].split('·').pop().trim() }}</span>
              <em v-if="c.important">{{ c.important }}</em>
            </button>
          </div>
        </section>
      </div>

      <button :class="{ on: tab === 'calendar' }" @click="emit('select', 'calendar')">日历</button>
      <button :class="{ on: tab === 'chat' }" @click="emit('select', 'chat')">对话</button>
      <button :class="{ on: tab === 'connectors' }" @click="emit('select', 'connectors')">渠道接入</button>
      <button :class="{ on: tab === 'settings' }" @click="emit('select', 'settings')">设置</button>
    </nav>

    <div class="foot">
      <div class="me">
        <Mascot mood="idle" :size="34" />
        <div class="me-txt"><b>小聚</b><span>在线 · 聚光中</span></div>
      </div>
      <p class="slogan">聚合消息，聚焦要事。<br>不是让你看更多消息，而是让你少看消息。</p>
    </div>
  </aside>
</template>

<style scoped>
.side {
  width: 224px; flex-shrink: 0; display: flex; flex-direction: column;
  background: var(--surface); border-right: 1px solid var(--line);
  padding: 18px 12px;
}
.brand { display: flex; align-items: baseline; gap: 6px; padding: 4px 10px 16px; }
.mark { color: var(--brand); font-size: 18px; }
.brand b { font-family: var(--font-display); font-size: 18px; font-weight: 750; letter-spacing: -.02em; }
.brand i { font-style: normal; font-size: var(--text-2xs); color: var(--text-3); letter-spacing: .01em; }

.nav { display: flex; flex-direction: column; gap: 2px; min-height: 0; overflow-y: auto; }
.nav > button {
  border: none; background: transparent; text-align: left;
  padding: 9px 11px; border-radius: 8px; color: var(--text-2);
  font-size: var(--text-base); line-height: 1.35;
}
.nav > button:hover { background: var(--surface-2); }
.nav > button.on { background: var(--brand-weak); color: var(--brand-strong); font-weight: 600; }

.sub { margin: 2px 0 6px; display: flex; flex-direction: column; gap: 1px; }
.ch-group + .ch-group { margin-top: 4px; }
.ch-hd {
  display: flex; align-items: center; gap: 7px; width: 100%; text-align: left;
  border: none; background: transparent; padding: 6px 8px; border-radius: 7px;
  color: var(--text-2); font-size: var(--text-sm); line-height: 1.35;
  transition: background 150ms ease;
}
.ch-hd:hover { background: var(--surface-2); }
.ch-hd :deep(.chic) { width: 20px; height: 20px; border-radius: 6px; box-shadow: none; }
.ch-hd :deep(.chic svg) { width: 12px; height: 12px; }
.ch-name { font-weight: 600; }
.ch-important {
  margin-left: auto; font-style: normal; background: var(--brand-weak);
  color: var(--brand-strong); border-radius: 999px; font-size: var(--text-2xs); padding: 0 6px;
}
.chevron { color: var(--text-3); font-size: 13px; transition: transform 180ms ease; }
.chevron.shut { transform: rotate(-90deg); }
.conv-list { margin: 1px 0 2px 9px; padding-left: 7px; border-left: 1px solid var(--line); }
.conv {
  display: flex; align-items: center; gap: 6px; border: none; background: transparent;
  width: 100%; padding: 6px 8px; border-radius: 7px; font-size: var(--text-xs);
  line-height: 1.4; color: var(--text-2);
  transition: background 150ms ease, transform 150ms ease;
}
.conv:hover { background: var(--surface-2); }
.conv:active { transform: scale(.985); }
.conv .t { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conv em {
  margin-left: auto; font-style: normal; background: var(--brand-weak);
  color: var(--brand-strong); border-radius: 999px; font-size: var(--text-2xs); padding: 0 6px;
}

.foot { margin-top: auto; }
.me { display: flex; gap: 8px; align-items: center; padding: 8px 6px; }
.me b { font-size: var(--text-sm); line-height: 1.35; display: block; }
.me span { font-size: var(--text-xs); color: var(--ok); }
.slogan { font-size: var(--text-xs); color: var(--text-3); line-height: var(--leading-snug); margin: 8px 6px 0; }
</style>
