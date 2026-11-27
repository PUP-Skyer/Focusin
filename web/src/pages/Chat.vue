<script setup>
import { computed, nextTick, onMounted, onUnmounted, inject, ref } from 'vue'
import Mascot from '../components/Mascot.vue'
import {
  get, post, chatStream, chatSessions, createChatSession, chatSessionMessages,
  runWorkflow, openMessageSource
} from '../api.js'

defineProps({ jump: Object })
const setMood = inject('setMood')
const goTab = inject('goTab')
const sessions = ref([])
const currentSession = ref(null)
const items = ref([])
const input = ref('')
const busy = ref(false)
const workflowRunning = ref(false)
const approval = ref(null)
const deciding = ref(false)
const listEl = ref(null)
const composerEl = ref(null)
const capabilityOpen = ref(false)
const calendarOpen = ref(false)
const calendarItems = ref([])
const calendarLoading = ref(false)
const connectors = ref([])
const notice = ref('')
let abortController = null
let noticeTimer

const QUICK = [
  '帮我看看接下来的日程',
  '最近有哪些重要消息',
  '帮我起草一条回复',
  '汇总今天需要处理的事'
]
const WORKFLOWS = [
  { id: 'daily_brief', title: '今日重点简报', desc: '消息、待办与日程一次看清', glyph: '今' },
  { id: 'important_digest', title: '重要消息摘要', desc: '近期重点，保留原文出处', glyph: '摘' },
  { id: 'schedule_check', title: '日程体检', desc: '检查待确认与近期安排', glyph: '程' }
]
const SKILLS = [
  { id: 'search', title: '消息检索', desc: '跨渠道找到原文', glyph: '搜' },
  { id: 'draft', title: '回复起草', desc: '只起草，不代发', glyph: '写' },
  { id: 'schedule', title: '日程整理', desc: '聚焦最近安排', glyph: '历' }
]
const PLUGINS = [
  { key: 'feishu', title: '飞书', desc: '检索已订阅群聊', glyph: '飞' },
  { key: 'email', title: '邮箱', desc: '汇总已连接邮箱', glyph: '邮' },
  { key: 'connectors', title: '更多插件', desc: '管理渠道与连接器', glyph: '接' }
]
const TOOL_LABELS = {
  search_messages: '检索聚合消息',
  list_schedule: '读取日程',
  create_schedule: '创建日程',
  update_schedule: '修改日程',
  delete_schedule: '忽略日程',
  save_draft: '保存草稿'
}
const RISK_LABELS = { safe: '只读', moderate: '需确认', sensitive: '敏感' }
const CHANNEL_LABELS = { wechat: '微信', qq: 'QQ', feishu: '飞书', email: '邮箱', dingtalk: '钉钉' }

const currentTitle = computed(() => currentSession.value?.title || '新对话')
const connectorByKey = computed(() => new Map(connectors.value.map(c => [c.key, c])))
const running = computed(() => busy.value || workflowRunning.value)

function scrollBottom() {
  nextTick(() => { if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight })
}

function showNotice(text) {
  notice.value = text
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => { notice.value = '' }, 3600)
}

async function loadSessions() {
  sessions.value = await chatSessions()
  if (currentSession.value) {
    const current = sessions.value.find(s => s.id === currentSession.value.id)
    if (current) currentSession.value = current
  }
}

async function loadMessages(sessionId) {
  const rows = await chatSessionMessages(sessionId)
  items.value = rows.map(m => ({ kind: m.role, text: m.content }))
  scrollBottom()
}

async function selectSession(session) {
  if (running.value || session.id === currentSession.value?.id) return
  currentSession.value = session
  localStorage.setItem('fi-chat-session', session.id)
  capabilityOpen.value = false
  try {
    await loadMessages(session.id)
  } catch (e) {
    showNotice(`读取会话失败：${e.message}`)
  }
}

async function newConversation() {
  if (running.value) return
  try {
    const session = await createChatSession()
    sessions.value.unshift(session)
    await selectSession(session)
    input.value = ''
    nextTick(() => composerEl.value?.focus())
  } catch (e) {
    showNotice(`创建会话失败：${e.message}`)
  }
}

