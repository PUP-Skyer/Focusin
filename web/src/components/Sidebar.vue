<script setup>
import { onMounted, ref } from 'vue'
import Mascot from './Mascot.vue'
import { get } from '../api.js'

const props = defineProps({ tab: String })
const emit = defineEmits(['select'])
const convs = ref([])

onMounted(async () => { convs.value = await get('/conversations') })

function jumpTo(c) {
  emit('select', 'messages')
  window.dispatchEvent(new CustomEvent('fi-jump', {
    detail: { channel: c.channel_key, conv: c.conv_key, stamp: Date.now() }
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
          <button v-for="c in convs" :key="c.conv_key" class="conv"
            @click="jumpTo(c)" :title="c.conv_title">
            <i :class="['ch-dot', 'ch-' + c.channel_key]" />
            <span class="t">{{ c.conv_title.split('｜')[0].split('·').pop().trim() }}</span>
            <em v-if="c.important">{{ c.important }}</em>
          </button>
        </div>

      <button :class="{ on: tab === 'calendar' }" @click="emit('select', 'calendar')">日历</button>
      <button :class="{ on: tab === 'chat' }" @click="emit('select', 'chat')">对话</button>
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
  width: 210px; flex-shrink: 0; display: flex; flex-direction: column;
  background: var(--surface); border-right: 1px solid var(--line);
  padding: 16px 12px;
}
.brand { display: flex; align-items: baseline; gap: 6px; padding: 4px 10px 14px; }
.mark { color: var(--brand); font-size: 18px; }
.brand b { font-size: 17px; }
.brand i { font-style: normal; font-size: 11px; color: var(--text-3); }

.nav { display: flex; flex-direction: column; gap: 2px; }
.nav > button {
  border: none; background: transparent; text-align: left;
  padding: 8px 10px; border-radius: 8px; color: var(--text-2); font-size: 13px;
}
.nav > button:hover { background: var(--surface-2); }
.nav > button.on { background: var(--brand-weak); color: var(--brand-strong); font-weight: 600; }

.sub { margin: 2px 0 6px; padding-left: 14px; display: flex; flex-direction: column; gap: 1px; }
.conv {
  display: flex; align-items: center; gap: 7px; border: none; background: transparent;
  padding: 5px 8px; border-radius: 7px; font-size: 12px; color: var(--text-2);
}
.conv:hover { background: var(--surface-2); }
.conv .t { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conv em {
  font-style: normal; margin-left: auto; background: var(--brand-weak);
  color: var(--brand-strong); border-radius: 999px; font-size: 10px; padding: 0 6px;
}

.foot { margin-top: auto; }
.me { display: flex; gap: 8px; align-items: center; padding: 8px 6px; }
.me b { font-size: 13px; display: block; }
.me span { font-size: 11px; color: var(--ok); }
.slogan { font-size: 11px; color: var(--text-3); line-height: 1.6; margin: 6px 6px 0; }
</style>
