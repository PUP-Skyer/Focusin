<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { get, post, GROUP_LABEL, GROUP_CLASS, CH_CLASS } from '../api.js'

const props = defineProps({ jump: Object })

const convs = ref([])
const sel = ref(null) // {channel, conv}
const pane = ref({ messages: [], n: 0 })
const injectInfo = ref(null)
const showChatter = ref(false)
const newIds = ref(new Set())

async function loadConvs() {
  convs.value = await get('/conversations')
}
async function loadPane() {
  if (!sel.value) return
  pane.value = await get(`/messages?channel=${sel.value.channel}&conv=${sel.value.conv}`)
}
async function select(c) {
  sel.value = c
  showChatter.value = false
  await loadPane()
}

async function injectDemo() {
  const r = await post('/demo/inject', {})
  injectInfo.value = r
  if (r.ok) {
    newIds.value.add(r.message.id)
    await Promise.all([loadConvs(), loadPane()])
    if (r.grp === 'schedule' && 'Notification' in window) {
      try {
        new Notification('聚光 FocusIn', {
          body: `新消息分诊为日程：${r.message.text.slice(0, 24)}…，请到日历页确认`
        })
      } catch { /* 浏览器未授权则静默 */ }
    }
    setTimeout(() => newIds.value.delete(r.message.id), 4000)
  }
}

const chatterCount = computed(() => pane.value.messages.filter(m => m.grp === 'chatter').length)
const visible = computed(() => showChatter.value
  ? pane.value.messages
  : pane.value.messages.filter(m => m.grp !== 'chatter'))

onMounted(async () => {
  await loadConvs()
  if (convs.value.length) {
    select({ channel: convs.value[0].channel_key, conv: convs.value[0].conv_key })
  }
})

watch(() => props.jump?.stamp, (s) => {
  if (s && props.jump.channel) {
    select({ channel: props.jump.channel, conv: props.jump.conv })
  }
})

window.addEventListener('fi-jump', (e) => {
  select({ channel: e.detail.channel, conv: e.detail.conv })
})
</script>

<template>
  <div class="ms">
    <aside class="ms-list card">
      <header class="blk-hd"><h3>会话</h3>
        <button class="btn btn-brand mini-btn" @click="injectDemo">模拟新消息入站</button>
      </header>
      <button v-for="c in convs" :key="c.conv_key" class="conv"
        :class="{ on: sel && sel.conv === c.conv_key }"
        @click="select({ channel: c.channel_key, conv: c.conv_key })">
        <span :class="['ch-dot', 'ch-' + c.channel_key]" />
        <span class="t">
          <b>{{ c.conv_title.split('｜')[0] }}</b>
          <i>{{ c.conv_title.split('｜')[1] || '' }}</i>
        </span>
        <em v-if="c.important">{{ c.important }}</em>
      </button>
      <p v-if="injectInfo?.ok" class="inj">
        新消息分诊 → <span :class="['grp', GROUP_CLASS[injectInfo.grp]]">
          {{ injectInfo.grp_label }}</span>
        <template v-if="injectInfo.event"> · 已生成日程待确认（日历页）</template>
      </p>
    </aside>

    <section class="ms-pane card">
      <template v-if="sel">
        <div class="pane-hd">
          <b>{{ convs.find(c => c.conv_key === sel.conv)?.conv_title || sel.conv }}</b>
          <span class="pane-sub">{{ pane.n }} 条消息 · 闲聊 {{ chatterCount }} 条已折叠</span>
        </div>

        <button v-if="chatterCount" class="btn mini-btn ch-toggle" @click="showChatter = !showChatter">
          {{ showChatter ? '折叠闲聊' : `展开闲聊（${chatterCount} 条）` }}
        </button>

        <div class="msgs">
          <div v-for="m in visible" :key="m.id"
            class="msg" :class="{ newmsg: newIds.has(m.id) }">
            <span class="avatar">{{ m.sender.slice(0, 1) }}</span>
            <div class="body">
              <header>
                <b>{{ m.sender }}</b>
                <span class="ts">{{ m.ts }}</span>
                <span v-if="m.grp !== 'chatter'"
                  :class="['grp', 'badge-pop', GROUP_CLASS[m.grp]]">
                  {{ GROUP_LABEL[m.grp] }}</span>
              </header>
              <p class="txt">{{ m.text }}</p>
            </div>
          </div>
        </div>
      </template>
      <p v-else class="empty">选择左侧会话查看消息流</p>
    </section>
  </div>
</template>

<style scoped>
.ms { display: grid; grid-template-columns: 300px 1fr; gap: 16px; height: 100%; min-height: 480px; }
.blk-hd { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.blk-hd h3 { margin: 0; font-size: 15px; }
.mini-btn { padding: 3px 10px; font-size: 11px; }

.ms-list { padding: 14px; overflow: auto; }
.conv { display: flex; align-items: center; gap: 9px; width: 100%; text-align: left;
  border: none; background: transparent; padding: 9px 8px; border-radius: 8px; }
.conv:hover { background: var(--surface-2); }
.conv.on { background: var(--brand-weak); }
.conv .t { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.conv b { font-size: 13px; font-weight: 600; }
.conv i { font-style: normal; font-size: 10px; color: var(--text-3); }
.conv em { font-style: normal; background: var(--brand-weak); color: var(--brand-strong);
  border-radius: 999px; font-size: 10px; padding: 0 6px; }
.inj { font-size: 11px; color: var(--text-2); background: var(--brand-weak);
  border-radius: 8px; padding: 8px; margin: 12px 0 0; }

.ms-pane { padding: 14px 18px; display: flex; flex-direction: column; overflow: hidden; }
.pane-hd { display: flex; align-items: baseline; gap: 12px; padding-bottom: 10px;
  border-bottom: 1px solid var(--line); }
.pane-hd b { font-size: 14px; }
.pane-sub { font-size: 11px; color: var(--text-3); }
.ch-toggle { margin: 10px 0 0; align-self: flex-start; }

.msgs { overflow: auto; padding: 12px 2px; display: flex; flex-direction: column; gap: 10px; }
.msg { display: flex; gap: 10px; }
.newmsg { animation: ripple 1s ease-out 2; border-radius: 10px; }
.avatar { width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
  background: var(--surface-2); display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600; color: var(--text-2); }
.body { min-width: 0; }
.body header { display: flex; align-items: center; gap: 8px; }
.body b { font-size: 12px; }
.ts { font-size: 10px; color: var(--text-3); }
.txt { margin: 3px 0 0; font-size: 13px; line-height: 1.55; color: var(--text); }
.empty { margin: auto; color: var(--text-3); }
</style>