async function send(text) {
  const msg = (text ?? input.value).trim()
  if (!msg || running.value || !currentSession.value) return
  input.value = ''
  capabilityOpen.value = false
  busy.value = true
  setMood('working')
  items.value.push({ kind: 'user', text: msg })

  const assistant = { kind: 'assistant', text: '', thinking: [], tools: [] }
  items.value.push(assistant)
  let sawApproval = false
  abortController = new AbortController()
  scrollBottom()

  try {
    for await (const ev of chatStream(msg, {
      sessionId: currentSession.value.id,
      signal: abortController.signal
    })) {
      if (ev.type === 'delta') { assistant.text += ev.text; scrollBottom() }
      else if (ev.type === 'thinking') assistant.thinking.push(ev.text)
      else if (ev.type === 'tool_start') {
        assistant.tools.push({ name: ev.name, args: ev.args, risk: ev.risk, ok: null, result: '' })
        scrollBottom()
      } else if (ev.type === 'tool_end') {
        const tool = assistant.tools.find(x => x.name === ev.name && x.ok === null)
        if (tool) { tool.ok = ev.ok; tool.result = ev.result }
        scrollBottom()
      } else if (ev.type === 'approval') {
        sawApproval = true
        approval.value = ev
        deciding.value = false
        setMood('waiting')
        scrollBottom()
      } else if (ev.type === 'approval_resolved') {
        if (approval.value && approval.value.id === ev.id) approval.value = null
        setMood(ev.decision === 'approve' ? 'working' : 'error')
      } else if (ev.type === 'error') {
        assistant.text += `${assistant.text ? '\n' : ''}${ev.message}`
      } else if (ev.type === 'done' && !assistant.text) {
        assistant.text = ev.content
      }
    }
    if (!assistant.text) assistant.text = '已处理完成。'
  } catch (e) {
    if (e.name !== 'AbortError') assistant.text += `${assistant.text ? '\n' : ''}连接本地服务失败：${e.message}`
    else if (!assistant.text) assistant.text = '已停止，本轮结果未完整生成。'
  } finally {
    busy.value = false
    abortController = null
    setMood(sawApproval ? 'idle' : 'happy')
    setTimeout(() => setMood('idle'), 2200)
    try { await loadSessions() } catch { /* 保留当前会话视图 */ }
    scrollBottom()
  }
}

function stop() {
  abortController?.abort()
}

async function decide(decision) {
  if (!approval.value || deciding.value) return
  deciding.value = true
  try {
    await post(`/approvals/${approval.value.id}/decision`, { decision })
  } catch (e) {
    deciding.value = false
    showNotice(`审批提交失败：${e.message}`)
  }
}

async function executeWorkflow(id) {
  if (running.value || !currentSession.value) return
  capabilityOpen.value = false
  workflowRunning.value = true
  setMood('working')
  try {
    const result = await runWorkflow(id, currentSession.value.id)
    items.value.push({ kind: 'workflow', run: result })
    try { await loadSessions() } catch { /* 保留当前工作流结果 */ }
    scrollBottom()
  } catch (e) {
    showNotice(`工作流执行失败：${e.message}`)
  } finally {
    workflowRunning.value = false
    setMood('happy')
    setTimeout(() => setMood('idle'), 1800)
  }
}

function useSkill(id) {
  capabilityOpen.value = false
  if (id === 'draft') {
    input.value = '帮我检索相关上下文，并起草一条简洁回复；只保存草稿，不要代发。'
    nextTick(() => {
      composerEl.value?.focus()
      composerEl.value?.setSelectionRange(input.value.length, input.value.length)
    })
    return
  }
  if (id === 'schedule') return executeWorkflow('schedule_check')
  send('帮我检索最近的重要消息，按重要程度整理，并给出渠道、会话、时间和发送者。')
}

function usePlugin(plugin) {
  capabilityOpen.value = false
  if (plugin.key === 'connectors') return goTab('connectors')
  if (connectorByKey.value.get(plugin.key)?.configured) {
    return send(`帮我检索${plugin.title}最近的重要消息，并给出原文出处。`)
  }
  goTab('connectors')
  showNotice(`请先连接${plugin.title}，再回来使用这个插件。`)
}

async function openCalendar() {
  capabilityOpen.value = false
  calendarOpen.value = true
  calendarLoading.value = true
  try {
    calendarItems.value = await get('/schedule')
  } catch (e) {
    showNotice(`读取日程失败：${e.message}`)
  } finally {
    calendarLoading.value = false
  }
}

async function openSource(message) {
  const source = message.channel_key ? message : { ...message, channel_key: message.channel }
  showNotice(await openMessageSource(source))
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    showNotice('已复制')
  } catch {
    showNotice('当前浏览器无法访问剪贴板')
  }
}

function toolLabel(name) {
  return TOOL_LABELS[name] || name
}

function formatSessionTime(ts) {
  return String(ts || '').slice(5, 16).replace('-', '/')
}

function autoGrow() {
  const el = composerEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

function onComposerKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}

const sr = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
const rec = ref(null)
function speak() {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!R) return
  if (!rec.value) {
    rec.value = new R()
    rec.value.lang = 'zh-CN'
    rec.value.onresult = (e) => { input.value = e.results[0][0].transcript; autoGrow() }
    rec.value.onend = () => { if (input.value) send() }
  }
  rec.value.start()
}

