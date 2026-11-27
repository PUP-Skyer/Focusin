<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  get, post, GROUP_LABEL, GROUP_CLASS, groupConversations,
  conversationGroupKey, notifyConversationsChanged, messageSource, openMessageSource,
  senderDisplayName, senderInitial
} from '../api.js'
import ChannelIcon from '../components/ChannelIcon.vue'
import MessageArticle from '../components/MessageArticle.vue'

const props = defineProps({ jump: Object })

const convs = ref([])
const emailAccounts = ref([])
const collapsed = ref(new Set())
const sel = ref(null)
const pane = ref({ messages: [], n: 0 })
const injectInfo = ref(null)
const showChatter = ref(false)
const newIds = ref(new Set())
const reading = ref(null)
const aliasTarget = ref(null)
const sourceNotice = ref('')
let sourceNoticeTimer

function sourceTitle(m) {
  const source = messageSource(m)
  return source.supported ? `点击打开${source.label}` : '点击复制定位信息'
}

async function openSource(m) {
  sourceNotice.value = await openMessageSource(m)
  clearTimeout(sourceNoticeTimer)
  sourceNoticeTimer = setTimeout(() => { sourceNotice.value = '' }, 5000)
}

const channelGroups = computed(() => groupConversations(convs.value, emailAccounts.value))
const selectedConv = computed(() => convs.value.find(c =>
  c.channel_key === sel.value?.channel && c.conv_key === sel.value?.conv
  && (c.account_key || '') === (sel.value?.account || '')))
const selectedGroup = computed(() => channelGroups.value.find(g =>
  g.channel === sel.value?.channel && (!sel.value?.conv || g.items.some(c =>
    c.conv_key === sel.value.conv && (c.account_key || '') === (sel.value?.account || '')))))

async function loadConvs() {
  const [items, accounts] = await Promise.all([get('/conversations'), get('/email-accounts')])
  convs.value = items
  emailAccounts.value = accounts
}

async function loadPane() {
  if (!sel.value) return
  const params = new URLSearchParams({ channel: sel.value.channel })
  if (sel.value.conv) params.set('conv', sel.value.conv)
  if (sel.value.account) params.set('account', sel.value.account)
  pane.value = await get(`/messages?${params}`)
}

async function select(c) {
  const match = convs.value.find(x => x.channel_key === c.channel && x.conv_key === c.conv
    && (x.account_key || '') === (c.account || ''))
  collapsed.value.delete(conversationGroupKey(match || {
    channel_key: c.channel, account_key: c.account, provider_key: c.provider_key
  }))
  sel.value = c
  showChatter.value = false
  reading.value = null
  await loadPane()
}

function toggleChannel(key) {
  collapsed.value = new Set(collapsed.value.has(key)
    ? [...collapsed.value].filter(k => k !== key)
    : [...collapsed.value, key])
}

