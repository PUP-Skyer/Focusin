<script setup>
import { computed, nextTick, onMounted, onUnmounted, inject, ref } from 'vue'
import Mascot from '../components/Mascot.vue'
import ChannelIcon from '../components/ChannelIcon.vue'
import {
  get, post, chatStream, chatSessions, createChatSession, chatSessionMessages,
  runWorkflow, openMessageSource, modelCatalog, listWorkspaces, chooseWorkspace, grantWorkspace,
  setWorkspaceAccess, removeWorkspace, uploadChatFiles, deleteChatUploads
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
const approvalChoice = ref('deny')
const approvalEl = ref(null)
const deciding = ref(false)
const listEl = ref(null)
const composerEl = ref(null)
const capabilityOpen = ref(false)
const calendarOpen = ref(false)
const calendarItems = ref([])
const calendarLoading = ref(false)
const connectors = ref([])
const notice = ref('')
const attachments = ref([])
const uploading = ref(false)
const fileInput = ref(null)
const folderInput = ref(null)
const workspaceOpen = ref(false)
const workspacePath = ref('')
const workspaceAccess = ref('read')
const workspaceConfirm = ref(false)
const workspaceBusy = ref(false)
const workspaces = ref([])
const modelOptions = ref([])
const defaultModel = ref('')
const selectedModel = ref(localStorage.getItem('fi-chat-model') || '')
const reasoningEffort = ref(localStorage.getItem('fi-chat-effort') || 'medium')
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
  save_draft: '保存草稿',
  list_workspace: '查看工作区',
  read_workspace_file: '读取工作区文件',
  write_workspace_file: '写入工作区文件',
  read_attachment: '读取附件'
}
const EFFORT_LABELS = { low: '快速', medium: '标准', high: '深入' }
const RISK_LABELS = { safe: '只读', moderate: '需确认', sensitive: '敏感' }
const CHANNEL_LABELS = { wechat: '微信', qq: 'QQ', feishu: '飞书', email: '邮箱', dingtalk: '钉钉' }
const TOOL_FIELD_LABELS = {
  query: '检索关键词', channel: '渠道', limit: '数量', title: '标题', start_at: '时间',
  id: '编号', status: '状态', reason: '原因', ok: '结果', note: '说明', draft_id: '草稿编号',
  messages: '消息', results: '结果', text: '内容', sender: '发送者', ts: '时间', count: '数量',
  workspace_id: '目录编号', path: '路径', access: '权限', content: '文件内容',
  relative_path: '相对路径', size: '大小', group_key: '文件夹', skipped: '已跳过'
}

function decodeEncodedWords(text) {
  return String(text || '').replace(/=\?([^?]+)\?([bq])\?([^?]*)\?=/gi, (_, charset, encoding, payload) => {
    try {
      const normalized = encoding.toLowerCase() === 'b'
        ? atob(payload)
        : payload.replace(/_/g, ' ').replace(/=([0-9a-f]{2})/gi, (_, hex) =>
          String.fromCharCode(parseInt(hex, 16)))
      return new TextDecoder(charset).decode(Uint8Array.from(normalized, c => c.charCodeAt(0)))
    } catch {
      return ''
    }
  })
}