onMounted(async () => {
  try {
    const [, loadedConnectors] = await Promise.all([loadSessions(), get('/connectors')])
    connectors.value = loadedConnectors
    const loadedSessions = sessions.value
    const savedId = localStorage.getItem('fi-chat-session')
    const saved = loadedSessions.find(s => s.id === savedId)
    if (saved) currentSession.value = saved
    else if (loadedSessions[0]) currentSession.value = loadedSessions[0]
    else currentSession.value = await createChatSession()
    if (currentSession.value) {
      localStorage.setItem('fi-chat-session', currentSession.value.id)
      await loadMessages(currentSession.value.id)
    }
    await loadSessions()
  } catch (e) {
    showNotice(`对话服务暂不可用：${e.message}`)
  }
  scrollBottom()
})

onUnmounted(() => {
  abortController?.abort()
  clearTimeout(noticeTimer)
  rec.value?.abort()
})
</script>

<template>
  <div class="chat-workspace">
    <aside class="session-rail" aria-label="对话会话">
      <div class="rail-head">
        <span class="rail-label">工作对话</span>
        <button class="new-chat" title="新对话" :disabled="running" @click="newConversation">
          <span class="new-plus">+</span><span class="new-label">新对话</span>
        </button>
      </div>
      <div class="session-list">
        <button v-for="session in sessions" :key="session.id"
          class="session-item" :class="{ on: session.id === currentSession?.id }"
          :disabled="running" @click="selectSession(session)">
          <span class="session-dot" />
          <span class="session-copy">
            <b>{{ session.title }}</b>
            <small>{{ formatSessionTime(session.updated_at) }}</small>
          </span>
        </button>
        <p v-if="!sessions.length" class="rail-empty">还没有历史对话</p>
      </div>
      <div class="agent-mini">
        <Mascot mood="idle" :size="30" />
        <div class="session-copy"><b>小聚</b><small>本地消息智能体</small></div>
        <span class="online-dot" />
      </div>
    </aside>

    <section class="conversation">
      <header class="conversation-head">
        <div class="conversation-title">
          <button class="mobile-new" title="新对话" :disabled="running" @click="newConversation">+</button>
          <h2>{{ currentTitle }}</h2>
          <span class="agent-pill"><span />小聚 · 消息智能体</span>
        </div>
        <button class="calendar-link" @click="openCalendar">查看日程</button>
      </header>

      <div ref="listEl" class="messages">
        <div v-if="!items.length" class="welcome">
          <div class="welcome-mark"><Mascot mood="idle" :size="58" /></div>
          <p class="eyebrow">FOCUSIN AGENT</p>
          <h1>把注意力留给真正重要的事。</h1>
          <p class="welcome-desc">我会基于你已订阅的消息与日程工作。先给结论，再给出处；外发内容只起草，不代发。</p>
          <div class="quick">
            <button v-for="q in QUICK" :key="q" class="quick-item" @click="send(q)">
              <span>{{ q }}</span><i>↗</i>
            </button>
          </div>
        </div>

        <template v-for="(m, i) in items" :key="i">
          <div v-if="m.kind === 'user'" class="bub user-bub">{{ m.text }}</div>

          <div v-else-if="m.kind === 'workflow'" class="workflow-card card">
            <div class="workflow-head">
              <span class="workflow-glyph">{{ WORKFLOWS.find(w => w.id === m.run.workflow_id)?.glyph || '自' }}</span>
              <div><p class="eyebrow">自动化工作流</p><h3>{{ m.run.title }}</h3></div>
              <span class="done-pill">已完成</span>
            </div>
            <p class="workflow-summary">{{ m.run.summary }}</p>
            <ol class="run-steps">
              <li v-for="(step, j) in m.run.steps" :key="j">
                <span class="step-check">✓</span><b>{{ step.name }}</b><small>{{ step.detail }}</small>
              </li>
            </ol>
            <div v-if="m.run.data?.messages?.length" class="wf-findings">
              <p class="section-label">优先关注</p>
              <button v-for="message in m.run.data.messages.slice(0, 4)" :key="message.id"
                class="finding" @click="openSource(message)">
                <span class="finding-source">{{ CHANNEL_LABELS[message.channel] || message.channel }} · {{ message.title }}</span>
                <b>{{ message.text.slice(0, 78) }}{{ message.text.length > 78 ? '…' : '' }}</b>
                <small>{{ message.ts }} · {{ message.sender }}</small>
              </button>
            </div>
            <div v-if="m.run.data?.schedule?.length" class="wf-schedule">
              <p class="section-label">最近日程</p>
              <div v-for="event in m.run.data.schedule.slice(0, 3)" :key="event.id">
                <time>{{ event.start_at.slice(5, 16) }}</time><span>{{ event.title }}</span>
              </div>
            </div>
          </div>

          <div v-else class="bub bot">
            <Mascot mood="idle" :size="26" />
            <div class="bot-body">
              <details v-if="m.thinking?.length" class="think">
                <summary>思考过程 <span>{{ m.thinking.length }} 步</span></summary>
                <p v-for="(t, j) in m.thinking" :key="j">{{ t }}</p>
              </details>

              <details v-for="(t, j) in m.tools" :key="'t' + j" class="tool"
                :class="{ bad: t.ok === false }">
                <summary>
                  <span class="dot" :class="{ run: t.ok === null, okk: t.ok === true, bad: t.ok === false }" />
                  <b>{{ toolLabel(t.name) }}</b>
                  <span class="risk" :class="'r-' + t.risk">{{ RISK_LABELS[t.risk] || t.risk }}</span>
                </summary>
                <pre class="t-args">{{ JSON.stringify(t.args, null, 2) }}</pre>
                <pre v-if="t.result" class="t-res">{{ t.result }}</pre>
              </details>

              <div v-if="m.tools?.some(t => t.ok === null && t.risk !== 'safe')" class="wait-approval">
                有操作正在等待你的确认，批准前不会执行。
              </div>
              <p v-if="m.text" class="bot-txt" v-text="m.text" />
              <button v-if="m.text" class="copy-btn" title="复制回复" @click="copyText(m.text)">复制</button>
            </div>
          </div>
        </template>
      </div>

      <div class="composer-wrap">
        <div v-if="capabilityOpen" class="cap-menu card">
          <div class="cap-menu-head">
            <div><p class="eyebrow">CAPABILITIES</p><h3>为这次对话添加能力</h3></div>
            <button class="close-btn" title="关闭" @click="capabilityOpen = false">×</button>
          </div>
          <section class="cap-section">
            <div class="cap-section-title"><b>自动化工作流</b><span>只读运行，不修改原始消息</span></div>
            <div class="cap-grid">
              <button v-for="flow in WORKFLOWS" :key="flow.id" :disabled="running" @click="executeWorkflow(flow.id)">
                <span class="cap-glyph">{{ flow.glyph }}</span>
                <span><b>{{ flow.title }}</b><small>{{ flow.desc }}</small></span>
                <i>→</i>
              </button>
            </div>
          </section>
          <div class="cap-columns">
            <section class="cap-section">
              <div class="cap-section-title"><b>Skills</b><span>可复用的做事方法</span></div>
              <div class="cap-grid compact">
                <button v-for="skill in SKILLS" :key="skill.id" :disabled="running" @click="useSkill(skill.id)">
                  <span class="cap-glyph">{{ skill.glyph }}</span>
                  <span><b>{{ skill.title }}</b><small>{{ skill.desc }}</small></span>
                </button>
              </div>
            </section>
            <section class="cap-section">
              <div class="cap-section-title"><b>插件与渠道</b><span>连接你的工作流</span></div>
              <div class="cap-grid compact">
                <button v-for="plugin in PLUGINS" :key="plugin.key" :disabled="running" @click="usePlugin(plugin)">
                  <span class="cap-glyph">{{ plugin.glyph }}</span>
                  <span><b>{{ plugin.title }}</b><small>{{ plugin.desc }}</small></span>
                  <span class="plugin-state" :class="{ configured: connectorByKey.get(plugin.key)?.configured }">
                    {{ plugin.key === 'connectors' ? '管理' : connectorByKey.get(plugin.key)?.configured ? '已连接' : '未连接' }}
                  </span>
                </button>
              </div>
            </section>
          </div>
          <button class="calendar-cap" @click="openCalendar">
            <span class="cap-glyph">历</span><span><b>查看日程</b><small>在对话中预览近期安排</small></span><i>→</i>
          </button>
        </div>

        <footer class="composer card">
          <button class="attach-btn" title="添加能力" :aria-expanded="capabilityOpen"
            :disabled="running" @click="capabilityOpen = !capabilityOpen">+</button>
          <textarea ref="composerEl" v-model="input" rows="1" placeholder="问消息、查日程、发起工作流……"
            @input="autoGrow" @keydown="onComposerKeydown" />
          <button v-if="sr" class="icon-btn" title="语音输入" :disabled="running" @click="speak">语</button>
          <button v-if="busy" class="stop-btn" @click="stop">停止</button>
          <button v-else class="btn btn-brand send-btn" :disabled="!input.trim() || workflowRunning || !currentSession" @click="send()">发送</button>
        </footer>
        <div class="composer-hint"><span>Enter 发送 · Shift + Enter 换行</span><span>消息与凭据仅保存在本机</span></div>
      </div>
    </section>
  </div>

  <div v-if="calendarOpen" class="drawer-mask" @click.self="calendarOpen = false">
    <aside class="calendar-preview card">
      <div class="drawer-head"><div><p class="eyebrow">CALENDAR</p><h3>近期日程</h3></div><button class="close-btn" @click="calendarOpen = false">×</button></div>
      <p v-if="calendarLoading" class="drawer-empty">正在读取日程…</p>
      <p v-else-if="!calendarItems.length" class="drawer-empty">暂时没有日程。</p>
      <div v-else class="calendar-list">
        <div v-for="event in calendarItems.slice(0, 8)" :key="event.id" class="calendar-item">
          <time>{{ event.start_at.slice(5, 16) }}</time>
          <div><b>{{ event.title }}</b><small>{{ event.status === 'confirmed' ? '已确认' : '待确认' }}</small></div>
          <button v-if="event.source" title="查看原文" @click="openSource(event.source)">↗</button>
        </div>
      </div>
      <button class="btn btn-brand full-calendar" @click="goTab('calendar')">打开完整日历</button>
    </aside>
  </div>

  <div v-if="approval" class="mask" @click.self="decide('deny')">
    <div class="approve card">
      <div class="warn-bar">敏感操作审批 · 点击遮罩默认拒绝</div>
      <h4>{{ toolLabel(approval.tool) }} <span :class="'risk r-' + approval.risk">{{ RISK_LABELS[approval.risk] || approval.risk }}</span></h4>
      <pre class="ap-args">{{ JSON.stringify(approval.args, null, 2) }}</pre>
      <p class="approval-note">仅本次授权。操作执行后会写入本地审计日志。</p>
      <div class="ap-acts">
        <button class="btn" :disabled="deciding" @click="decide('deny')">拒绝</button>
        <button class="btn btn-brand" :disabled="deciding" @click="decide('approve')">批准</button>
      </div>
    </div>
  </div>

  <div v-if="notice" class="toast">{{ notice }}</div>