async function injectDemo() {
  const r = await post('/demo/inject', {})
  injectInfo.value = r
  if (r.ok) {
    newIds.value.add(r.message.id)
    await Promise.all([loadConvs(), loadPane()])
    notifyConversationsChanged()
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
const visible = computed(() => {
  const rows = showChatter.value
    ? pane.value.messages
    : pane.value.messages.filter(m => m.grp !== 'chatter')
  return [...rows].reverse()
})

function dateLabel(ts) {
  const date = new Date(String(ts || '').replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return '其他日期'
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(date)
  target.setHours(0, 0, 0, 0)
  const diff = Math.round((today - target) / 86400000)
  if (diff === 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff > 1 && diff < 7) return `周${'日一二三四五六'[date.getDay()]}`
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const groupedMessages = computed(() => {
  const groups = []
  for (const message of visible.value) {
    const label = dateLabel(message.ts)
    let group = groups.find(item => item.label === label)
    if (!group) {
      group = { label, items: [] }
      groups.push(group)
    }
    group.items.push(message)
  }
  return groups
})

function cleanEmailBody(text) {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const kept = []
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (/^-{3,}\s*(回复|转发|原始|forwarded|original)/i.test(line)) break
    if (/^forwarded message\s*[:：]/i.test(line)) break
    if (/^>/.test(line)) continue
    if (kept.length >= 3 && /^(from|sent|date|to|cc|bcc|subject|发件人|发送时间|日期|收件人|抄送|主题)\s*[:：]/i.test(line)) break
    kept.push(lines[i].replace(/[ \t]+$/, ''))
  }
  return kept.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

function messageView(m) {
  if (sel.value?.channel !== 'email') return { subject: '', body: m.text || '' }
  const normalized = String(m.text || '').replace(/\r\n?/g, '\n').trim()
  const splitAt = normalized.indexOf('\n')
  const subject = (splitAt >= 0 ? normalized.slice(0, splitAt) : normalized).trim() || '(无主题)'
  const body = cleanEmailBody(splitAt >= 0 ? normalized.slice(splitAt + 1) : '').replace(/\*/g, '')
  return { subject, body }
}

function messageSummary(m) {
  const view = messageView(m)
  if (view.subject) {
    return { subject: view.subject, preview: view.body.replace(/\s+/g, ' ').trim() }
  }
  const text = String(m.text || '').replace(/\s+/g, ' ').trim()
  if (text.length <= 76) return { subject: text || '无标题消息', preview: '' }
  return { subject: text.slice(0, 76), preview: text.slice(76) }
}

function formatTime(ts) {
  return String(ts || '').slice(11, 16)
}

function openReader(m) {
  reading.value = m
}

function needsAlias(m) {
  return m.channel_key === 'feishu' && senderDisplayName(m) === '昵称未同步'
}

function openAlias(m) {
  aliasTarget.value = m.id
  reading.value = m
}

function closeReader() {
  reading.value = null
  aliasTarget.value = null
}

function onKeydown(e) {
  if (e.key === 'Escape') closeReader()
}

watch(reading, value => {
  document.body.style.overflow = value ? 'hidden' : ''
})

async function refresh() {
  await loadConvs()
  if (sel.value) await loadPane()
}

function onVisibility() {
  if (!document.hidden) refresh()
}

onMounted(async () => {
  await loadConvs()
  if (!sel.value && convs.value.length) {
    const c = convs.value[0]
    await select({ channel: c.channel_key, conv: c.conv_key, account: c.account_key || '' })
  }
  window.addEventListener('fi-conversations-changed', refresh)
  window.addEventListener('focus', refresh)
  document.addEventListener('visibilitychange', onVisibility)
  window.addEventListener('keydown', onKeydown)
})

watch(() => props.jump?.stamp, (stamp) => {
  if (stamp && props.jump.channel) {
    select({
      channel: props.jump.channel, conv: props.jump.conv,
      account: props.jump.account || ''
    })
  }
}, { immediate: true })

function onJump(e) {
  select({ channel: e.detail.channel, conv: e.detail.conv, account: e.detail.account || '' })
}

window.addEventListener('fi-jump', onJump)

onUnmounted(() => {
  window.removeEventListener('fi-jump', onJump)
  window.removeEventListener('fi-conversations-changed', refresh)
  window.removeEventListener('focus', refresh)
  document.removeEventListener('visibilitychange', onVisibility)
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="ms">
    <aside class="ms-list card">
      <header class="blk-hd">
        <h3>会话</h3>
        <button class="btn btn-brand mini-btn" @click="injectDemo">模拟新消息入站</button>
      </header>
      <section v-for="g in channelGroups" :key="g.key" class="ch-group">
        <button class="ch-hd" :aria-expanded="!collapsed.has(g.key)" :title="g.title || g.label" @click="toggleChannel(g.key)">
          <ChannelIcon :channel="g.channel" />
          <span class="ch-meta"><b>{{ g.label }}</b><i>{{ g.items.length }} 个会话</i></span>
          <em v-if="g.important" class="ch-important">{{ g.important }}</em>
          <span class="chevron" :class="{ shut: collapsed.has(g.key) }">⌄</span>
        </button>
        <div v-if="!collapsed.has(g.key)" class="conv-list">
          <button v-for="c in g.items" :key="`${c.channel_key}:${c.account_key || ''}:${c.conv_key}`" class="conv"
            :class="{ on: sel && sel.channel === c.channel_key && sel.conv === c.conv_key && (sel.account || '') === (c.account_key || '') }"
            @click="select({ channel: c.channel_key, conv: c.conv_key, account: c.account_key || '' })">
            <span class="t">
              <b>{{ c.conv_title.split('｜')[0] }}</b>
              <i>{{ c.conv_title.split('｜')[1] || (c.channel_key === 'email' ? c.account_label : '') || '' }}</i>
            </span>
            <em v-if="c.important">{{ c.important }}</em>
          </button>
        </div>
      </section>
      <p v-if="injectInfo?.ok" class="inj">
        新消息分诊 → <span :class="['grp', GROUP_CLASS[injectInfo.grp]]">{{ injectInfo.grp_label }}</span>
        <template v-if="injectInfo.event"> · 已生成日程待确认（日历页）</template>
      </p>
    </aside>

    <section class="ms-pane card">
      <template v-if="sel">
        <div class="pane-hd">
          <ChannelIcon :channel="sel.channel" />
          <div class="pane-title">
            <b>{{ selectedConv?.conv_title || sel.conv || selectedGroup?.label || sel.channel }}</b>
            <i>{{ selectedGroup?.label || sel.channel }}</i>
          </div>
          <span class="pane-sub">{{ pane.n }} 条消息 · 闲聊 {{ chatterCount }} 条已折叠</span>
        </div>

        <div class="list-toolbar">
          <button v-if="chatterCount" class="btn mini-btn" type="button" @click="showChatter = !showChatter">
            {{ showChatter ? '折叠闲聊' : `展开闲聊（${chatterCount} 条）` }}
          </button>
          <span v-else class="toolbar-note">按时间倒序排列</span>
          <span class="toolbar-count">{{ groupedMessages.length }} 天</span>
        </div>

        <p v-if="sourceNotice" class="source-notice" role="status">{{ sourceNotice }}</p>

        <div class="message-list">
          <section v-for="group in groupedMessages" :key="group.label" class="date-group">
            <header class="date-heading">
              <b>{{ group.label }}</b>
              <span>{{ group.items.length }} 条</span>
            </header>
            <div v-for="m in group.items" :key="m.id"
              class="message-row" :class="{ newmsg: newIds.has(m.id) }"
              :title="`阅读全文 · ${sourceTitle(m)}`" role="link" tabindex="0"
              @click="openReader(m)" @keydown.enter.self.prevent="openReader(m)">
              <span class="row-sender">
                <span class="avatar">
                  <img v-if="m.sender_avatar" :src="m.sender_avatar" :alt="senderDisplayName(m)"
                    referrerpolicy="no-referrer" @error="m.sender_avatar = ''">
                  <span v-else class="avatar-id">{{ senderInitial(m) }}</span>
                </span>
                <span class="sender-copy">
                  <b :class="{ unresolved: needsAlias(m) }" :title="senderDisplayName(m)">{{ senderDisplayName(m) }}</b>
                  <button v-if="needsAlias(m)" class="alias-shortcut" type="button" @click.stop="openAlias(m)">补昵称</button>
                </span>
              </span>

              <span class="row-content">
                <span class="row-subject" :title="messageSummary(m).subject">{{ messageSummary(m).subject }}</span>
                <span v-if="messageSummary(m).preview" class="row-preview" :title="messageSummary(m).preview">
                  {{ messageSummary(m).preview }}
                </span>
              </span>

              <span class="row-meta">
                <time :datetime="m.ts">{{ formatTime(m.ts) }}</time>
                <span v-if="m.attachments?.length" class="row-attachment" title="包含附件">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21.4 11.6-8.9 8.9a6 6 0 0 1-8.5-8.5l9.6-9.6a4 4 0 0 1 5.7 5.7l-9.6 9.6a2 2 0 0 1-2.8-2.8l8.9-8.9" /></svg>
                </span>
                <span v-if="m.grp !== 'chatter'" :class="['grp-dot', GROUP_CLASS[m.grp]]" :title="GROUP_LABEL[m.grp]"></span>
              </span>

              <button class="row-source" type="button" @click.stop="openSource(m)">原平台 ↗</button>
            </div>
          </section>
          <p v-if="!visible.length" class="empty">这个会话还没有可显示的消息。</p>
        </div>
      </template>
      <p v-else class="empty">选择左侧会话查看消息流</p>
    </section>

    <Teleport to="body">
      <div v-if="reading" class="reader-mask" @click.self="closeReader">
        <div class="reader-dialog" role="dialog" aria-modal="true" aria-label="消息原文">
          <button class="reader-close" type="button" aria-label="关闭" @click="closeReader">×</button>
          <MessageArticle :message="reading" :subject="messageView(reading).subject"
            :body="messageView(reading).body" :edit-alias="aliasTarget === reading.id"
            @source="openSource(reading)" @collapse="closeReader" />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.ms { display: grid; grid-template-columns: minmax(230px, 300px) minmax(0, 1fr); gap: 16px; height: 100%; min-height: 480px; }
.blk-hd { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.blk-hd h3 { margin: 0; font-size: var(--text-lg); }
.mini-btn { padding: 4px 10px; font-size: var(--text-xs); line-height: 1.3; }

.ms-list { padding: 14px 10px; overflow: auto; }
.ch-group + .ch-group { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); }
.ch-hd {
  display: flex; align-items: center; gap: 9px; width: 100%; padding: 7px 8px;
  border: none; border-radius: 10px; background: transparent; color: var(--text); text-align: left;
  transition: background 160ms ease;
}
.ch-hd:hover { background: var(--surface-2); }
.ch-hd :deep(.chic) { width: 28px; height: 28px; border-radius: 8px; }
.ch-hd :deep(.chic svg) { width: 16px; height: 16px; }
.ch-meta { flex: 1; min-width: 0; display: flex; align-items: baseline; gap: 6px; }
.ch-meta b { font-size: var(--text-sm); line-height: 1.35; font-weight: 650; }
.ch-meta i { font-size: var(--text-2xs); line-height: 1.35; font-style: normal; color: var(--text-3); white-space: nowrap; }
.ch-important {
  font-style: normal; min-width: 19px; text-align: center; background: var(--brand-weak);
  color: var(--brand-strong); border-radius: 999px; font-size: var(--text-2xs); padding: 1px 5px;
}
.chevron { color: var(--text-3); font-size: 15px; transition: transform 180ms ease; }
.chevron.shut { transform: rotate(-90deg); }
.conv-list { margin: 3px 0 0 15px; padding-left: 8px; border-left: 1px solid var(--line); }
.conv { display: flex; align-items: center; gap: 9px; width: 100%; text-align: left;
  border: none; background: transparent; padding: 8px; border-radius: 8px;
  transition: background 150ms ease, transform 150ms ease; }
.conv:hover { background: var(--surface-2); }
.conv:active { transform: scale(.985); }
.conv.on { background: var(--brand-weak); }
.conv .t { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.conv b { font-size: var(--text-xs); line-height: 1.4; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conv i { font-style: normal; font-size: var(--text-2xs); line-height: 1.35; color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conv em { font-style: normal; background: var(--brand-weak); color: var(--brand-strong);
  border-radius: 999px; font-size: var(--text-2xs); padding: 0 6px; }
.inj { font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-2); background: var(--brand-weak);
  border-radius: 8px; padding: 9px; margin: 12px 0 0; }

.ms-pane { display: flex; flex-direction: column; overflow: hidden; min-width: 0; padding: 0; }
.pane-hd { display: flex; align-items: center; gap: 10px; padding: 15px 20px; border-bottom: 1px solid var(--line); }
.pane-hd :deep(.chic) { width: 28px; height: 28px; border-radius: 8px; }
.pane-hd :deep(.chic svg) { width: 16px; height: 16px; }
.pane-title { min-width: 0; display: flex; align-items: baseline; gap: 8px; }
.pane-title b { font-family: var(--font-display); font-size: var(--text-md); line-height: 1.35; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pane-title i { font-size: var(--text-2xs); line-height: 1.35; font-style: normal; color: var(--text-3); white-space: nowrap; }
.pane-sub { margin-left: auto; font-size: var(--text-xs); line-height: var(--leading-snug); color: var(--text-3); white-space: nowrap; }
.list-toolbar { display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 6px 20px; border-bottom: 1px solid var(--line); background: var(--surface); }
.toolbar-note { color: var(--text-3); font-size: var(--text-xs); }
.toolbar-count { margin-left: auto; color: var(--text-3); font-size: var(--text-xs); }
.source-notice {
  margin: 10px 20px 0; padding: 8px 11px; border: 1px solid var(--line);
  border-left: 3px solid var(--brand); border-radius: 8px;
  background: var(--surface-2); color: var(--text-2); font-size: var(--text-xs); line-height: var(--leading-snug);
}

.message-list { flex: 1; overflow: auto; padding: 0 20px 24px; }
.date-group + .date-group { margin-top: 10px; }
.date-heading { display: flex; align-items: baseline; gap: 8px; padding: 18px 8px 8px; color: var(--text-3); }
.date-heading b { font-size: var(--text-sm); line-height: 1.35; font-weight: 650; }
.date-heading span { font-size: var(--text-2xs); line-height: 1.35; }
.message-row {
  display: grid; grid-template-columns: 190px minmax(0, 1fr) 78px 80px;
  grid-template-areas: "sender content meta source"; align-items: center; gap: 14px;
  min-height: 72px; padding: 14px 8px; border-bottom: 1px solid var(--line);
  cursor: pointer; transition: background 150ms ease;
}
.message-row:hover { background: var(--surface-2); }
.message-row:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
.message-row.newmsg { animation: ripple 1s ease-out 2; background: var(--brand-weak); }
.row-sender { grid-area: sender; display: flex; align-items: center; gap: 10px; min-width: 0; }
.avatar {
  width: 36px; height: 36px; border-radius: 10px; flex: none; overflow: hidden;
  display: flex; align-items: center; justify-content: center; background: var(--surface-2);
  color: var(--text-3); font-size: var(--text-2xs); font-weight: 700;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.sender-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.sender-copy b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--text-sm); line-height: 1.35; font-weight: 650; }
.sender-copy b.unresolved { color: var(--text-3); font-weight: 550; }
.alias-shortcut {
  align-self: flex-start; border: 1px solid var(--line); border-radius: 999px;
  padding: 1px 7px; background: var(--brand-weak); color: var(--brand-strong);
  font-size: var(--text-2xs); line-height: 1.5; font-weight: 650; cursor: pointer;
}
.alias-shortcut:hover { border-color: var(--brand); }
.row-content { grid-area: content; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.row-subject { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); font-size: var(--text-md); line-height: 1.4; font-weight: 700; letter-spacing: -.01em; }
.row-preview { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-3); font-size: var(--text-xs); line-height: 1.5; }
.row-meta { grid-area: meta; display: flex; align-items: center; justify-content: flex-end; gap: 8px; color: var(--text-3); font-size: var(--text-xs); line-height: 1.3; font-variant-numeric: tabular-nums; }
.row-attachment { display: inline-flex; }
.row-attachment svg { width: 14px; height: 14px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.grp-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex: none; }
.row-source { grid-area: source; justify-self: end; border: none; background: transparent; color: var(--brand-strong); font-size: var(--text-xs); line-height: 1.3; font-weight: 600; padding: 5px 0 5px 8px; white-space: nowrap; }
.row-source:hover { text-decoration: underline; text-underline-offset: 3px; }
.empty { margin: 40px auto; color: var(--text-3); font-size: var(--text-sm); line-height: var(--leading-normal); text-align: center; }

.reader-mask {
  position: fixed; inset: 0; z-index: 1000; display: flex; justify-content: center;
  padding: 32px 20px; overflow: auto; background: rgba(20, 19, 18, .42);
  backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px);
}
.reader-dialog { position: relative; width: min(960px, 100%); min-width: 0; margin: auto; }
.reader-close {
  position: absolute; top: 12px; right: 12px; z-index: 2; width: 34px; height: 34px;
  display: grid; place-items: center; border: 1px solid var(--line); border-radius: 50%;
  background: var(--surface); color: var(--text-2); font-size: 22px; line-height: 1;
  box-shadow: var(--shadow-1);
}
.reader-close:hover { border-color: var(--brand); color: var(--brand-strong); }

@media (max-width: 1024px) {
  .message-row { grid-template-columns: 160px minmax(0, 1fr) 68px; grid-template-areas: "sender content meta" "sender source source"; gap: 4px 12px; }
  .row-source { justify-self: end; padding-top: 0; }
}

@media (max-width: 780px) {
  .ms { display: flex; flex-direction: column; height: auto; min-height: 0; }
  .ms-list { max-height: 260px; flex: none; }
  .ms-pane { min-height: 520px; }
  .pane-hd { flex-wrap: wrap; padding-inline: 14px; }
  .pane-sub { width: 100%; margin-left: 38px; white-space: normal; }
  .list-toolbar { padding-inline: 14px; }
  .message-list { padding-inline: 10px; }
  .message-row { grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: "sender meta" "content content" "source source"; gap: 7px 10px; padding: 13px 6px; }
  .row-content { gap: 3px; }
  .row-subject { font-size: var(--text-base); }
  .row-source { justify-self: end; }
  .reader-mask { padding: 12px; }
}

@media (max-width: 480px) {
  .row-preview { font-size: var(--text-xs); }
}
</style>