function humanText(value, multiline = false) {
  let text = typeof value === 'string' ? value : value == null ? '' : String(value)
  text = decodeEncodedWords(text)
    .replace(/=\?[^?\s]+\?[bq]\?[a-z0-9_=-]*…?/gi, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/<[^>]*>/g, ' ')
    .replace(/\\r\\n|\\n|\\r/g, '\n')
    .replace(/\r\n?/g, '\n')
    .replace(/\\/g, '')
    .replace(/\{?\s*['"]title['"]\s*:\s*['"]/gi, '')
    .replace(/[\\\s'"}]+$/, '')
  text = multiline
    ? text.replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim()
    : text.replace(/\s+/g, ' ').trim()
  return text || '未命名事项'
}

function excerpt(value, limit = 78) {
  const text = humanText(value)
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

function formatToolText(value) {
  if (value == null || value === '') return ''
  if (typeof value === 'string') {
    const text = value.trim()
    if (/^[\[{]/.test(text)) {
      try { return formatToolText(JSON.parse(text)) } catch { /* 保留普通文本 */ }
    }
    return humanText(value, true)
  }
  if (Array.isArray(value)) {
    return value.map((entry, index) => `${index + 1}. ${formatToolText(entry)}`).filter(Boolean).join('\n')
  }
  if (typeof value === 'object') {
    return Object.entries(value).map(([key, entry]) => {
      if (entry == null || entry === '') return ''
      const label = TOOL_FIELD_LABELS[key] || humanText(key)
      const content = key === 'ok' ? (entry ? '成功' : '失败') : formatToolText(entry)
      return content ? `${label}：${content.replace(/\n/g, '\n  ')}` : ''
    }).filter(Boolean).join('\n')
  }
  return humanText(value, true)
}

function formatSessionTime(ts) {
  const text = humanText(ts)
  const match = text.match(/(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  return match ? `${match[1]}/${match[2]} ${match[3]}:${match[4]}` : text
}

function formatEventTime(ts) {
  const text = humanText(ts)
  const match = text.match(/(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  return match ? `${match[1]}-${match[2]} ${match[3]}:${match[4]}` : text
}

function parseScheduleAnswer(text) {
  const lines = humanText(text, true).split('\n').map(line => line.trim()).filter(Boolean)
  const intro = []
  const items = []
  let current = null

  for (const line of lines) {
    const match = line.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s*[｜|]\s*(.+)$/)
    if (match) {
      const detail = match[3].match(/^(.*?)[（(](已确认|待确认)[）)]\s*依据[:：]\s*(.*)$/)
      const parsedTitle = detail ? detail[1].trim() : ''
      let source = detail ? detail[3].trim() : ''
      const sourceId = source.match(/[（(]日程#(\d+)[）)]\s*$/)
      const id = sourceId ? sourceId[1] : ''
      if (sourceId) source = source.slice(0, sourceId.index).trim()
      current = {
        date: match[1],
        time: match[2],
        title: parsedTitle || source || match[3],
        status: detail ? detail[2] : '',
        source: parsedTitle ? source : '',
        id
      }
      items.push(current)
    } else if (current) {
      const sourceId = line.match(/^[（(]日程#(\d+)[）)]$/)
      if (sourceId) current.id = sourceId[1]
      else current.source = `${current.source} ${line}`.trim()
    } else {
      intro.push(line)
    }
  }

  return items.length ? { intro, items } : null
}

function answerBlocks(text) {
  const schedule = parseScheduleAnswer(text)
  if (schedule) {
    return [
      ...schedule.intro.map(line => ({ type: 'paragraph', text: line })),
      { type: 'schedule', items: schedule.items }
    ]
  }

  return humanText(text, true).split(/\n{2,}/).map(chunk => {
    const lines = chunk.split('\n').map(line => line.trim()).filter(Boolean)
    if (lines.length === 1) {
      const heading = lines[0].match(/^#{1,3}\s+(.+)$/)
      if (heading) return { type: 'heading', level: lines[0].startsWith('###') ? 3 : 2, text: heading[1] }
    }
    const listItem = lines.length > 0 && lines.every(line => /^(?:[-•·]|\d+[.、])\s*/.test(line))
    if (!listItem) return { type: 'paragraph', text: lines.join('\n') }
    return {
      type: 'list',
      items: lines.map(line => {
        const match = line.match(/^([-•·]|\d+[.、])\s*(.*)$/)
        return { marker: match[1], text: match[2] }
      })
    }
  }).filter(Boolean)
}

function inlineParts(text) {
  return String(text || '').split(/(\*\*[^*\n]+\*\*)/g).filter(Boolean).map(part => ({
    text: part.startsWith('**') && part.endsWith('**') ? part.slice(2, -2) : part,
    bold: part.startsWith('**') && part.endsWith('**')
  }))
}

const currentTitle = computed(() => currentSession.value?.title || '新对话')
const currentMeta = computed(() => {
  const count = Number(currentSession.value?.message_count || 0)
  return count ? `${count} 条消息 · 仅保存在本机` : '本地会话 · 仅保存在本机'
})
const connectorByKey = computed(() => new Map(connectors.value.map(c => [c.key, c])))
const connectedNames = computed(() => connectors.value
  .filter(c => c.configured)
  .map(c => c.name)
  .slice(0, 3))
const contextText = computed(() => connectedNames.value.length
  ? `已连接 ${connectedNames.value.join(' · ')}`
  : '尚未连接消息渠道')
const running = computed(() => busy.value || workflowRunning.value)
const attachmentGroups = computed(() => {
  const groups = new Map()
  for (const attachment of attachments.value) {
    const key = attachment.group_key || `file:${attachment.id}`
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        id: attachment.id,
        name: attachment.kind === 'folder'
          ? attachment.group_key
          : attachment.relative_path || attachment.name,
        kind: attachment.kind,
        size: attachment.size || 0,
        count: 0,
        ids: []
      })
    }
    const group = groups.get(key)
    group.count += 1
    group.size += attachment.size || 0
    group.ids.push(attachment.id)
  }
  return [...groups.values()]
})
const modelChoices = computed(() => {
  const models = [...new Set([...modelOptions.value, defaultModel.value].filter(Boolean))]
  if (selectedModel.value && selectedModel.value !== 'local' && !models.includes(selectedModel.value)) {
    models.unshift(selectedModel.value)
  }
  return [{ value: 'local', label: '本地规则' }, ...models.map(model => ({ value: model, label: model }))]
})
const permissionLabel = computed(() => {
  if (!workspaces.value.length) return '未授权目录'
  return workspaces.value.some(item => item.access === 'write') ? '可编辑目录' : '只读目录'
})

function scrollBottom() {
  nextTick(() => { if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight })
}

function showNotice(text) {
  notice.value = text
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => { notice.value = '' }, 3600)
}

function formatBytes(size) {
  if (!size) return '0 KB'
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function persistChatOptions() {
  localStorage.setItem('fi-chat-model', selectedModel.value)
  localStorage.setItem('fi-chat-effort', reasoningEffort.value)
}

async function loadChatContext() {
  try {
    const [catalog, granted] = await Promise.all([
      modelCatalog().catch(() => ({ models: [], default: '' })),
      listWorkspaces().catch(() => [])
    ])
    modelOptions.value = catalog.models || []
    defaultModel.value = catalog.default || ''
    workspaces.value = granted
    if (!selectedModel.value) selectedModel.value = catalog.default || 'local'
  } catch {
    modelOptions.value = []
  }
}

function pickFiles(folder = false) {
  if (uploading.value || running.value) return
  capabilityOpen.value = false
  workspaceOpen.value = false
  const target = folder ? folderInput.value : fileInput.value
  target?.click()
}

async function onFilesSelected(event) {
  const files = [...(event.target.files || event.dataTransfer?.files || [])]
  event.target.value = ''
  if (!files.length || !currentSession.value || uploading.value) return
  uploading.value = true
  try {
    const result = await uploadChatFiles(currentSession.value.id, files)
    attachments.value.push(...(result.attachments || []))
    if (result.skipped) showNotice(`${result.skipped} 个敏感或超量文件已跳过`)
  } catch (e) {
    showNotice(`上传失败：${e.message}`)
  } finally {
    uploading.value = false
  }
}

async function removeAttachmentGroup(group) {
  attachments.value = attachments.value.filter(item => !group.ids.includes(item.id))
  if (!currentSession.value) return
  try {
    await deleteChatUploads(currentSession.value.id, group.ids)
  } catch (e) {
    showNotice(`移除附件失败：${e.message}`)
    await loadChatContext()
  }
}

async function discardAttachments() {
  const ids = attachments.value.map(item => item.id)
  const sessionId = currentSession.value?.id
  attachments.value = []
  if (ids.length && sessionId) {
    try { await deleteChatUploads(sessionId, ids) } catch { /* 已从本次输入移除 */ }
  }
}

async function chooseLocalWorkspace() {
  if (workspaceBusy.value) return
  workspaceBusy.value = true
  try {
    const result = await chooseWorkspace()
    if (result.path) workspacePath.value = result.path
  } catch (e) {
    showNotice(`选择目录失败：${e.message}`)
  } finally {
    workspaceBusy.value = false
  }
}

async function addWorkspace() {
  const path = workspacePath.value.trim()
  if (!path || workspaceBusy.value) return
  if (workspaceAccess.value === 'write' && !workspaceConfirm.value) {
    showNotice('请先确认：允许智能体在每次审批后写入此目录')
    return
  }
  workspaceBusy.value = true
  const grantedAccess = workspaceAccess.value
  try {
    const created = await grantWorkspace(path, grantedAccess)
    workspaces.value = [...workspaces.value.filter(item => item.id !== created.id), created]
    workspacePath.value = ''
    workspaceConfirm.value = false
    workspaceAccess.value = 'read'
    showNotice(grantedAccess === 'write' ? '已授予编辑权限，写入仍需逐次确认' : '已授予目录只读权限')
  } catch (e) {
    showNotice(`目录授权失败：${e.message}`)
  } finally {
    workspaceBusy.value = false
  }
}

async function changeWorkspaceAccess(item, access) {
  if (workspaceBusy.value || item.access === access) return
  if (access === 'write' && !window.confirm(`允许智能体在每次审批后写入「${item.path}」吗？`)) return
  workspaceBusy.value = true
  try {
    const updated = await setWorkspaceAccess(item.id, access)
    workspaces.value = workspaces.value.map(entry => entry.id === updated.id ? updated : entry)
  } catch (e) {
    showNotice(`权限更新失败：${e.message}`)
  } finally {
    workspaceBusy.value = false
  }
}

async function deleteWorkspace(item) {
  workspaceBusy.value = true
  try {
    await removeWorkspace(item.id)
    workspaces.value = workspaces.value.filter(entry => entry.id !== item.id)
  } catch (e) {
    showNotice(`移除目录失败：${e.message}`)
  } finally {
    workspaceBusy.value = false
  }
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
  if (running.value || uploading.value || session.id === currentSession.value?.id) return
  await discardAttachments()
  currentSession.value = session
  localStorage.setItem('fi-chat-session', session.id)
  capabilityOpen.value = false
  workspaceOpen.value = false
  try {
    await loadMessages(session.id)
  } catch (e) {
    showNotice(`读取会话失败：${e.message}`)
  }
}

async function newConversation() {
  if (running.value || uploading.value) return
  await discardAttachments()
  try {
    const session = await createChatSession()
    sessions.value.unshift(session)
    await selectSession(session)
    input.value = ''
    workspaceOpen.value = false
    nextTick(() => composerEl.value?.focus())
  } catch (e) {
    showNotice(`创建会话失败：${e.message}`)
  }
}

async function send(text) {
  const msg = (text ?? input.value).trim()
  const pendingAttachments = [...attachments.value]
  const attachmentIds = pendingAttachments.map(item => item.id)
  if ((!msg && !attachmentIds.length) || running.value || uploading.value || !currentSession.value) return
  const displayText = msg || `请查看我上传的 ${attachmentGroups.value.length} 项内容。`
  const model = selectedModel.value
  const effort = reasoningEffort.value
  persistChatOptions()
  input.value = ''
  attachments.value = []
  capabilityOpen.value = false
  workspaceOpen.value = false
  busy.value = true
  setMood('working')
  items.value.push({ kind: 'user', text: displayText })

  const assistant = { kind: 'assistant', text: '', thinking: [], tools: [] }
  items.value.push(assistant)
  let sawApproval = false
  abortController = new AbortController()
  scrollBottom()

  try {
    for await (const ev of chatStream(displayText, {
      sessionId: currentSession.value.id,
      signal: abortController.signal,
      model,
      reasoningEffort: effort,
      attachmentIds
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
        approvalChoice.value = 'deny'
        deciding.value = false
        setMood('waiting')
        scrollBottom()
        nextTick(() => approvalEl.value?.focus())
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
  approvalChoice.value = decision
  try {
    await post(`/approvals/${approval.value.id}/decision`, { decision })
  } catch (e) {
    deciding.value = false
    showNotice(`审批提交失败：${e.message}`)
  }
}

function onApprovalKeydown(e) {
  if (!approval.value || deciding.value) return
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    approvalChoice.value = approvalChoice.value === 'deny' ? 'approve' : 'deny'
    e.preventDefault()
  } else if (e.key === 'Enter') {
    e.preventDefault()
    decide(approvalChoice.value)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    decide('deny')
  }
}

async function executeWorkflow(id) {
  if (running.value || !currentSession.value) return
  capabilityOpen.value = false
  workspaceOpen.value = false
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

function onGlobalKeydown(e) {
  if (e.key !== 'Escape' || approval.value) return
  capabilityOpen.value = false
  workspaceOpen.value = false
  calendarOpen.value = false
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
  window.addEventListener('keydown', onGlobalKeydown)
  try {
    const [, loadedConnectors] = await Promise.all([loadSessions(), get('/connectors')])
    loadChatContext()
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
  window.removeEventListener('keydown', onGlobalKeydown)
  abortController?.abort()
  clearTimeout(noticeTimer)
  rec.value?.abort()
})
</script>

<template>
  <div class="chat-workspace">
    <aside class="session-rail" aria-label="对话会话">
      <div class="rail-head">
        <div class="rail-heading">
          <span class="rail-label">工作空间</span>
          <small>{{ sessions.length }} 个会话</small>
        </div>
        <button class="new-chat" title="新对话" :disabled="running" @click="newConversation">
          <span class="new-plus">+</span><span class="new-label">新对话</span>
        </button>
      </div>
      <div class="session-section-label">最近对话</div>
      <div class="session-list">
        <button v-for="session in sessions" :key="session.id"
          class="session-item" :class="{ on: session.id === currentSession?.id }"
          :disabled="running" @click="selectSession(session)">
          <span class="session-mark">{{ session.title.slice(0, 1) }}</span>
          <span class="session-copy">
            <b>{{ session.title }}</b>
            <small><time class="time-pill">{{ formatSessionTime(session.updated_at) }}</time><i v-if="session.message_count"> · {{ session.message_count }} 条</i></small>
          </span>
          <span class="session-active" />
        </button>
        <p v-if="!sessions.length" class="rail-empty">还没有历史对话</p>
      </div>
      <div class="agent-mini">
        <Mascot mood="idle" :size="32" />
        <div class="session-copy"><b>小聚</b><small>本地消息智能体</small></div>
        <span class="online-dot" />
      </div>
    </aside>

    <section class="conversation">
      <header class="conversation-head">
        <div class="conversation-title">
          <button class="mobile-new" title="新对话" :disabled="running" @click="newConversation">+</button>
          <div class="title-copy">
            <h2>{{ currentTitle }}</h2>
            <p>{{ currentMeta }}</p>
          </div>
          <span class="agent-pill"><span />小聚 · 本地智能体</span>
        </div>
        <div class="head-actions">
          <span class="context-pill" :title="contextText"><i />{{ contextText }}</span>
          <button class="calendar-link" @click="openCalendar"><span>历</span>查看日程</button>
        </div>
      </header>

      <div ref="listEl" class="messages">
        <div v-if="!items.length" class="welcome">
          <div class="welcome-top">
            <div class="welcome-mark"><Mascot mood="idle" :size="46" /></div>
            <div><p class="eyebrow">FOCUSIN AGENT</p><span class="ready-label"><i />小聚正在待命</span></div>
          </div>
          <h1>把注意力留给<br class="desktop-break" />真正重要的事。</h1>
          <p class="welcome-desc">我会基于你已订阅的消息与日程工作。先给结论，再给出处；外发内容只起草，不代发。</p>
          <div class="context-strip">
            <span class="context-strip-label">当前上下文</span>
            <b>{{ contextText }}</b>
            <span>仅读取你手动订阅的会话</span>
          </div>
          <div class="quick">
            <button v-for="(q, index) in QUICK" :key="q" class="quick-item" @click="send(q)">
              <span class="quick-index">0{{ index + 1 }}</span>
              <span>{{ q }}</span><i>↗</i>
            </button>
          </div>
        </div>

        <template v-for="(m, i) in items" :key="i">
          <div v-if="m.kind === 'user'" class="bub user-bub">{{ m.text }}</div>

          <div v-else-if="m.kind === 'workflow'" class="workflow-card card">
            <div class="workflow-head">
              <span class="workflow-glyph">{{ WORKFLOWS.find(w => w.id === m.run.workflow_id)?.glyph || '自' }}</span>
              <div><p class="eyebrow">自动化工作流</p><h3>{{ humanText(m.run.title) }}</h3></div>
              <span class="done-pill">已完成</span>
            </div>
            <p class="workflow-summary">{{ humanText(m.run.summary) }}</p>
            <ol class="run-steps">
              <li v-for="(step, j) in m.run.steps" :key="j">
                <span class="step-check">✓</span><b>{{ humanText(step.name) }}</b><small>{{ humanText(step.detail) }}</small>
              </li>
            </ol>
            <div v-if="m.run.data?.messages?.length" class="wf-findings">
              <p class="section-label">优先关注</p>
              <button v-for="message in m.run.data.messages.slice(0, 4)" :key="message.id"
                class="finding" @click="openSource(message)">
                <span class="finding-source">{{ CHANNEL_LABELS[message.channel] || message.channel }} · {{ humanText(message.title) }}</span>
                <b>{{ excerpt(message.text) }}</b>
                <small><time class="time-pill">{{ formatEventTime(message.ts) }}</time><span> · {{ humanText(message.sender) }}</span></small>
              </button>
            </div>
            <div v-if="m.run.data?.schedule?.length" class="wf-schedule">
              <p class="section-label">最近日程</p>
              <div v-for="event in m.run.data.schedule.slice(0, 3)" :key="event.id">
                <time class="time-pill">{{ formatEventTime(event.start_at) }}</time><span>{{ humanText(event.title) }}</span>
              </div>
            </div>
          </div>

          <div v-else class="assistant-turn">
            <div class="assistant-meta">
              <Mascot mood="idle" :size="30" />
              <div><b>小聚</b><span>消息智能体</span></div>
              <span v-if="m.tools?.some(t => t.ok === null)" class="turn-state"><i />正在处理</span>
              <span v-else-if="m.text" class="turn-state done">已完成</span>
            </div>
            <div class="assistant-content">
              <details v-if="m.thinking?.length" class="think">
                <summary><span class="summary-dot think-dot" />思考过程 <span>{{ m.thinking.length }} 步</span><i>⌄</i></summary>
                <div class="think-body"><p v-for="(t, j) in m.thinking" :key="j">{{ t }}</p></div>
              </details>

              <div v-if="m.tools?.length" class="tool-timeline">
                <details v-for="(t, j) in m.tools" :key="'t' + j" class="tool"
                  :class="{ bad: t.ok === false }" :open="t.ok === null">
                  <summary>
                    <span class="tool-node" :class="{ run: t.ok === null, okk: t.ok === true, bad: t.ok === false }">
                      <i v-if="t.ok === true">✓</i><i v-else-if="t.ok === false">!</i>
                    </span>
                    <b>{{ toolLabel(t.name) }}</b>
                    <span class="risk" :class="'r-' + t.risk">{{ RISK_LABELS[t.risk] || t.risk }}</span>
                    <em>{{ t.ok === null ? '运行中' : t.ok ? '已完成' : '失败' }}</em>
                    <i class="tool-chevron">⌄</i>
                  </summary>
                  <div class="tool-body">
                    <div class="t-readable">
                      <span class="t-label">操作内容</span>
                      <p>{{ formatToolText(t.args) }}</p>
                    </div>
                    <div v-if="t.result" class="t-readable">
                      <span class="t-label">执行结果</span>
                      <p>{{ formatToolText(t.result) }}</p>
                    </div>
                  </div>
                </details>
              </div>

              <div v-if="m.tools?.some(t => t.ok === null && t.risk !== 'safe')" class="wait-approval">
                <span>!</span>有操作正在等待你的确认，批准前不会执行。
              </div>
              <div v-if="m.text" class="bot-answer">
                <template v-for="(block, blockIndex) in answerBlocks(m.text)" :key="blockIndex">
                  <p v-if="block.type === 'paragraph'" class="answer-paragraph"><template v-for="(part, partIndex) in inlineParts(block.text)" :key="partIndex"><b v-if="part.bold">{{ part.text }}</b><template v-else>{{ part.text }}</template></template></p>
                  <h4 v-else-if="block.type === 'heading'" class="answer-heading" :class="'level-' + block.level"><template v-for="(part, partIndex) in inlineParts(block.text)" :key="partIndex"><b v-if="part.bold">{{ part.text }}</b><template v-else>{{ part.text }}</template></template></h4>
                  <div v-else-if="block.type === 'list'" class="answer-list">
                    <div v-for="(entry, entryIndex) in block.items" :key="entryIndex" class="answer-list-item">
                      <span class="answer-list-marker">{{ entry.marker }}</span>
                      <p><template v-for="(part, partIndex) in inlineParts(entry.text)" :key="partIndex"><b v-if="part.bold">{{ part.text }}</b><template v-else>{{ part.text }}</template></template></p>
                    </div>
                  </div>
                  <div v-else class="answer-schedule">
                    <article v-for="entry in block.items" :key="entry.id || `${entry.date}-${entry.time}-${entry.title}`" class="answer-schedule-item">
                      <div class="answer-item-meta">
                        <time class="time-pill">{{ entry.date }} {{ entry.time }}</time>
                        <span v-if="entry.status" class="answer-status" :class="entry.status === '已确认' ? 'confirmed' : 'pending'">
                          {{ entry.status }}
                        </span>
                      </div>
                      <div class="answer-item-body">
                        <h4>{{ entry.title }}</h4>
                        <p v-if="entry.source" class="answer-source"><span>依据</span>{{ entry.source }}</p>
                      </div>
                    </article>
                  </div>
                </template>
              </div>
              <div v-if="m.text" class="assistant-actions">
                <span>内容来自本机已订阅上下文</span>
                <button class="copy-btn" title="复制回复" @click="copyText(m.text)">复制回复</button>
              </div>
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
                  <ChannelIcon v-if="plugin.key !== 'connectors'" :channel="plugin.key" />
                  <span v-else class="cap-glyph">{{ plugin.glyph }}</span>
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
          <p class="cap-footnote">能力仅在本机运行；外发内容永远只起草，不代发。</p>
        </div>

        <div v-if="workspaceOpen" class="workspace-menu card" role="dialog" aria-label="本地目录访问权限">
          <div class="workspace-head">
            <div><p class="eyebrow">LOCAL WORKSPACE</p><h3>访问本地目录</h3></div>
            <button class="close-btn" title="关闭" @click="workspaceOpen = false">×</button>
          </div>
          <p class="workspace-intro">只授权你明确选择的目录。默认只读，敏感文件始终不可访问。</p>
          <label class="workspace-path">
            <span>目录绝对路径</span>
            <div class="workspace-path-row">
              <input v-model="workspacePath" placeholder="选择目录或手动填写，如 D:\项目\资料" @keydown.enter.prevent="addWorkspace" />
              <button class="btn workspace-choose" :disabled="workspaceBusy" @click="chooseLocalWorkspace">
                {{ workspaceBusy ? '请稍候…' : '选择目录' }}
              </button>
            </div>
          </label>
          <div class="workspace-grant-row">
            <div class="access-switch" aria-label="新目录访问权限">
              <button :class="{ on: workspaceAccess === 'read' }" @click="workspaceAccess = 'read'; workspaceConfirm = false">只读</button>
              <button :class="{ on: workspaceAccess === 'write' }" @click="workspaceAccess = 'write'">可编辑</button>
            </div>
            <button class="btn btn-brand" :disabled="!workspacePath.trim() || workspaceBusy" @click="addWorkspace">授权目录</button>
          </div>
          <label v-if="workspaceAccess === 'write'" class="workspace-confirm">
            <input v-model="workspaceConfirm" type="checkbox" />
            <span>我确认允许写入；每次实际写入仍会单独审批。</span>
          </label>
          <div v-if="workspaces.length" class="workspace-list">
            <p class="workspace-list-label">已授权目录</p>
            <article v-for="item in workspaces" :key="item.id" class="workspace-item">
              <span class="workspace-item-icon">▱</span>
              <div class="workspace-item-copy"><b :title="item.path">{{ item.path }}</b><small>{{ item.access === 'write' ? '可编辑 · 写入需审批' : '只读' }}</small></div>
              <div class="workspace-item-actions">
                <button :class="{ on: item.access === 'read' }" :disabled="workspaceBusy" @click="changeWorkspaceAccess(item, 'read')">只读</button>
                <button :class="{ on: item.access === 'write' }" :disabled="workspaceBusy" @click="changeWorkspaceAccess(item, 'write')">编辑</button>
                <button class="remove-workspace" title="移除目录" :disabled="workspaceBusy" @click="deleteWorkspace(item)">×</button>
              </div>
            </article>
          </div>
          <p class="workspace-security">路径会被限制在已授权目录内；系统目录、密钥文件与凭据目录不可访问。</p>
        </div>

        <footer class="composer card" @dragover.prevent @drop.prevent="onFilesSelected">
          <div v-if="attachmentGroups.length" class="attachment-strip">
            <div v-for="group in attachmentGroups" :key="group.key" class="attachment-chip">
              <span class="attachment-kind">{{ group.kind === 'folder' ? '▱' : '▤' }}</span>
              <span class="attachment-copy"><b :title="group.name">{{ group.name }}</b><small>{{ group.count > 1 ? `${group.count} 个文件 · ${formatBytes(group.size)}` : formatBytes(group.size) }}</small></span>
              <button title="移除附件" :disabled="uploading" @click="removeAttachmentGroup(group)">×</button>
            </div>
          </div>
          <textarea ref="composerEl" v-model="input" rows="1" placeholder="问消息、查日程、发起工作流，或添加本地文件……"
            @input="autoGrow" @keydown="onComposerKeydown" />
          <div class="composer-toolbar">
            <div class="composer-tools">
              <button class="composer-icon plus-btn" title="添加能力" :aria-expanded="capabilityOpen"
                :disabled="running" @click="capabilityOpen = !capabilityOpen; workspaceOpen = false">+</button>
              <button class="composer-icon" title="上传文件" aria-label="上传文件"
                :disabled="running || uploading" @click="pickFiles(false)">↗</button>
              <button class="composer-icon" title="上传文件夹" aria-label="上传文件夹"
                :disabled="running || uploading" @click="pickFiles(true)">▱</button>
              <button class="permission-pill" :class="{ granted: workspaces.length }" :aria-expanded="workspaceOpen"
                :disabled="running" @click="workspaceOpen = !workspaceOpen; capabilityOpen = false">
                <span>!</span>{{ permissionLabel }}
              </button>
              <span v-if="uploading" class="upload-state"><i />上传中</span>
            </div>
            <div class="composer-options">
              <select v-model="selectedModel" class="composer-select model-select" title="选择模型" aria-label="选择模型" @change="persistChatOptions">
                <option v-for="model in modelChoices" :key="model.value" :value="model.value">{{ model.label }}</option>
              </select>
              <select v-model="reasoningEffort" class="composer-select effort-select" title="思考强度" aria-label="思考强度" @change="persistChatOptions">
                <option v-for="(label, value) in EFFORT_LABELS" :key="value" :value="value">{{ label }}</option>
              </select>
              <button v-if="sr" class="composer-icon voice-btn" title="语音输入" :disabled="running" @click="speak">语</button>
              <button v-if="busy" class="stop-btn" @click="stop">停止</button>
              <button v-else class="send-btn" :disabled="(!input.trim() && !attachments.length) || uploading || workflowRunning || !currentSession" @click="send()">
                <span>发送</span><i>↑</i>
              </button>
            </div>
          </div>
          <input ref="fileInput" class="hidden-input" type="file" multiple @change="onFilesSelected" />
          <input ref="folderInput" class="hidden-input" type="file" webkitdirectory directory multiple @change="onFilesSelected" />
        </footer>
        <div class="composer-hint"><span>Enter 发送 · Shift + Enter 换行</span><span>{{ workspaces.length ? `${workspaces.length} 个目录已授权` : '消息与凭据仅保存在本机' }}</span></div>
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
          <time class="time-pill">{{ formatEventTime(event.start_at) }}</time>
          <div><b>{{ humanText(event.title) }}</b><small>{{ event.status === 'confirmed' ? '已确认' : '待确认' }}</small></div>
          <button v-if="event.source" title="查看原文" @click="openSource(event.source)">↗</button>
        </div>
      </div>
      <button class="btn btn-brand full-calendar" @click="goTab('calendar')">打开完整日历</button>
    </aside>
  </div>

  <div v-if="approval" class="mask" @click.self="decide('deny')">
    <div ref="approvalEl" class="approve card" role="dialog" aria-modal="true" aria-labelledby="approval-title"
      tabindex="-1" @keydown="onApprovalKeydown">
      <div class="warn-bar"><span>!</span>敏感操作审批 · 点击遮罩默认拒绝</div>
      <div class="approval-heading">
        <p class="eyebrow">HUMAN IN THE LOOP</p>
        <h4 id="approval-title">{{ toolLabel(approval.tool) }} <span :class="'risk r-' + approval.risk">{{ RISK_LABELS[approval.risk] || approval.risk }}</span></h4>
        <p>小聚需要你的明确许可，才会继续执行。</p>
      </div>
      <div class="ap-args">
        <span class="t-label">操作内容</span>
        <p>{{ formatToolText(approval.args) }}</p>
      </div>
      <p class="approval-note">仅本次授权。操作执行后会写入本地审计日志。</p>
      <div class="ap-acts">
        <button class="btn" :class="{ selected: approvalChoice === 'deny' }" :disabled="deciding" @click="decide('deny')">拒绝</button>
        <button class="btn btn-primary" :class="{ selected: approvalChoice === 'approve' }" :disabled="deciding" @click="decide('approve')">批准执行</button>
      </div>
      <p class="approval-shortcut">← → 选择 · Enter 确认 · Esc 拒绝</p>
    </div>
  </div>

  <div v-if="notice" class="toast">{{ notice }}</div>
</template>

<style scoped>
.chat-workspace {
  display: grid; grid-template-columns: 208px minmax(0, 1fr); height: 100%; min-height: 0;
  overflow: hidden; border: 1px solid var(--line); border-radius: 16px;
  background: var(--surface); box-shadow: var(--shadow-1);
  font-family: "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif;
}
.calendar-preview, .approve, .toast {
  font-family: "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif;
}
.session-rail {
  display: flex; flex-direction: column; min-height: 0; padding: 16px 12px 12px;
  border-right: 1px solid var(--line);
  background: color-mix(in srgb, var(--surface-2) 68%, var(--surface));
}
.rail-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 22px; }
.rail-heading { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.rail-label { color: var(--text); font-size: var(--text-sm); font-weight: 700; letter-spacing: -.01em; }
.rail-heading small { color: var(--text-3); font-size: 10px; }
.new-chat {
  height: 34px; display: inline-flex; align-items: center; gap: 5px; padding: 0 11px;
  border: 1px solid var(--text); border-radius: 999px; background: var(--text); color: var(--surface);
  font-size: var(--text-xs); font-weight: 600; transition: background var(--dur-1) var(--ease-out), transform var(--dur-1) var(--ease-out);
}
.new-chat:hover { background: color-mix(in srgb, var(--text) 86%, var(--surface)); }
.new-chat:active { transform: scale(.97); }
.new-chat:disabled { opacity: .45; pointer-events: none; }
.new-plus { font-size: 17px; font-weight: 400; line-height: 1; }
.session-section-label { margin: 0 8px 8px; color: var(--text-3); font-size: 10px; font-weight: 600; letter-spacing: .08em; }
.session-list { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.session-item {
  position: relative; display: flex; align-items: center; gap: 9px; width: 100%; min-height: 52px;
  padding: 8px; border: 1px solid transparent; border-radius: 10px; background: transparent;
  color: var(--text-2); text-align: left; transition: background var(--dur-1) var(--ease-out), border-color var(--dur-1) var(--ease-out);
}
.session-item:hover { background: color-mix(in srgb, var(--surface) 55%, transparent); }
.session-item.on { border-color: var(--line); background: var(--surface); color: var(--text); box-shadow: 0 1px 2px rgba(29,28,26,.04); }
.session-item:disabled { opacity: .5; pointer-events: none; }
.session-mark {
  width: 28px; height: 28px; display: grid; place-items: center; flex-shrink: 0;
  border-radius: 8px; background: var(--surface-2); color: var(--text-3);
  font-size: var(--text-xs); font-weight: 700;
}
.session-item.on .session-mark { background: var(--brand-weak); color: var(--brand-strong); }
.session-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 3px; }
.session-copy b { overflow: hidden; font-size: var(--text-xs); font-weight: 700; white-space: nowrap; text-overflow: ellipsis; }
.session-copy small { display: flex; align-items: center; gap: 4px; color: var(--text-3); font-size: 10px; white-space: nowrap; }
.session-copy small i { font-style: normal; }
.time-pill {
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
  padding: 3px 8px; border: 1px solid color-mix(in srgb, var(--brand) 18%, var(--line));
  border-radius: 999px; background: var(--brand-weak); color: var(--brand-strong);
  font-family: inherit; font-size: 10px; font-weight: 700; font-variant-numeric: tabular-nums;
  line-height: 1.2; white-space: nowrap;
}
.session-active { width: 5px; height: 5px; flex-shrink: 0; border-radius: 50%; background: transparent; }
.session-item.on .session-active { background: var(--brand); }
.rail-empty { padding: 12px 8px; color: var(--text-3); font-size: var(--text-xs); line-height: 1.6; }
.agent-mini { display: flex; align-items: center; gap: 9px; margin-top: 12px; padding: 13px 8px 2px; border-top: 1px solid var(--line); }
.online-dot { width: 7px; height: 7px; margin-left: auto; border-radius: 50%; background: var(--ok); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 12%, transparent); }

.conversation { min-width: 0; min-height: 0; display: flex; flex-direction: column; background: var(--surface); }
.conversation-head {
  min-height: 72px; display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 14px 24px; border-bottom: 1px solid var(--line);
}
.conversation-title { min-width: 0; display: flex; align-items: center; gap: 12px; }
.title-copy { min-width: 0; }
.conversation-title h2 { margin: 0; overflow: hidden; font-size: 17px; font-weight: 700; letter-spacing: -.02em; white-space: nowrap; text-overflow: ellipsis; }
.title-copy p { margin: 3px 0 0; color: var(--text-3); font-size: 10px; line-height: 1.4; }
.agent-pill {
  display: inline-flex; align-items: center; gap: 6px; flex-shrink: 0; padding: 5px 9px;
  border: 1px solid var(--line); border-radius: 999px; background: var(--surface-2);
  color: var(--text-2); font-size: 10px; font-weight: 500;
}
.agent-pill span { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); }
.head-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.context-pill {
  max-width: 220px; display: inline-flex; align-items: center; gap: 6px; overflow: hidden;
  color: var(--text-3); font-size: 10px; white-space: nowrap; text-overflow: ellipsis;
}
.context-pill i, .ready-label i { width: 6px; height: 6px; flex-shrink: 0; border-radius: 50%; background: var(--brand); }
.calendar-link {
  height: 34px; display: inline-flex; align-items: center; gap: 7px; padding: 0 12px;
  border: 1px solid var(--line); border-radius: 999px; background: var(--surface);
  color: var(--text-2); font-size: var(--text-xs); font-weight: 600;
  transition: border-color var(--dur-1) var(--ease-out), color var(--dur-1) var(--ease-out);
}
.calendar-link span { color: var(--brand-strong); font-size: 10px; font-weight: 700; }
.calendar-link:hover { border-color: var(--brand); color: var(--brand-strong); }
.mobile-new { display: none; width: 34px; height: 34px; place-items: center; border: 1px solid var(--line); border-radius: 50%; background: var(--surface); font-size: 18px; }

.messages {
  flex: 1; min-height: 0; overflow-y: auto; padding: 24px clamp(20px, 4vw, 48px) 28px;
  display: flex; flex-direction: column; gap: 24px; scroll-behavior: smooth;
  background: radial-gradient(circle at 18% 0%, color-mix(in srgb, var(--brand-weak) 28%, transparent), transparent 32%), var(--surface);
}
.welcome { position: relative; width: min(760px, 100%); margin: auto; padding: clamp(24px, 5vh, 52px) 0; }
.welcome-top { display: flex; align-items: center; gap: 13px; margin-bottom: 28px; }
.welcome-mark {
  width: 54px; height: 54px; display: grid; place-items: center; border: 1px solid var(--line);
  border-radius: 16px; background: var(--surface); box-shadow: var(--shadow-1);
}
.eyebrow { margin: 0 0 5px; color: var(--brand-strong); font-size: 10px; font-weight: 700; letter-spacing: .13em; }
.ready-label { display: inline-flex; align-items: center; gap: 6px; color: var(--text-2); font-size: var(--text-xs); }
.ready-label i { background: var(--ok); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 10%, transparent); }
.welcome h1 { max-width: 660px; margin: 0; font-size: clamp(30px, 3.4vw, 42px); font-weight: 750; line-height: 1.16; letter-spacing: -.045em; }
.welcome-desc { max-width: 620px; margin: 18px 0 0; color: var(--text-2); font-size: 15px; line-height: 1.8; }
.context-strip {
  display: flex; align-items: center; gap: 12px; margin: 28px 0 18px; padding: 12px 14px;
  border: 1px solid var(--line); border-radius: 10px; background: color-mix(in srgb, var(--surface-2) 62%, transparent);
  color: var(--text-3); font-size: 10px;
}
.context-strip-label { color: var(--text-3); font-weight: 600; letter-spacing: .04em; }
.context-strip b { color: var(--text-2); font-size: var(--text-xs); font-weight: 600; }
.context-strip > span:last-child { margin-left: auto; }
.quick { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.quick-item {
  display: flex; align-items: center; gap: 12px; min-height: 58px; padding: 12px 14px;
  border: 1px solid var(--line); border-radius: 12px; background: var(--surface);
  color: var(--text); text-align: left; font-size: var(--text-sm); font-weight: 700;
  transition: border-color var(--dur-1) var(--ease-out), background var(--dur-1) var(--ease-out), transform var(--dur-1) var(--ease-out);
}
.quick-item:hover { border-color: color-mix(in srgb, var(--brand) 55%, var(--line)); background: color-mix(in srgb, var(--brand-weak) 32%, var(--surface)); transform: translateY(-1px); }
.quick-item:active { transform: scale(.99); }
.quick-index { color: var(--brand-strong); font-family: var(--font-mono); font-size: 10px; }
.quick-item i { margin-left: auto; color: var(--text-3); font-size: 14px; font-style: normal; }
.quick-item:hover i { color: var(--brand-strong); }

.user-bub {
  align-self: flex-end; max-width: min(78%, 640px); padding: 12px 16px;
  border: 1px solid var(--line); border-radius: 14px 14px 4px 14px;
  background: var(--surface-2); color: var(--text); font-size: 14px; line-height: 1.7; white-space: pre-wrap;
}
.assistant-turn { align-self: center; width: min(780px, 100%); }
.assistant-meta { display: flex; align-items: center; gap: 9px; margin-bottom: 10px; }
.assistant-meta > div { display: flex; align-items: baseline; gap: 7px; }
.assistant-meta b { font-size: var(--text-sm); font-weight: 700; }
.assistant-meta > div span { color: var(--text-3); font-size: 10px; }
.turn-state { display: inline-flex; align-items: center; gap: 5px; margin-left: auto; color: var(--brand-strong); font-size: 10px; }
.turn-state i { width: 5px; height: 5px; border-radius: 50%; background: var(--brand); animation: breathe 1s infinite; }
.turn-state.done { color: var(--ok); }
.assistant-content { min-width: 0; padding-left: 39px; }
.think, .tool { width: 100%; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: var(--text-2); }
.think { margin-bottom: 8px; background: color-mix(in srgb, var(--surface-2) 55%, var(--surface)); }
.think summary, .tool summary { cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px; min-height: 38px; padding: 8px 11px; }
.think summary::-webkit-details-marker, .tool summary::-webkit-details-marker { display: none; }
.think summary { font-size: var(--text-xs); }
.think summary > span:nth-child(2) { margin-left: auto; color: var(--text-3); font-size: 10px; }
.think summary > i, .tool-chevron { margin-left: 4px; color: var(--text-3); font-size: 12px; font-style: normal; transition: transform var(--dur-1) var(--ease-out); }
.think[open] summary > i, .tool[open] .tool-chevron { transform: rotate(180deg); }
.summary-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-3); }
.think-dot { background: color-mix(in srgb, var(--brand) 65%, var(--text-3)); }
.think-body { padding: 0 12px 10px 25px; }
.think-body p { margin: 5px 0; color: var(--text-3); font-size: var(--text-xs); line-height: 1.65; }
.tool-timeline { position: relative; display: flex; flex-direction: column; gap: 7px; margin: 4px 0 12px; }
.tool-timeline::before { content: ''; position: absolute; left: 20px; top: 18px; bottom: 18px; width: 1px; background: var(--line); }
.tool { position: relative; }
.tool summary b { min-width: 0; font-size: var(--text-xs); font-weight: 600; }
.tool-node {
  position: relative; z-index: 1; width: 19px; height: 19px; display: grid; place-items: center; flex-shrink: 0;
  border: 1px solid var(--line); border-radius: 50%; background: var(--surface-2); color: #fff; font-size: 10px; font-style: normal;
}
.tool-node.run { border-color: var(--brand); background: var(--brand); animation: tool-pulse 1.2s ease-in-out infinite; }
.tool-node.okk { border-color: var(--ok); background: var(--ok); }
.tool-node.bad { border-color: var(--warn); background: var(--warn); }
.risk { margin-left: auto; padding: 2px 7px; border-radius: 999px; font-size: 9px; font-weight: 600; line-height: 1.4; }
.r-safe { background: color-mix(in srgb, var(--ok) 11%, var(--surface)); color: color-mix(in srgb, var(--ok) 82%, var(--text)); }
.r-moderate { background: var(--brand-weak); color: var(--brand-strong); }
.r-sensitive { background: color-mix(in srgb, var(--warn) 10%, var(--surface)); color: color-mix(in srgb, var(--warn) 82%, var(--text)); }
.tool summary em { color: var(--text-3); font-size: 9px; font-style: normal; }
.tool-chevron { margin-left: 0; }
.tool-body { padding: 10px 12px 12px 38px; border-top: 1px solid var(--line); }
.t-readable { padding: 10px 11px; border-radius: 8px; background: var(--surface-2); }
.t-readable + .t-readable { margin-top: 8px; }
.t-label { display: block; margin-bottom: 5px; color: var(--text-3); font-size: 9px; font-weight: 700; letter-spacing: .04em; }
.t-readable p { max-height: 180px; margin: 0; overflow: auto; color: var(--text-2); font-family: inherit; font-size: 11px; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.wait-approval { display: flex; align-items: center; gap: 8px; margin: 4px 0 12px; padding: 10px 12px; border-radius: 10px; background: var(--brand-weak); color: var(--brand-strong); font-size: var(--text-xs); }
.wait-approval span { width: 17px; height: 17px; display: grid; place-items: center; border-radius: 50%; background: var(--brand); color: #fff; font-size: 10px; font-weight: 700; }
.bot-answer { margin-top: 12px; color: var(--text); font-size: 14px; line-height: 1.75; overflow-wrap: anywhere; }
.answer-paragraph { margin: 0 0 12px; white-space: pre-line; }
.answer-paragraph:last-child { margin-bottom: 0; }
.answer-paragraph b, .answer-list-item b, .answer-heading b { font-weight: 700; color: var(--text); }
.answer-heading { margin: 18px 0 8px; color: var(--text); font-weight: 700; line-height: 1.55; letter-spacing: -.01em; }
.answer-heading:first-child { margin-top: 0; }
.answer-heading.level-2 { font-size: 16px; }
.answer-heading.level-3 { font-size: 14px; }
.answer-list { display: flex; flex-direction: column; gap: 7px; margin: 4px 0 14px; }
.answer-list-item { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 5px; }
.answer-list-marker { color: var(--brand-strong); font-weight: 700; }
.answer-list-item p { margin: 0; white-space: pre-line; }
.answer-schedule { margin: 16px 0 2px; border-top: 1px solid var(--line); }
.answer-schedule-item { display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 14px; padding: 13px 0; border-bottom: 1px solid var(--line); }
.answer-item-meta { display: flex; flex-direction: column; align-items: flex-start; gap: 7px; }
.answer-status { display: inline-flex; align-items: center; min-height: 20px; padding: 2px 8px; border-radius: 999px; font-size: 10px; font-weight: 700; line-height: 1.4; }
.answer-status.pending { background: var(--brand-weak); color: var(--brand-strong); }
.answer-status.confirmed { background: color-mix(in srgb, var(--ok) 11%, var(--surface)); color: color-mix(in srgb, var(--ok) 82%, var(--text)); }
.answer-item-body { min-width: 0; }
.answer-item-body h4 { margin: 0 0 4px; color: var(--text); font-size: 14px; font-weight: 700; line-height: 1.65; }
.answer-source { margin: 0; color: var(--text-3); font-size: 12px; line-height: 1.65; }
.answer-source span { margin-right: 7px; color: var(--text-3); font-weight: 700; }
.assistant-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 14px; color: var(--text-3); font-size: 9px; }
.copy-btn { border: none; background: transparent; color: var(--text-3); font-size: 10px; }
.copy-btn:hover { color: var(--brand-strong); }

.workflow-card { align-self: center; width: min(780px, 100%); padding: 20px; border-radius: 14px; }
.workflow-head { display: flex; align-items: center; gap: 12px; }
.workflow-glyph { width: 40px; height: 40px; display: grid; place-items: center; flex-shrink: 0; border-radius: 12px; background: var(--brand-weak); color: var(--brand-strong); font-size: var(--text-sm); font-weight: 700; }
.workflow-head h3 { margin: 0; font-size: 16px; letter-spacing: -.01em; }
.done-pill { margin-left: auto; padding: 4px 9px; border-radius: 999px; background: color-mix(in srgb, var(--ok) 11%, var(--surface)); color: color-mix(in srgb, var(--ok) 82%, var(--text)); font-size: 10px; font-weight: 600; }
.workflow-summary { margin: 18px 0; color: var(--text); font-size: 15px; font-weight: 600; line-height: 1.65; }
.run-steps { display: flex; flex-direction: column; gap: 0; margin: 0 0 18px; padding: 0; list-style: none; }
.run-steps li { position: relative; display: grid; grid-template-columns: 22px 1fr; gap: 2px 10px; min-height: 42px; padding: 7px 0; }
.run-steps li:not(:last-child)::after { content: ''; position: absolute; left: 10px; top: 28px; bottom: -5px; width: 1px; background: var(--line); }
.step-check { position: relative; z-index: 1; grid-row: span 2; width: 21px; height: 21px; display: grid; place-items: center; border-radius: 50%; background: color-mix(in srgb, var(--ok) 12%, var(--surface)); color: var(--ok); font-size: 10px; font-weight: 700; }
.run-steps b { font-size: var(--text-xs); font-weight: 600; }
.run-steps small { color: var(--text-3); font-size: 10px; line-height: 1.5; }
.section-label { margin: 0 0 9px; color: var(--text-3); font-size: 10px; font-weight: 600; letter-spacing: .04em; }
.wf-findings { display: flex; flex-direction: column; gap: 7px; }
.finding { display: flex; flex-direction: column; gap: 4px; width: 100%; padding: 11px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: var(--text); text-align: left; transition: border-color var(--dur-1) var(--ease-out), background var(--dur-1) var(--ease-out); }
.finding:hover { border-color: color-mix(in srgb, var(--brand) 50%, var(--line)); background: color-mix(in srgb, var(--brand-weak) 22%, var(--surface)); }
.finding small { display: flex; align-items: center; gap: 4px; color: var(--text-3); font-size: 10px; }
.finding-source { color: var(--brand-strong); font-size: 10px; font-weight: 700; }
.finding b { font-size: var(--text-xs); font-weight: 700; line-height: 1.6; }
.wf-schedule { margin-top: 16px; }
.wf-schedule > div { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-top: 1px solid var(--line); font-size: var(--text-xs); }
.wf-schedule time { color: var(--brand-strong); font-variant-numeric: tabular-nums; }

.composer-wrap { position: relative; width: min(780px, 100%); margin: 0 auto; padding: 12px 0 16px; }
.composer {
  display: flex; flex-direction: column; gap: 6px; padding: 12px; border-radius: 18px;
  background: var(--surface); box-shadow: 0 8px 24px rgba(29,28,26,.08), 0 1px 2px rgba(29,28,26,.05);
  transition: border-color var(--dur-1) var(--ease-out), box-shadow var(--dur-1) var(--ease-out);
}
.composer:focus-within { border-color: color-mix(in srgb, var(--brand) 62%, var(--line)); box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand) 10%, transparent), 0 8px 24px rgba(29,28,26,.08); }
.composer textarea { width: 100%; min-width: 0; min-height: 46px; max-height: 120px; padding: 7px 4px; border: none; outline: none; resize: none; background: transparent; font-size: 15px; line-height: 1.6; }
.composer textarea::placeholder { color: var(--text-3); }
.composer-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-width: 0; }
.composer-tools, .composer-options { display: flex; align-items: center; gap: 7px; min-width: 0; }
.composer-icon { width: 32px; height: 32px; display: grid; place-items: center; flex-shrink: 0; border: 1px solid transparent; border-radius: 50%; background: transparent; color: var(--text-2); font-size: 17px; line-height: 1; transition: background var(--dur-1) var(--ease-out), color var(--dur-1) var(--ease-out), border-color var(--dur-1) var(--ease-out); }
.composer-icon:hover { border-color: var(--line); background: var(--surface-2); color: var(--text); }
.composer-icon:disabled { opacity: .4; pointer-events: none; }
.plus-btn { border-color: var(--line); background: var(--surface-2); color: var(--text); font-size: 21px; font-weight: 300; }
.plus-btn:hover, .plus-btn[aria-expanded="true"] { border-color: var(--brand); background: var(--brand-weak); color: var(--brand-strong); }
.permission-pill { height: 32px; display: inline-flex; align-items: center; gap: 6px; padding: 0 10px; border: 1px solid color-mix(in srgb, var(--warn) 22%, var(--line)); border-radius: 999px; background: color-mix(in srgb, var(--warn) 8%, var(--surface)); color: color-mix(in srgb, var(--warn) 80%, var(--text)); font-size: 10px; white-space: nowrap; transition: border-color var(--dur-1) var(--ease-out), background var(--dur-1) var(--ease-out); }
.permission-pill span { width: 14px; height: 14px; display: grid; place-items: center; border: 1px solid currentColor; border-radius: 50%; font-size: 9px; font-weight: 700; }
.permission-pill:hover, .permission-pill[aria-expanded="true"] { border-color: var(--warn); background: color-mix(in srgb, var(--warn) 14%, var(--surface)); }
.permission-pill.granted { border-color: color-mix(in srgb, var(--ok) 28%, var(--line)); background: color-mix(in srgb, var(--ok) 8%, var(--surface)); color: color-mix(in srgb, var(--ok) 82%, var(--text)); }
.upload-state { display: inline-flex; align-items: center; gap: 5px; color: var(--text-3); font-size: 10px; white-space: nowrap; }
.upload-state i { width: 6px; height: 6px; border-radius: 50%; background: var(--brand); animation: breathe 1s infinite; }
.composer-select { height: 32px; max-width: 168px; padding: 0 26px 0 10px; border: 1px solid var(--line); border-radius: 999px; outline: none; background: var(--surface-2); color: var(--text-2); font: inherit; font-size: 10px; cursor: pointer; text-overflow: ellipsis; }
.composer-select:focus-visible { border-color: var(--brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand) 12%, transparent); }
.effort-select { max-width: 72px; }
.voice-btn { font-size: 11px; }
.send-btn { height: 34px; min-width: 68px; display: inline-flex; align-items: center; justify-content: center; gap: 7px; padding: 0 13px; border: 1px solid var(--text); border-radius: 999px; background: var(--text); color: var(--surface); font-size: 11px; font-weight: 600; transition: background var(--dur-1) var(--ease-out), transform var(--dur-1) var(--ease-out), opacity var(--dur-1) var(--ease-out); }
.send-btn i { font-size: 14px; font-style: normal; font-weight: 400; }
.send-btn:hover { background: color-mix(in srgb, var(--text) 86%, var(--surface)); }
.send-btn:active { transform: scale(.97); }
.send-btn:disabled { opacity: .32; pointer-events: none; }
.stop-btn { height: 34px; padding: 0 13px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--text-2); font-size: 10px; }
.hidden-input { display: none; }
.composer-hint { display: flex; justify-content: space-between; gap: 10px; padding: 8px 4px 0; color: var(--text-3); font-size: 9px; }
.attachment-strip { display: flex; gap: 7px; padding: 1px 0 5px; overflow-x: auto; scrollbar-width: thin; }
.attachment-chip { min-width: 180px; max-width: 250px; display: flex; align-items: center; gap: 8px; padding: 7px 8px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); }
.attachment-kind { width: 27px; height: 27px; display: grid; place-items: center; flex-shrink: 0; border-radius: 7px; background: var(--surface); color: var(--brand-strong); font-size: 14px; }
.attachment-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.attachment-copy b { overflow: hidden; font-size: 10px; font-weight: 600; white-space: nowrap; text-overflow: ellipsis; }
.attachment-copy small { color: var(--text-3); font-size: 9px; }
.attachment-chip button { width: 22px; height: 22px; display: grid; place-items: center; flex-shrink: 0; border: none; border-radius: 50%; background: transparent; color: var(--text-3); font-size: 15px; }
.attachment-chip button:hover { background: var(--surface); color: var(--text); }

.workspace-menu {
  position: absolute; left: 0; bottom: calc(100% + 8px); z-index: 31; width: min(460px, 100%);
  max-height: min(620px, calc(100vh - 180px)); overflow-y: auto; padding: 20px;
  border-radius: 16px; box-shadow: var(--shadow-2); animation: menu-in 180ms var(--ease-out);
}
.workspace-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.workspace-head h3 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
.workspace-intro { margin: 10px 0 16px; color: var(--text-2); font-size: var(--text-xs); line-height: 1.65; }
.workspace-path { display: flex; flex-direction: column; gap: 6px; }
.workspace-path span, .workspace-list-label { color: var(--text-3); font-size: 10px; font-weight: 600; }
.workspace-path-row { display: flex; align-items: center; gap: 8px; }
.workspace-path input { flex: 1; min-width: 0; width: 100%; height: 40px; padding: 0 11px; border: 1px solid var(--line); border-radius: 9px; outline: none; background: var(--surface-2); font: inherit; font-size: var(--text-xs); }
.workspace-choose { flex-shrink: 0; height: 40px; padding-inline: 12px; white-space: nowrap; }
.workspace-choose:disabled { cursor: wait; opacity: .6; }
.workspace-path input:focus-visible { border-color: var(--brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand) 12%, transparent); }
.workspace-grant-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 10px; }
.workspace-grant-row .btn { height: 34px; font-size: 10px; }
.access-switch { display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface-2); }
.access-switch button { height: 26px; padding: 0 11px; border: none; border-radius: 999px; background: transparent; color: var(--text-3); font-size: 10px; }
.access-switch button.on { background: var(--surface); color: var(--text); box-shadow: 0 1px 3px rgba(29,28,26,.08); }
.workspace-confirm { display: flex; align-items: flex-start; gap: 8px; margin-top: 12px; padding: 10px; border-radius: 9px; background: color-mix(in srgb, var(--warn) 9%, var(--surface)); color: color-mix(in srgb, var(--warn) 78%, var(--text)); font-size: 10px; line-height: 1.55; }
.workspace-confirm input { margin-top: 2px; accent-color: var(--warn); }
.workspace-list { margin-top: 18px; padding-top: 15px; border-top: 1px solid var(--line); }
.workspace-list-label { margin: 0 0 9px; }
.workspace-item { display: flex; align-items: center; gap: 9px; padding: 9px 0; }
.workspace-item + .workspace-item { border-top: 1px solid var(--line); }
.workspace-item-icon { width: 30px; height: 30px; display: grid; place-items: center; flex-shrink: 0; border-radius: 8px; background: var(--brand-weak); color: var(--brand-strong); }
.workspace-item-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 3px; }
.workspace-item-copy b { overflow: hidden; font-size: 10px; font-weight: 600; white-space: nowrap; text-overflow: ellipsis; }
.workspace-item-copy small { color: var(--text-3); font-size: 9px; }
.workspace-item-actions { display: flex; align-items: center; gap: 4px; }
.workspace-item-actions button { height: 25px; padding: 0 7px; border: 1px solid transparent; border-radius: 999px; background: transparent; color: var(--text-3); font-size: 9px; }
.workspace-item-actions button.on { border-color: var(--line); background: var(--surface-2); color: var(--text); }
.workspace-item-actions .remove-workspace { width: 25px; padding: 0; font-size: 15px; }
.workspace-item-actions .remove-workspace:hover { background: color-mix(in srgb, var(--warn) 9%, var(--surface)); color: var(--warn); }
.workspace-security { margin: 14px 0 0; padding: 10px 11px; border-radius: 9px; background: var(--surface-2); color: var(--text-3); font-size: 9px; line-height: 1.6; }

.cap-menu {
  position: absolute; left: 0; bottom: calc(100% + 8px); z-index: 30; width: 100%; max-width: 720px;
  max-height: min(650px, calc(100vh - 180px)); overflow-y: auto; padding: 20px;
  border-radius: 16px; box-shadow: var(--shadow-2); animation: menu-in 180ms var(--ease-out);
}
.cap-menu-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.cap-menu-head h3 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
.close-btn { width: 30px; height: 30px; display: grid; place-items: center; flex-shrink: 0; border: none; border-radius: 50%; background: var(--surface-2); color: var(--text-2); font-size: 18px; line-height: 1; }
.close-btn:hover { background: var(--brand-weak); color: var(--brand-strong); }
.cap-section + .cap-section { margin-top: 16px; }
.cap-section-title { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 9px; }
.cap-section-title b { font-size: var(--text-xs); font-weight: 700; }
.cap-section-title span { color: var(--text-3); font-size: 10px; }
.cap-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.cap-grid button { position: relative; display: flex; align-items: center; gap: 9px; min-width: 0; min-height: 56px; padding: 10px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: var(--text); text-align: left; transition: border-color var(--dur-1) var(--ease-out), background var(--dur-1) var(--ease-out), transform var(--dur-1) var(--ease-out); }
.cap-grid button:hover { border-color: color-mix(in srgb, var(--brand) 50%, var(--line)); background: color-mix(in srgb, var(--brand-weak) 28%, var(--surface)); transform: translateY(-1px); }
.cap-grid button:disabled { opacity: .45; pointer-events: none; }
.cap-grid button > span:nth-child(2) { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.cap-grid b { font-size: var(--text-xs); font-weight: 600; }
.cap-grid small { overflow: hidden; color: var(--text-3); font-size: 10px; white-space: nowrap; text-overflow: ellipsis; }
.cap-grid i { margin-left: auto; color: var(--brand-strong); font-size: 13px; font-style: normal; }
.cap-glyph { width: 30px; height: 30px; display: grid; place-items: center; flex-shrink: 0; border-radius: 9px; background: var(--surface-2); color: var(--brand-strong); font-size: 10px; font-weight: 700; }
.cap-grid :deep(.chic) { width: 30px; height: 30px; border-radius: 9px; box-shadow: none; }
.cap-grid :deep(.chic svg) { width: 16px; height: 16px; }
.cap-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--line); }
.cap-grid.compact { grid-template-columns: 1fr; }
.plugin-state { margin-left: auto; flex-shrink: 0; color: var(--text-3); font-size: 9px; }
.plugin-state.configured { color: var(--ok); }
.calendar-cap { width: 100%; display: flex; align-items: center; gap: 10px; margin-top: 16px; padding: 11px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); color: var(--text); text-align: left; }
.calendar-cap:hover { border-color: var(--brand); }
.calendar-cap > span:nth-child(2) { display: flex; flex-direction: column; gap: 3px; }
.calendar-cap b { font-size: var(--text-xs); }
.calendar-cap small { color: var(--text-3); font-size: 10px; }
.calendar-cap i { margin-left: auto; color: var(--brand-strong); font-style: normal; }
.cap-footnote { margin: 12px 2px 0; color: var(--text-3); font-size: 9px; text-align: center; }