</template>

<style scoped>
.chat-workspace { display: grid; grid-template-columns: 216px minmax(0, 1fr); height: 100%; min-height: 0; gap: 14px; }
.session-rail { display: flex; flex-direction: column; min-height: 0; padding: 12px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow-1); }
.rail-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px; }
.rail-label { font-size: var(--text-xs); color: var(--text-3); }
.new-chat { height: 32px; display: inline-flex; align-items: center; gap: 5px; padding: 0 10px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface-2); color: var(--text); font-size: var(--text-xs); }
.new-chat:hover { border-color: var(--brand); color: var(--brand-strong); }
.new-plus { font-size: 17px; line-height: 1; }
.session-list { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.session-item { display: flex; align-items: flex-start; gap: 8px; width: 100%; padding: 9px 8px; border: none; border-radius: 8px; background: transparent; color: var(--text-2); text-align: left; }
.session-item:hover { background: var(--surface-2); }
.session-item.on { background: var(--brand-weak); color: var(--brand-strong); }
.session-item:disabled { opacity: .55; }
.session-dot { width: 6px; height: 6px; margin-top: 6px; flex-shrink: 0; border-radius: 50%; background: var(--text-3); }
.session-item.on .session-dot { background: var(--brand); }
.session-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.session-copy b { font-size: var(--text-xs); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-copy small { font-size: var(--text-2xs); color: var(--text-3); }
.rail-empty { padding: 10px 6px; font-size: var(--text-xs); color: var(--text-3); }
.agent-mini { display: flex; align-items: center; gap: 7px; margin-top: 10px; padding: 10px 6px 2px; border-top: 1px solid var(--line); }
.online-dot { width: 7px; height: 7px; margin-left: auto; border-radius: 50%; background: var(--ok); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 14%, transparent); }

.conversation { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.conversation-head { min-height: 42px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 4px 10px; }
.conversation-title { min-width: 0; display: flex; align-items: center; gap: 10px; }
.conversation-title h2 { margin: 0; font-size: var(--text-md); font-weight: 650; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.agent-pill { display: inline-flex; align-items: center; gap: 6px; flex-shrink: 0; padding: 4px 9px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--text-2); font-size: var(--text-2xs); }
.agent-pill span { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); }
.calendar-link, .mobile-new { border: none; background: transparent; color: var(--text-2); font-size: var(--text-xs); }
.calendar-link:hover { color: var(--brand-strong); }
.mobile-new { display: none; width: 28px; height: 28px; border: 1px solid var(--line); border-radius: 50%; font-size: 18px; }
.messages { flex: 1; min-height: 0; overflow-y: auto; padding: 8px 4px 22px; display: flex; flex-direction: column; gap: 18px; scroll-behavior: smooth; }
.welcome { width: min(700px, 100%); margin: auto; padding: 34px; border: 1px solid var(--line); border-radius: 18px; background: linear-gradient(145deg, var(--surface) 40%, var(--brand-weak)); box-shadow: var(--shadow-1); }
.welcome-mark { width: 68px; height: 68px; display: grid; place-items: center; margin-bottom: 20px; border-radius: 20px; background: var(--surface); box-shadow: var(--shadow-1); }
.eyebrow { margin: 0 0 6px; color: var(--brand-strong); font-size: 10px; font-weight: 700; letter-spacing: .14em; }
.welcome h1 { max-width: 520px; margin: 0; font-size: clamp(24px, 3vw, 34px); line-height: 1.18; letter-spacing: -.035em; }
.welcome-desc { max-width: 560px; margin: 14px 0 24px; color: var(--text-2); font-size: var(--text-base); line-height: var(--leading-relaxed); }
.quick { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.quick-item { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 46px; padding: 10px 13px; border: 1px solid var(--line); border-radius: 10px; background: color-mix(in srgb, var(--surface) 86%, transparent); color: var(--text); text-align: left; font-size: var(--text-sm); }
.quick-item:hover { border-color: var(--brand); background: var(--surface); transform: translateY(-1px); }
.quick-item i { color: var(--brand-strong); font-style: normal; }

.bub { max-width: 88%; font-size: var(--text-base); line-height: var(--leading-relaxed); }
.user-bub { align-self: flex-end; padding: 11px 16px; border-radius: 14px 14px 4px 14px; background: #241f1a; color: #fff; white-space: pre-wrap; box-shadow: var(--shadow-1); }
.bot { align-self: flex-start; display: flex; align-items: flex-start; gap: 10px; }
.bot-body { min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 7px; }
.bot-txt { margin: 0; padding: 12px 15px; border: 1px solid var(--line); border-radius: 4px 14px 14px 14px; background: var(--surface); white-space: pre-wrap; box-shadow: var(--shadow-1); }
.copy-btn { align-self: flex-end; border: none; background: transparent; color: var(--text-3); font-size: var(--text-2xs); }
.copy-btn:hover { color: var(--brand-strong); }
.think, .tool { width: 100%; max-width: 620px; padding: 8px 11px; border-radius: 9px; background: var(--surface-2); color: var(--text-2); font-size: var(--text-xs); }
.think summary, .tool summary { cursor: pointer; list-style: none; display: flex; align-items: center; gap: 7px; }
.think summary span { margin-left: auto; color: var(--text-3); }
.think p { margin: 8px 0 0; }
.tool summary b { font-weight: 600; }
.tool .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-3); }
.tool .dot.run { background: var(--brand); animation: breathe 1s infinite; }
.tool .dot.okk { background: var(--ok); }
.tool .dot.bad { background: var(--warn); }
.risk { margin-left: auto; padding: 1px 6px; border-radius: 999px; font-size: 10px; }
.r-safe { background: #e3f7f1; color: #0e8a70; }
.r-moderate { background: #fdeed9; color: #b05e00; }
.r-sensitive { background: #ffe7e7; color: #d0342c; }
.t-args, .t-res { margin: 8px 0 0; font-family: var(--font-mono); font-size: 10px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; color: var(--text-3); max-height: 160px; overflow: auto; }
.wait-approval { padding: 7px 10px; border-radius: 8px; background: var(--brand-weak); color: var(--brand-strong); font-size: var(--text-xs); }

.workflow-card { width: min(720px, 94%); padding: 18px; }
.workflow-head { display: flex; align-items: center; gap: 11px; }
.workflow-glyph { width: 38px; height: 38px; display: grid; place-items: center; flex-shrink: 0; border-radius: 11px; background: var(--brand-weak); color: var(--brand-strong); font-weight: 700; }
.workflow-head h3 { margin: 0; font-size: var(--text-md); }
.done-pill { margin-left: auto; padding: 3px 8px; border-radius: 999px; background: #e3f7f1; color: #0e8a70; font-size: 10px; }
.workflow-summary { margin: 15px 0; font-size: var(--text-md); font-weight: 600; }
.run-steps { display: flex; gap: 8px; margin: 0 0 16px; padding: 0; list-style: none; }
.run-steps li { flex: 1; min-width: 0; display: grid; grid-template-columns: 18px 1fr; gap: 2px 6px; padding: 9px; border-radius: 9px; background: var(--surface-2); }
.step-check { grid-row: span 2; width: 17px; height: 17px; display: grid; place-items: center; border-radius: 50%; background: var(--ok); color: #fff; font-size: 10px; }
.run-steps b { font-size: var(--text-2xs); }
.run-steps small { color: var(--text-3); font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.section-label { margin: 0 0 8px; color: var(--text-3); font-size: var(--text-2xs); font-weight: 600; }
.wf-findings { display: flex; flex-direction: column; gap: 6px; }
.finding { display: flex; flex-direction: column; gap: 3px; width: 100%; padding: 9px 11px; border: 1px solid var(--line); border-radius: 9px; background: var(--surface); color: var(--text); text-align: left; }
.finding:hover { border-color: var(--brand); }
.finding-source { color: var(--brand-strong); font-size: 10px; }
.finding b { font-size: var(--text-xs); font-weight: 600; line-height: 1.5; }
.finding small { color: var(--text-3); font-size: 10px; }
.wf-schedule { margin-top: 14px; }
.wf-schedule > div { display: flex; gap: 12px; padding: 6px 0; border-top: 1px solid var(--line); font-size: var(--text-xs); }
.wf-schedule time { color: var(--brand-strong); font-variant-numeric: tabular-nums; }

.composer-wrap { position: relative; width: min(820px, 100%); margin: 8px auto 0; }
.composer { display: flex; align-items: flex-end; gap: 8px; padding: 9px 10px; border-radius: 16px; box-shadow: var(--shadow-2); }
.composer:focus-within { border-color: color-mix(in srgb, var(--brand) 58%, var(--line)); }
.composer textarea { flex: 1; min-width: 0; max-height: 120px; padding: 8px 4px; border: none; outline: none; resize: none; background: transparent; font-size: var(--text-base); line-height: var(--leading-normal); }
.attach-btn { width: 34px; height: 34px; flex-shrink: 0; border: 1px solid var(--line); border-radius: 50%; background: var(--surface-2); color: var(--text); font-size: 22px; line-height: 1; }
.attach-btn:hover { border-color: var(--brand); color: var(--brand-strong); }
.icon-btn { width: 32px; height: 34px; flex-shrink: 0; border: none; background: transparent; color: var(--text-2); font-size: var(--text-xs); }
.send-btn { height: 34px; padding-inline: 16px; }
.stop-btn { height: 34px; padding: 0 13px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--text-2); font-size: var(--text-xs); }
.composer-hint { display: flex; justify-content: space-between; gap: 10px; padding: 7px 4px 0; color: var(--text-3); font-size: 10px; }

.cap-menu { position: absolute; left: 0; bottom: calc(100% + 10px); z-index: 30; width: min(660px, calc(100vw - 56px)); max-height: min(650px, calc(100vh - 180px)); overflow-y: auto; padding: 18px; box-shadow: var(--shadow-2); animation: menu-in 180ms var(--ease-out); }
.cap-menu-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.cap-menu-head h3 { margin: 0; font-size: var(--text-lg); }
.close-btn { width: 28px; height: 28px; border: none; border-radius: 50%; background: var(--surface-2); color: var(--text-2); font-size: 18px; line-height: 1; }
.cap-section + .cap-section { margin-top: 14px; }
.cap-section-title { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.cap-section-title b { font-size: var(--text-xs); }
.cap-section-title span { color: var(--text-3); font-size: 10px; }
.cap-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; }
.cap-grid button { position: relative; display: flex; align-items: center; gap: 8px; min-width: 0; padding: 10px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: var(--text); text-align: left; }
.cap-grid button:hover { border-color: var(--brand); background: var(--brand-weak); transform: translateY(-1px); }
.cap-grid button:disabled { opacity: .5; pointer-events: none; }
.cap-grid button > span:nth-child(2) { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.cap-grid b { font-size: var(--text-xs); }
.cap-grid small { color: var(--text-3); font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cap-grid i { margin-left: auto; color: var(--brand-strong); font-style: normal; }
.cap-glyph { width: 30px; height: 30px; display: grid; place-items: center; flex-shrink: 0; border-radius: 9px; background: var(--surface-2); color: var(--brand-strong); font-size: var(--text-xs); font-weight: 700; }
.cap-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--line); }
.cap-grid.compact { grid-template-columns: 1fr; }
.plugin-state { margin-left: auto; flex-shrink: 0; color: var(--text-3); font-size: 9px; }
.plugin-state.configured { color: var(--ok); }
.calendar-cap { width: 100%; display: flex; align-items: center; gap: 9px; margin-top: 14px; padding: 10px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); color: var(--text); text-align: left; }
.calendar-cap > span:nth-child(2) { display: flex; flex-direction: column; gap: 2px; }
.calendar-cap b { font-size: var(--text-xs); }
.calendar-cap small { color: var(--text-3); font-size: 10px; }
.calendar-cap i { margin-left: auto; color: var(--brand-strong); font-style: normal; }

.drawer-mask { position: fixed; inset: 0; z-index: 55; background: rgba(29, 28, 26, .22); backdrop-filter: blur(3px); }
.calendar-preview { position: absolute; top: 72px; right: 22px; bottom: 22px; width: min(390px, calc(100vw - 32px)); padding: 20px; overflow-y: auto; box-shadow: var(--shadow-2); animation: drawer-in 220ms var(--ease-out); }
.drawer-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 18px; }
.drawer-head h3 { margin: 0; font-size: var(--text-xl); }
.drawer-empty { padding: 30px 0; color: var(--text-3); text-align: center; font-size: var(--text-sm); }
.calendar-list { display: flex; flex-direction: column; gap: 8px; }
.calendar-item { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); }
.calendar-item time { color: var(--brand-strong); font-size: var(--text-xs); font-variant-numeric: tabular-nums; }
.calendar-item > div { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.calendar-item b { font-size: var(--text-sm); }
.calendar-item small { color: var(--text-3); font-size: 10px; }
.calendar-item button { margin-left: auto; border: none; background: transparent; color: var(--brand-strong); }
.full-calendar { width: 100%; margin-top: 18px; }

.mask { position: fixed; inset: 0; z-index: 70; display: grid; place-items: center; padding: 16px; background: rgba(29, 28, 26, .38); backdrop-filter: blur(4px); }
.approve { width: min(440px, 100%); overflow: hidden; box-shadow: var(--shadow-2); }
.warn-bar { padding: 10px 16px; background: var(--warn); color: #fff; font-size: var(--text-xs); }
.approve h4 { display: flex; align-items: center; gap: 8px; margin: 18px 16px 12px; font-size: var(--text-md); }
.ap-args { max-height: 200px; margin: 0 16px; padding: 12px; overflow: auto; border-radius: 9px; background: var(--surface-2); font-family: var(--font-mono); font-size: var(--text-xs); white-space: pre-wrap; }
.approval-note { margin: 12px 16px 0; color: var(--text-3); font-size: var(--text-xs); }
.ap-acts { display: flex; justify-content: flex-end; gap: 9px; margin: 16px; }
.toast { position: fixed; left: 50%; bottom: 28px; z-index: 90; max-width: min(520px, calc(100vw - 32px)); padding: 10px 16px; transform: translateX(-50%); border-radius: 999px; background: #241f1a; color: #fff; box-shadow: var(--shadow-2); font-size: var(--text-xs); }

@keyframes breathe { 50% { opacity: .35; transform: scale(.8); } }
@keyframes menu-in { from { opacity: 0; transform: translateY(8px) scale(.985); } to { opacity: 1; transform: none; } }
@keyframes drawer-in { from { opacity: 0; transform: translateX(18px); } to { opacity: 1; transform: none; } }

@media (max-width: 1120px) {
  .chat-workspace { grid-template-columns: 184px minmax(0, 1fr); }
  .agent-pill { display: none; }
}
@media (max-width: 860px) {
  .chat-workspace { grid-template-columns: 64px minmax(0, 1fr); gap: 10px; }
  .session-rail { padding: 9px; }
  .rail-label, .new-label, .session-copy, .agent-mini .session-copy, .online-dot { display: none; }
  .rail-head { justify-content: center; }
  .new-chat { width: 36px; height: 36px; justify-content: center; padding: 0; }
  .session-item { justify-content: center; padding: 10px 0; }
  .session-dot { width: 8px; height: 8px; margin: 0; }
  .agent-mini { justify-content: center; padding-inline: 0; }
  .cap-columns { grid-template-columns: 1fr; gap: 0; }
  .cap-menu { width: min(600px, calc(100vw - 40px)); }
}
@media (max-width: 620px) {
  .chat-workspace { display: block; }
  .session-rail { display: none; }
  .mobile-new { display: inline-grid; place-items: center; }
  .conversation-head { padding-inline: 0; }
  .welcome { padding: 24px 18px; }
  .quick { grid-template-columns: 1fr; }
  .messages { padding-inline: 0; }
  .bub { max-width: 96%; }
  .workflow-card { width: 100%; }
  .run-steps { flex-direction: column; }
  .cap-menu { position: fixed; left: 12px; right: 12px; bottom: 104px; width: auto; max-height: calc(100vh - 140px); }
  .cap-grid { grid-template-columns: 1fr; }
  .composer-hint span:last-child { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .messages, .cap-menu, .calendar-preview, .tool .dot.run { animation: none; scroll-behavior: auto; }
}
</style>