.drawer-mask { position: fixed; inset: 0; z-index: 55; background: rgba(29, 28, 26, .2); backdrop-filter: blur(3px); }
.calendar-preview { position: absolute; top: 80px; right: 24px; bottom: 24px; width: min(390px, calc(100vw - 32px)); padding: 22px; overflow-y: auto; border-radius: 16px; box-shadow: var(--shadow-2); animation: drawer-in 220ms var(--ease-out); }
.drawer-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 20px; }
.drawer-head h3 { margin: 0; font-size: 21px; letter-spacing: -.02em; }
.drawer-empty { padding: 36px 0; color: var(--text-3); text-align: center; font-size: var(--text-sm); }
.calendar-list { display: flex; flex-direction: column; gap: 9px; }
.calendar-item { display: flex; align-items: center; gap: 13px; padding: 13px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); }
.calendar-item time { min-width: 72px; color: var(--brand-strong); font-size: var(--text-xs); font-variant-numeric: tabular-nums; }
.calendar-item > div { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.calendar-item b { font-size: var(--text-sm); font-weight: 700; }
.calendar-item small { color: var(--text-3); font-size: 10px; }
.calendar-item button { width: 30px; height: 30px; margin-left: auto; border: none; border-radius: 50%; background: var(--surface); color: var(--brand-strong); }
.full-calendar { width: 100%; height: 40px; margin-top: 20px; border-color: var(--text); background: var(--text); color: var(--surface); }
.full-calendar:hover { border-color: color-mix(in srgb, var(--text) 86%, var(--surface)); background: color-mix(in srgb, var(--text) 86%, var(--surface)); color: var(--surface); }

.mask { position: fixed; inset: 0; z-index: 70; display: grid; place-items: center; padding: 16px; background: rgba(29, 28, 26, .34); backdrop-filter: blur(5px); }
.approve { width: min(460px, 100%); overflow: hidden; border-radius: 16px; outline: none; box-shadow: var(--shadow-2); animation: approve-in 180ms var(--ease-out); }
.warn-bar { display: flex; align-items: center; gap: 8px; padding: 11px 18px; background: var(--warn); color: #fff; font-size: var(--text-xs); font-weight: 600; }
.warn-bar span { width: 17px; height: 17px; display: grid; place-items: center; border: 1px solid rgba(255,255,255,.6); border-radius: 50%; font-size: 10px; }
.approval-heading { margin: 20px 20px 14px; }
.approval-heading h4 { display: flex; align-items: center; gap: 9px; margin: 0; font-size: 18px; }
.approval-heading h4 .risk { margin-left: 0; }
.approval-heading > p:last-child { margin: 8px 0 0; color: var(--text-2); font-size: var(--text-xs); line-height: 1.6; }
.ap-args { max-height: 210px; margin: 0 20px; padding: 13px; overflow: auto; border-radius: 10px; background: var(--surface-2); font-family: inherit; font-size: var(--text-xs); line-height: 1.7; }
.ap-args p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.approval-note { margin: 13px 20px 0; color: var(--text-3); font-size: var(--text-xs); line-height: 1.6; }
.ap-acts { display: flex; justify-content: flex-end; gap: 10px; margin: 20px; }
.ap-acts .btn { min-width: 92px; height: 38px; }
.ap-acts .btn-primary { border-color: var(--text); background: var(--text); color: var(--surface); }
.ap-acts .btn-primary:hover { border-color: color-mix(in srgb, var(--text) 86%, var(--surface)); background: color-mix(in srgb, var(--text) 86%, var(--surface)); color: var(--surface); }
.ap-acts .btn.selected { border-color: var(--brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand) 12%, transparent); }
.approval-shortcut { margin: -8px 20px 16px; color: var(--text-3); font-size: 9px; text-align: right; }
.toast { position: fixed; left: 50%; bottom: 28px; z-index: 90; max-width: min(520px, calc(100vw - 32px)); padding: 11px 17px; transform: translateX(-50%); border-radius: 999px; background: #241f1a; color: #fff; box-shadow: var(--shadow-2); font-size: var(--text-xs); }

@keyframes breathe { 50% { opacity: .4; transform: scale(.86); } }
@keyframes tool-pulse { 50% { box-shadow: 0 0 0 4px color-mix(in srgb, var(--brand) 13%, transparent); } }
@keyframes menu-in { from { opacity: 0; transform: translateY(8px) scale(.99); } to { opacity: 1; transform: none; } }
@keyframes drawer-in { from { opacity: 0; transform: translateX(18px); } to { opacity: 1; transform: none; } }
@keyframes approve-in { from { opacity: 0; transform: translateY(6px) scale(.985); } to { opacity: 1; transform: none; } }

@media (max-width: 1120px) {
  .chat-workspace { grid-template-columns: 188px minmax(0, 1fr); }
  .agent-pill { display: none; }
  .context-pill { max-width: 170px; }
  .conversation-head { padding-inline: 20px; }
}
@media (max-width: 960px) {
  .chat-workspace { grid-template-columns: 68px minmax(0, 1fr); }
  .session-rail { padding: 14px 9px 10px; }
  .rail-heading, .session-section-label, .new-label, .session-copy, .session-active, .agent-mini .session-copy, .online-dot { display: none; }
  .rail-head { justify-content: center; margin-bottom: 16px; }
  .new-chat { width: 38px; height: 38px; justify-content: center; padding: 0; }
  .session-item { justify-content: center; min-height: 44px; padding: 7px 0; border: none; }
  .session-item.on { border: none; background: var(--surface); }
  .session-mark { width: 30px; height: 30px; }
  .agent-mini { justify-content: center; padding-inline: 0; }
  .context-pill { display: none; }
  .messages { padding-inline: 22px; }
}
@media (max-width: 900px) {
  .composer-toolbar { flex-wrap: wrap; }
  .composer-options { margin-left: auto; }
  .model-select { max-width: 140px; }
}
@media (max-width: 720px) {
  .conversation-head { min-height: 66px; padding: 12px 16px; }
  .conversation-title { gap: 9px; }
  .conversation-title h2 { font-size: 16px; }
  .calendar-link { width: 34px; padding: 0; justify-content: center; font-size: 0; }
  .calendar-link span { font-size: 11px; }
  .messages { padding: 20px 16px 24px; }
  .welcome { padding-block: 24px; }
  .welcome h1 { font-size: 30px; }
  .welcome-desc { font-size: 14px; }
  .context-strip { flex-wrap: wrap; gap: 7px 10px; }
  .context-strip > span:last-child { width: 100%; margin-left: 0; }
  .quick { grid-template-columns: 1fr; }
  .assistant-content { padding-left: 0; }
  .assistant-meta { margin-bottom: 12px; }
  .answer-schedule-item { grid-template-columns: 1fr; gap: 7px; }
  .answer-item-meta { flex-direction: row; align-items: center; }
  .composer-wrap { padding-inline: 0; }
  .composer-toolbar { flex-wrap: wrap; }
  .composer-options { margin-left: auto; }
  .model-select { max-width: 140px; }
  .workflow-card { padding: 16px; }
  .cap-menu { position: fixed; left: 12px; right: 12px; bottom: 108px; width: auto; max-width: none; max-height: calc(100vh - 140px); }
  .workspace-menu { position: fixed; left: 12px; right: 12px; bottom: 108px; width: auto; max-width: none; max-height: calc(100vh - 140px); }
  .cap-grid { grid-template-columns: 1fr; }
  .cap-columns { grid-template-columns: 1fr; gap: 0; }
  .composer-hint span:last-child { display: none; }
}
@media (max-width: 620px) {
  .chat-workspace { display: block; border-radius: 12px; }
  .conversation { height: 100%; }
  .session-rail { display: none; }
  .mobile-new { display: grid; }
  .conversation-head { padding-inline: 12px; }
  .user-bub { max-width: 92%; }
  .assistant-actions > span { display: none; }
  .assistant-actions { justify-content: flex-end; }
  .tool summary em { display: none; }
  .calendar-preview { top: 72px; right: 12px; bottom: 12px; width: calc(100vw - 24px); }
  .composer { border-radius: 16px; }
  .composer-tools { width: 100%; }
  .composer-options { width: 100%; justify-content: flex-end; }
  .model-select { flex: 1; max-width: none; }
  .workspace-item { align-items: flex-start; flex-wrap: wrap; }
  .workspace-item-copy { min-width: calc(100% - 45px); }
  .workspace-item-actions { margin-left: 39px; }
}
@media (max-width: 420px) {
  .permission-pill { padding-inline: 8px; font-size: 9px; }
  .composer-tools { gap: 4px; }
  .composer-options { gap: 5px; }
  .voice-btn { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .messages, .cap-menu, .workspace-menu, .calendar-preview, .approve, .tool-node.run, .turn-state i { animation: none; scroll-behavior: auto; }
}
</style>
